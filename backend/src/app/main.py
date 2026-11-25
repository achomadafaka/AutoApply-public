from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .migrations import init_db
from .settings import get_settings
from .routes import (
    health,
    jobs,
    applications,
    materials,
    automation,
    settings,
    selectors,
    ai,
    artifacts,
    profile,
)


def create_app() -> FastAPI:
    config = get_settings()
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db(Path(config.database_path))
        yield

    app = FastAPI(title="AutoApply API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def restrict_browser_writes(request: Request, call_next):
        origin = request.headers.get("origin")
        if (request.method not in {"GET", "HEAD", "OPTIONS"}
                and origin is not None and origin not in config.cors_origins):
            return JSONResponse(status_code=403, content={"error": {
                "code": "untrusted_origin", "message": "Origin not allowed", "details": None
            }})
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    app.include_router(health.router)
    app.include_router(jobs.router, prefix=config.api_prefix)
    app.include_router(applications.router, prefix=config.api_prefix)
    app.include_router(materials.router, prefix=config.api_prefix)
    app.include_router(automation.router, prefix=config.api_prefix)
    app.include_router(settings.router, prefix=config.api_prefix)
    app.include_router(selectors.router, prefix=config.api_prefix)
    app.include_router(ai.router, prefix=config.api_prefix)
    app.include_router(artifacts.router, prefix=config.api_prefix)
    app.include_router(profile.router, prefix=config.api_prefix)

    def _error_payload(code: str, message: str, details=None):
        return {"error": {"code": code, "message": message, "details": details}}

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, str):
            payload = _error_payload("http_error", detail)
        else:
            payload = _error_payload("http_error", "Request failed", detail)
        return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_payload("validation_error", "Validation error", jsonable_encoder(exc.errors(), custom_encoder={Exception: str})),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_error_payload("internal_error", "Internal server error"),
        )

    return app


app = create_app()
