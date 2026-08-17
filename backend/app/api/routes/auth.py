"""POST /auth/register and /auth/login — JWT auth."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.middleware.rate_limit import limiter
from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse

router = APIRouter(tags=["auth"])
logger = get_logger(__name__)


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=uuid4(),
        email=body.email,
        name=body.name,
        hashed_password=hash_password(body.password),
        target_role=body.target_role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token, _ = create_access_token(subject=str(user.id), plan=user.plan)
    logger.info("user_registered", user_id=str(user.id), email=user.email)

    return RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        token=token,
    )


@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, expires_at = create_access_token(subject=str(user.id), plan=user.plan)
    logger.info("user_logged_in", user_id=str(user.id))

    return LoginResponse(
        token=token,
        expires_at=expires_at.isoformat(),
    )
