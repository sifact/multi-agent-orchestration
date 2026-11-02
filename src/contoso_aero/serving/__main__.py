"""Run the playground: `uv run contoso-aero-ui [--port 8010]`."""

from __future__ import annotations

import argparse
import sys

from ..config import SettingsError
from ..llm import ModelError
from .web_app import DEFAULT_PORT, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contoso-aero-ui", description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        serve(args.port)
    except (FileNotFoundError, SettingsError, ModelError) as error:
        print(f"Cannot start the playground: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
