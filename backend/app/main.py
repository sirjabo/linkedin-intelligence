import os
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import structlog

from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import configure_logging, get_logger
from app.api.routes import cv, chat, auth, candidates, jobs, match, applications, recommendations, interview, forms, agent

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.SECRET_KEY == "dev-secret-change-in-production" and settings.ENVIRONMENT != "development":
        logger.warning("insecure_secret_key", message="SECRET_KEY is still the default value — set a strong key in production")
    logger.info("startup", environment=settings.ENVIRONMENT)
    yield
    logger.info("shutdown")


app = FastAPI(title="LinkedIn Intelligence API", version="2.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT != "development":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


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
app.include_router(recommendations.router, prefix="/api/v2")
app.include_router(interview.router, prefix="/api/v2")
app.include_router(forms.router, prefix="/api/v2")
app.include_router(agent.router, prefix="/api/v2")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
