import smtplib
import uuid
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_password_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.candidate import Candidate
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)
bearer_scheme = HTTPBearer()

# Strict in production, permissive in dev/test to avoid test interference
_LOGIN_LIMIT = "5/minute" if settings.ENVIRONMENT == "production" else "200/minute"
_REGISTER_LIMIT = "3/minute" if settings.ENVIRONMENT == "production" else "200/minute"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_REGISTER_LIMIT)
async def register(request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    try:
        await db.flush()
        # Auto-create Candidate record for new user
        candidate = Candidate(user_id=user.id)
        db.add(candidate)
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None

    logger.info("user_registered", user_id=str(user.id))
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_LOGIN_LIMIT)
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    logger.info("user_login", user_id=str(user.id))
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError("not a refresh token")
        user_id = uuid.UUID(data["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from None

    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


def _send_reset_email(to_email: str, reset_url: str) -> None:
    if not settings.SMTP_HOST:
        logger.info("smtp_not_configured_reset_url", url=reset_url)
        return
    msg = MIMEText(
        f"Usá este link para resetear tu contraseña (expira en 15 minutos):\n\n{reset_url}\n\n"
        "Si no lo pediste vos, ignorá este email.",
        "plain",
        "utf-8",
    )
    msg["Subject"] = "Resetear contraseña — LinkedIn Intelligence"
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as s:
            if settings.SMTP_USER:
                s.starttls()
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
    except Exception as exc:
        logger.warning("smtp_send_failed", error=str(exc))


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    # Always return 204 to avoid leaking which emails are registered
    if not user:
        return
    token = create_password_reset_token(payload.email)
    if settings.FRONTEND_URL:
        frontend_url = settings.FRONTEND_URL.rstrip("/")
    elif settings.CORS_ORIGINS:
        frontend_url = settings.CORS_ORIGINS.split(",")[0].strip().rstrip("/")
    else:
        frontend_url = ""
    reset_url = f"{frontend_url}/reset-password?token={token}"
    _send_reset_email(payload.email, reset_url)
    logger.info("password_reset_requested", user_id=str(user.id))


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        email = decode_password_reset_token(payload.token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    result = await db.execute(select(User).where(User.email == email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(payload.password)
    await db.commit()
    logger.info("password_reset_completed", user_id=str(user.id))
