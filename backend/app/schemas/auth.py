"""Auth request/response schemas — Sprint 002."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    target_role: Literal[
        "ai_engineer", "data_engineer", "analytics_engineer", "ml_engineer"
    ] = "ai_engineer"


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_at: str


class TokenPayload(BaseModel):
    sub: str
    plan: str = "free"
    exp: int
