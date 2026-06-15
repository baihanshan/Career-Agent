"""FastAPI application entrypoint."""

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover - allows structure checks before deps install
    FastAPI = None


def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Install backend dependencies first.")

    from backend.app.api.routes import router

    app = FastAPI(title="CareerPilot Agent")
    app.include_router(router)
    return app


app = create_app() if FastAPI is not None else None
