"""
SJM-Integrator FastAPI entry point.

Run locally:   python app.py        -> serves http://localhost:8000
Run in Docker: docker compose up     -> db (apache/age) + app

DB connection + graph name come from env (DB_DSN, GRAPH_NAME); see docker-compose.yml.
"""
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api import routes_config, routes_graph, routes_import
from db.age_connection import get_connection
from db.graph_setup import init_graph

app = FastAPI(title="SJM-Integrator")

# Initialize the graph + labels once at startup.
init_graph(get_connection())

app.include_router(routes_import.router)
app.include_router(routes_graph.router)
app.include_router(routes_config.router)

# Serve the single-page frontend at the root.
_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import threading
    import webbrowser

    import uvicorn

    url = "http://localhost:8000"
    # Open a browser only when run directly against a local DB (not inside the
    # app container, where DB_DSN points at the 'db' service host).
    in_container = "@db:" in os.environ.get("DB_DSN", "")
    if not in_container and os.environ.get("OPEN_BROWSER", "1") == "1":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    print(f"SJM-Integrator running at {url}")
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
