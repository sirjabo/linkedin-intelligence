"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/v2/auth/register", json={
        "email": "alice@example.com",
        "password": "Secure1234",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "bob@example.com", "password": "Secure1234"}
    await client.post("/api/v2/auth/register", json=payload)
    resp = await client.post("/api/v2/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    resp = await client.post("/api/v2/auth/register", json={
        "email": "weak@example.com",
        "password": "short",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/api/v2/auth/register", json={
        "email": "carol@example.com",
        "password": "Secure1234",
    })
    resp = await client.post("/api/v2/auth/login", json={
        "email": "carol@example.com",
        "password": "Secure1234",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v2/auth/register", json={
        "email": "dave@example.com",
        "password": "Secure1234",
    })
    resp = await client.post("/api/v2/auth/login", json={
        "email": "dave@example.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_without_token(client: AsyncClient):
    resp = await client.get("/api/v2/candidates/me")
    assert resp.status_code == 403  # HTTPBearer returns 403 when no token


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token(client: AsyncClient):
    resp = await client.get(
        "/api/v2/candidates/me",
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token(client: AsyncClient):
    reg = await client.post("/api/v2/auth/register", json={
        "email": "eve@example.com",
        "password": "Secure1234",
    })
    token = reg.json()["access_token"]
    resp = await client.get(
        "/api/v2/candidates/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Should be 200, not 401 — the candidate was auto-created on register
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    reg = await client.post("/api/v2/auth/register", json={
        "email": "frank@example.com",
        "password": "Secure1234",
    })
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/api/v2/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
