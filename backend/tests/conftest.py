"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

# Ensure settings can load before app imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-16-chars")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://linkedin_user:changeme@localhost:5432/linkedin_intelligence",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "false")


@pytest.fixture
def sample_cv_text() -> str:
    return (
        "Soy Analytics Engineer con 5 años de experiencia en Python, SQL, pandas, "
        "n8n y Power BI. Trabajé en BBVA desarrollando pipelines de datos y "
        "automatizaciones. Tengo experiencia con PostgreSQL, Git y APIs REST."
    )
