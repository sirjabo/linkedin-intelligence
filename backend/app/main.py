"""LinkedIn Intelligence — FastAPI application."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import Response

from app.api.middleware.rate_limit import limiter
from app.api.routes import analyze, auth, chat, cv, health, market
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("app_starting", environment=settings.ENVIRONMENT, version=settings.APP_VERSION)
    try:
        await init_db()
    except Exception as exc:
        logger.warning("init_db_skipped", error=str(exc))
    yield
    logger.info("app_stopping")


app = FastAPI(
    title="LinkedIn Intelligence API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RateLimitExceeded)
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

_cors_origins_env = os.environ.get("CORS_ORIGINS", "")
cors_origins = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else list(settings.CORS_ORIGINS)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(cv.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", path=str(request.url.path), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Error interno del servidor",
                "docs_url": "https://docs.linkedin-intelligence.com/errors/INTERNAL_ERROR",
            }
        },
    )
