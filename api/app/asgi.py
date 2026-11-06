"""The ASGI app for Vercel (DECISIONS D131): Vercel's Python runtime imports a module-level
`app`. Uvicorn locally uses the factory instead (app.main:create_app --factory); either way
create_app() runs the startup guards before the first request.
"""

from app.main import create_app

app = create_app()
