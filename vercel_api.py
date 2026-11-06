"""The API's entry point on Vercel (DECISIONS D131): the Python service's root is the
repository, so the SQL files in db/sql ship with it (a service can't read outside its
root). The API's package `app` lives in api/, so put that folder on the import path,
then hand Vercel the ASGI app.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))

from app.asgi import app  # noqa: E402 (after the path is set)

__all__ = ["app"]
