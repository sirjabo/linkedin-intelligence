import os
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.routes import cv, chat, auth, candidates, jobs, match, applications

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", environment=settings.ENVIRONMENT)
    yield
    logger.info("shutdown")


app = FastAPI(title="LinkedIn Intelligence API", version="2.0.0", lifespan=lifespan)

_cors_origins_env = os.environ.get("CORS_ORIGINS", "")
_default_origins = ["http://localhost:3000", "http://frontend:3000"]
cors_origins = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# v1 legacy routes (CV coaching chatbot — kept during migration)
app.include_router(cv.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")

# v2 routes
app.include_router(auth.router, prefix="/api/v2")
app.include_router(candidates.router, prefix="/api/v2")
app.include_router(jobs.router, prefix="/api/v2")
app.include_router(match.router, prefix="/api/v2")
app.include_router(applications.router, prefix="/api/v2")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
