"""OpenAI-compatible chat client that reports model time and rate-limit wait separately.

Adapted from nl-to-sql's client. The endpoint is rate limited, so a 429 wait is recorded on its
own: folding it into model time would make the latency comparison with project 2 meaningless.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import ModelSettings, SettingsError

MAX_RESPONSE_BYTES = 1_000_000
MAX_RATE_LIMIT_RETRIES = 8
DEFAULT_RATE_LIMIT_WAIT_SECONDS = 20.0
MAX_RATE_LIMIT_WAIT_SECONDS = 65.0
# Some hosts reject a malformed tool call with HTTP 400; a fresh sample usually succeeds.
MAX_MALFORMED_TOOL_CALL_RETRIES = 3

Transport = Callable[[Request, float], bytes]


class ModelError(Exception):
    """Raised when the model is misconfigured, unreachable or answers in an unsupported shape."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """One model turn, with its cost split into token counts, model time and retry wait."""

    content: str | None
    tool_calls: list[ToolCall]
    input_tokens: int = 0
    output_tokens: int = 0
    model_seconds: float = 0.0
    retry_wait_seconds: float = 0.0
    retries: int = 0


class ModelClient(Protocol):
    """Structural interface the agents consume, so tests can script the model."""

    def complete(self, messages: list[dict[str, object]],
                 tools: Sequence[dict[str, object]] = ()) -> ModelResponse: ...


class ChatCompletionClient:
    """Send chat-completions requests through an injectable transport and sleep."""

    def __init__(self, settings: ModelSettings, transport: Transport | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        try:
            settings.require_complete()
        except SettingsError as error:
            raise ModelError(str(error)) from error
        self.settings = settings
        self.transport = self._default_transport if transport is None else transport
        self.sleep = sleep

    def complete(self, messages: list[dict[str, object]],
                 tools: Sequence[dict[str, object]] = ()) -> ModelResponse:
        payload: dict[str, object] = {"model": self.settings.model_name, "messages": messages,
                                      "temperature": 0}
        if tools:
            payload.update(tools=list(tools), tool_choice="auto")
        try:
            body = json.dumps(payload).encode("utf-8")
        except (TypeError, ValueError):
            raise ModelError("Model request contains unsupported data.") from None
        request = Request(
            self.settings.completion_url, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.settings.api_key}",
                     "Content-Type": "application/json",
                     "User-Agent": "contoso-aero/0.1"})
        response_body, model_seconds, waited, retries = self._send(request)
        if len(response_body) > MAX_RESPONSE_BYTES:
            raise ModelError("Model endpoint response exceeded the size limit.")
        try:
            decoded = json.loads(response_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ModelError("Model endpoint returned invalid JSON.") from None
        return _parse_response(decoded, model_seconds, waited, retries)

    def _send(self, request: Request) -> tuple[bytes, float, float, int]:
        """Return the body, time spent in requests, time spent waiting, and retry count."""
        model_seconds = waited = 0.0
        retries = malformed = 0
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            started = time.perf_counter()
            try:
                body = self.transport(request, self.settings.timeout_seconds)
                return body, model_seconds + time.perf_counter() - started, waited, retries
            except HTTPError as error:
                model_seconds += time.perf_counter() - started
                if _is_malformed_tool_call(error) and malformed < MAX_MALFORMED_TOOL_CALL_RETRIES:
                    malformed += 1
                    retries += 1
                    continue
                if error.code != 429 or attempt == MAX_RATE_LIMIT_RETRIES:
                    raise ModelError(f"Model endpoint returned HTTP {error.code}.") from None
                wait = _retry_after_seconds(error)
                if wait > MAX_RATE_LIMIT_WAIT_SECONDS:
                    # A long Retry-After means a daily quota, not a per-minute burst: waiting
                    # the capped time and retrying would only burn minutes per call.
                    raise ModelError(f"Model endpoint quota exhausted; it asks to retry after "
                                     f"{wait:.0f}s.") from None
                self.sleep(wait)
                waited += wait
                retries += 1
            except (URLError, TimeoutError, OSError):
                raise ModelError("Model request failed; check the endpoint and settings.") from None
        raise ModelError("Model endpoint kept rate-limiting the request.")

    @staticmethod
    def _default_transport(request: Request, timeout: float) -> bytes:
        with urlopen(request, timeout=timeout) as response:
            return response.read(MAX_RESPONSE_BYTES + 1)


def _parse_response(payload: object, model_seconds: float, waited: float,
                    retries: int) -> ModelResponse:
    try:
        message = payload["choices"][0]["message"]  # type: ignore[index]
        content = message.get("content")
        raw_calls = message.get("tool_calls") or []
        usage = payload.get("usage") or {}  # type: ignore[union-attr]
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ModelError("Model endpoint returned an unsupported response shape.") from None
    if content is not None and not isinstance(content, str):
        raise ModelError("Model endpoint returned unsupported message content.")
    if not isinstance(raw_calls, list):
        raise ModelError("Model endpoint returned invalid tool calls.")
    return ModelResponse(
        content=content, tool_calls=[_parse_tool_call(call) for call in raw_calls],
        input_tokens=_count(usage, "prompt_tokens"), output_tokens=_count(usage, "completion_tokens"),
        model_seconds=model_seconds, retry_wait_seconds=waited, retries=retries)


def _count(usage: object, key: str) -> int:
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _parse_tool_call(raw: object) -> ToolCall:
    try:
        call_id, function = raw["id"], raw["function"]  # type: ignore[index]
        name, arguments = function["name"], json.loads(function["arguments"])
    except (KeyError, TypeError, json.JSONDecodeError):
        raise ModelError("Model endpoint returned an unsupported tool-call shape.") from None
    if not (isinstance(call_id, str) and isinstance(name, str) and isinstance(arguments, dict)):
        raise ModelError("Model endpoint returned an unsupported tool-call shape.")
    return ToolCall(call_id=call_id, name=name, arguments=arguments)


def _retry_after_seconds(error: HTTPError) -> float:
    """Read Retry-After; the caller refuses waits beyond its cap instead of shortening them."""
    header = error.headers.get("Retry-After") if error.headers else None
    try:
        wait = float(header) if header is not None else DEFAULT_RATE_LIMIT_WAIT_SECONDS
    except ValueError:
        wait = DEFAULT_RATE_LIMIT_WAIT_SECONDS
    return max(wait, 1.0)


def _is_malformed_tool_call(error: HTTPError) -> bool:
    if error.code != 400:
        return False
    try:
        return b"tool_use_failed" in error.read(10_000)
    except OSError:
        return False
