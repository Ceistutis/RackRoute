"""FastAPI application entrypoint."""

from fastapi import FastAPI

app = FastAPI(title="RackRoute API", version="0.1.0")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Return the application's liveness status."""
    return {"status": "ok"}
