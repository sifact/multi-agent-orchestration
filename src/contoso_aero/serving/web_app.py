"""Browser playground for trying the router, coordinator and agent modules by hand.

Standard library only. Locally it binds to loopback; the public demo runs the same handler as a
Vercel function (see deploy/vercel). The model key never leaves the server. Questions run
one at a time behind a lock: the free-tier endpoint is rate limited, and parallel questions would
only add retry wait to each other's timings.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from threading import Lock
from urllib.parse import urlsplit

from ..agents.common import AgentContext, AgentReply
from ..config import DataSettings, ModelSettings, load_model_settings
from ..coordination import ask_coordinated
from ..data import TABLE_OWNERS
from ..llm import ChatCompletionClient
from ..routing import LABELS, ROUTES, PipelineResult, ask

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8010
MAX_REQUEST_BYTES = 4_096
MAX_QUESTION_CHARS = 1_000
ROUTER_MODE = "router"
COORDINATOR_MODE = "coordinator"


def shape_result(result: PipelineResult, mode: str) -> dict[str, object]:
    """Turn a pipeline result into the JSON the page renders; no prompts or keys leave here."""
    intent = result.intent
    return {
        "mode": mode,
        "question": result.question,
        "label": result.label,
        "answer": result.answer,
        "refused": result.refused,
        "error": result.error,
        "timing": {"intent": result.intent_seconds, "agent": result.agent_seconds,
                   "total": result.total_seconds, "plan": result.plan_seconds,
                   "steps": result.step_seconds, "synthesis": result.synthesis_seconds},
        "agents_called": result.agents_called,
        "plan": None if result.plan is None else asdict(result.plan),
        "coordination_steps": [
            {
                "id": execution.step.id,
                "agent": execution.step.agent,
                "question": execution.step.question,
                "depends_on": list(execution.step.depends_on),
                "status": execution.status,
                "seconds": execution.seconds,
                "answer": execution.reply.answer if execution.reply else "",
                "error": execution.error,
                "tool_calls": [asdict(step) for step in execution.reply.trace]
                if execution.reply else [],
            }
            for execution in result.coordination_steps
        ],
        "intent": None if intent is None else {
            "label": intent.label, "raw": intent.raw, "input_tokens": intent.input_tokens,
            "output_tokens": intent.output_tokens, "model_seconds": intent.model_seconds,
            "retry_wait_seconds": intent.retry_wait_seconds},
        "agent": None if result.agent is None else _shape_reply(result.agent),
    }


def _shape_reply(reply: AgentReply) -> dict[str, object]:
    return {
        "name": reply.agent, "input_tokens": reply.input_tokens,
        "output_tokens": reply.output_tokens, "model_seconds": reply.model_seconds,
        "retry_wait_seconds": reply.retry_wait_seconds, "model_calls": reply.model_calls,
        "tool_calls": reply.tool_calls, "trace": [asdict(step) for step in reply.trace],
    }


def run_question(question: str, mode: str, context: AgentContext) -> PipelineResult:
    """Ask through v1 routing, v2 coordination, or one agent directly."""
    if mode == ROUTER_MODE:
        return ask(question, context)
    if mode == COORDINATOR_MODE:
        return ask_coordinated(question, context)
    started = time.perf_counter()
    reply = ROUTES[mode](question, context)
    elapsed = time.perf_counter() - started
    return PipelineResult(
        question=question, label=mode, answer=reply.answer, refused=False, intent=None,
        agent=reply, intent_seconds=0.0, agent_seconds=elapsed, total_seconds=elapsed,
        error=reply.error, agents_called=[reply.agent])


def describe(settings: ModelSettings, data: DataSettings) -> dict[str, object]:
    """What the page shows in its header and agent cards, without credentials."""
    agents = [{"name": name, "tables": list(TABLE_OWNERS.get(name, ()))} for name in ROUTES]
    documents = sorted(path.stem for path in data.knowledge_dir.glob("*.md"))
    return {"model": settings.model_name, "endpoint": urlsplit(settings.base_url).hostname,
            "labels": list(LABELS), "agents": agents, "documents": documents}


def _index_html() -> bytes:
    return files(__package__).joinpath("static/index.html").read_bytes()


class _Handler(BaseHTTPRequestHandler):
    context: AgentContext
    info: dict[str, object]
    lock: Lock

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in {"/", "/index.html"}:
            self._send(HTTPStatus.OK, _index_html(), "text/html; charset=utf-8")
        elif path == "/api/info":
            self._send_json(HTTPStatus.OK, self.info)
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/ask":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if not 0 < length <= MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request size is invalid."})
            return
        try:
            body = json.loads(self.rfile.read(length))
            question = str(body.get("question", "")).strip()
            mode = str(body.get("mode", ROUTER_MODE))
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Send JSON with a question."})
            return
        if not question or len(question) > MAX_QUESTION_CHARS:
            self._send_json(HTTPStatus.BAD_REQUEST,
                            {"error": f"Ask a question of 1 to {MAX_QUESTION_CHARS} characters."})
            return
        if mode not in {ROUTER_MODE, COORDINATOR_MODE} and mode not in ROUTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Unknown mode '{mode}'."})
            return
        with self.lock:
            result = run_question(question, mode, self.context)
        self._send_json(HTTPStatus.OK, shape_result(result, mode))

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json")

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"contoso-aero ui: {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")


def make_handler(data: DataSettings | None = None) -> type[BaseHTTPRequestHandler]:
    """Build the request handler class; the local server and the Vercel function both use it.

    The model key stays in server-side settings and is never sent to the page.

    Raises:
        SettingsError: If the model endpoint is not configured.
        FileNotFoundError: If the dataset has not been built.
    """
    data = data or DataSettings()
    if not data.database_path.is_file():
        raise FileNotFoundError("Dataset missing. Build it with: uv run python -m contoso_aero.data")
    settings = load_model_settings()
    context = AgentContext(model=ChatCompletionClient(settings), database_path=data.database_path,
                           knowledge_dir=data.knowledge_dir, max_steps=settings.max_agent_steps)
    return type("Handler", (_Handler,), {"context": context, "info": describe(settings, data),
                                         "lock": Lock()})


def serve(port: int = DEFAULT_PORT) -> None:
    """Serve the playground on loopback until interrupted."""
    with ThreadingHTTPServer((DEFAULT_HOST, port), make_handler()) as server:
        print(f"Contoso Aero playground at http://{DEFAULT_HOST}:{port}  (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nPlayground stopped.")
