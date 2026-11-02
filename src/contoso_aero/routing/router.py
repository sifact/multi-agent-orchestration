"""The router: a plain lookup table from intent label to agent module's `handle` function."""

from __future__ import annotations

from collections.abc import Callable

from ..agents import knowledge, production, quality, service, telemetry
from ..agents.common import AgentContext, AgentReply

Handler = Callable[[str, AgentContext], AgentReply]

# Deliberately a dict and nothing smarter: the router picks exactly one module and never merges.
ROUTES: dict[str, Handler] = {
    "telemetry": telemetry.handle,
    "service": service.handle,
    "production": production.handle,
    "quality": quality.handle,
    "knowledge": knowledge.handle,
}

REFUSAL = ("I can only help with Contoso Aero Engines questions about engine telemetry, service "
           "history, production, quality, or procedures and service bulletins.")


def route(label: str) -> Handler | None:
    """Return the module for `label`, or None when the question must be refused."""
    return ROUTES.get(label)
