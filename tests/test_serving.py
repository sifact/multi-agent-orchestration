"""Offline tests for the browser playground: result shaping, direct agent calls and the HTTP API."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Sequence
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from contoso_aero.agents.common import AgentContext
from contoso_aero.config import DataSettings, ModelSettings
from contoso_aero.llm import ModelResponse, ToolCall
from contoso_aero.serving import describe, run_question, shape_result
from contoso_aero.serving.web_app import _Handler


class ScriptedModel:
    def __init__(self, *responses: ModelResponse) -> None:
        self.responses = list(responses)

    def complete(self, messages: list[dict[str, object]],
                 tools: Sequence[dict[str, object]] = ()) -> ModelResponse:
        return self.responses.pop(0)


def _sql_then_answer() -> list[ModelResponse]:
    return [
        ModelResponse(content=None, input_tokens=10, output_tokens=2,
                      tool_calls=[ToolCall("c1", "query_sql", {"sql": "SELECT esn FROM engines"})]),
        ModelResponse(content="CX7-10001 is active.", tool_calls=[], input_tokens=12,
                      output_tokens=4),
    ]


@pytest.fixture
def context(tmp_path: Path):
    database = tmp_path / "test.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE engines (esn TEXT, status TEXT)")
        connection.execute("INSERT INTO engines VALUES ('CX7-10001', 'active')")
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    def build(*responses: ModelResponse) -> AgentContext:
        return AgentContext(model=ScriptedModel(*responses), database_path=database,
                            knowledge_dir=knowledge_dir, max_steps=2)
    return build


def test_given_direct_mode_when_asked_then_intent_is_skipped_and_sql_is_traced(context) -> None:
    result = run_question("Which engines are active?", "telemetry", context(*_sql_then_answer()))

    shaped = shape_result(result, "telemetry")

    assert shaped["intent"] is None and shaped["label"] == "telemetry"
    assert shaped["answer"] == "CX7-10001 is active."
    step = shaped["agent"]["trace"][0]
    assert step["tool"] == "query_sql" and step["arguments"]["sql"] == "SELECT esn FROM engines"
    assert "CX7-10001" in step["output"]


def test_given_router_mode_when_off_topic_then_refusal_is_shaped_without_agent(context) -> None:
    result = run_question("Tell me a joke", "router",
                          context(ModelResponse(content="unsupported", tool_calls=[])))

    shaped = shape_result(result, "router")

    assert shaped["refused"] and shaped["agent"] is None
    assert shaped["intent"]["label"] == "unsupported"


def test_given_settings_when_described_then_no_key_is_exposed(tmp_path: Path) -> None:
    settings = ModelSettings(base_url="https://api.example.test/v1", api_key="secret-key",
                             model_name="m")

    info = describe(settings, DataSettings(knowledge_dir=tmp_path))

    assert "secret-key" not in json.dumps(info)
    assert info["endpoint"] == "api.example.test"
    assert [agent["name"] for agent in info["agents"]] == ["telemetry", "service", "production",
                                                           "quality", "knowledge"]


@pytest.fixture
def server(context):
    handler = type("Handler", (_Handler,), {"context": context(*_sql_then_answer()),
                                            "info": {"model": "m"}, "lock": Lock()})
    handler.log_message = lambda *args: None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _post(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    request = Request(url, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def test_given_running_server_when_page_and_question_requested_then_both_are_served(server) -> None:
    with urlopen(f"{server}/", timeout=5) as response:
        assert b"Contoso Aero" in response.read()

    status, body = _post(f"{server}/api/ask", {"question": "Active engines?", "mode": "telemetry"})

    assert status == 200 and body["answer"] == "CX7-10001 is active."


def test_given_unknown_mode_or_empty_question_when_posted_then_request_is_rejected(server) -> None:
    assert _post(f"{server}/api/ask", {"question": "Hi", "mode": "evaluation_only"})[0] == 400
    assert _post(f"{server}/api/ask", {"question": "  ", "mode": "router"})[0] == 400
