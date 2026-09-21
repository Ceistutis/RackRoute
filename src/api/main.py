"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from datacenter.exceptions import InvalidSafetyMarginError, NoRouteAvailableError, RackNotFoundError
from datacenter.infrastructure import load_layout
from datacenter.services import CableRouteService

from .routes import router

DEFAULT_LAYOUT_PATH = Path(__file__).resolve().parents[2] / "data" / "example_datacenter.json"
FRONTEND_PATH = Path(__file__).resolve().parents[2] / "frontend"


def create_app(layout_path: str | Path = DEFAULT_LAYOUT_PATH) -> FastAPI:
    """Load a configured layout once at startup; invalid files fail startup."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.layout = load_layout(layout_path)
        app.state.cable_route_service = CableRouteService(app.state.layout)
        yield

    app = FastAPI(title="RackRoute API", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(FRONTEND_PATH / "index.html")

    @app.exception_handler(RackNotFoundError)
    async def rack_not_found(request: Request, error: RackNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(NoRouteAvailableError)
    async def no_route(request: Request, error: NoRouteAvailableError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(InvalidSafetyMarginError)
    async def invalid_margin(request: Request, error: InvalidSafetyMarginError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        # Exclude raw inputs/context: they can contain non-JSON values such as NaN.
        details = [{"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                   for item in error.errors()]
        return JSONResponse(status_code=422, content={"detail": details})

    return app


app = create_app()
