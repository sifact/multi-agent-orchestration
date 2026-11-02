"""Vercel entry point: serves the playground page and its API from one Python function.

Vercel's Python runtime looks for a `BaseHTTPRequestHandler` subclass named `handler`. Every path
is rewritten here (see vercel.json), so the shared handler routes `/`, `/api/info` and `/api/ask`
exactly as it does locally. The package and the trimmed database are copied in by build.sh.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contoso_aero.serving import make_handler


class handler(make_handler()):
    """The shared playground handler, under the name Vercel's Python runtime requires."""
