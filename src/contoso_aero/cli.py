"""Command line: ask the Contoso Aero Engines assistant a question (router or coordinator)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .agents.common import AgentContext
from .config import DataSettings, SettingsError, load_model_settings
from .coordination import ask_coordinated
from .llm import ChatCompletionClient, ModelError
from .routing import PipelineResult, ask


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contoso-aero", description=__doc__)
    parser.add_argument("question", nargs="?", help="Question to ask; omit to read stdin.")
    parser.add_argument("--json", action="store_true", help="Print the full result as JSON.")
    parser.add_argument("--coordinator", action="store_true",
                        help="Version 2: let several agents work on the question (default: router).")
    args = parser.parse_args(argv)
    question = args.question if args.question is not None else sys.stdin.read()

    data = DataSettings()
    if not data.database_path.is_file():
        print("Dataset missing. Build it with: uv run python -m contoso_aero.data", file=sys.stderr)
        return 2
    try:
        settings = load_model_settings()
        context = AgentContext(model=ChatCompletionClient(settings),
                               database_path=data.database_path,
                               knowledge_dir=data.knowledge_dir, max_steps=settings.max_agent_steps)
    except (SettingsError, ModelError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    result = (ask_coordinated if args.coordinator else ask)(question, context)
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(_format(result))
    return 1 if result.error else 0


def _format(result: PipelineResult) -> str:
    if result.error:
        return f"Error: {result.error}"
    if result.plan is not None:
        steps = ", ".join(f"{step.agent} {result.step_seconds.get(step.id, 0.0):.2f}s"
                          for step in result.plan.steps)
        cost = (f"[{', '.join(result.agents_called) or result.label}] plan "
                f"{result.plan_seconds:.2f}s, steps ({steps}), synthesis "
                f"{result.synthesis_seconds:.2f}s, total {result.total_seconds:.2f}s")
    else:
        cost = (f"[{result.label}] intent {result.intent_seconds:.2f}s, agent "
                f"{result.agent_seconds:.2f}s, total {result.total_seconds:.2f}s")
    return f"{result.answer}\n\n{cost}"


if __name__ == "__main__":
    raise SystemExit(main())
