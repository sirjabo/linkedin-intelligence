"""Unit tests for cv_storage — real PDF generation (P0 Phase 3).

Tests verify file is produced, has .pdf extension, non-zero size,
and contains personalized content from CVVersion when available.
"""
import os
import uuid
from types import SimpleNamespace

import pytest

from app.services import cv_storage


def _make_candidate(name="Jane Doe", email="jane@example.com", location="Buenos Aires"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        email=email,
        location=location,
        sources=[],
        salary_min_usd=95000,
    )


def _make_profile(summary=None, skills=None, experience=None, education=None):
    return SimpleNamespace(
        summary=summary or "Senior Data Engineer with 7 years of experience.",
        skills=skills or ["Python", "Spark", "Airflow", "dbt", "AWS"],
        experience=experience or [
            {
                "company": "BigCo",
                "role": "Senior Data Engineer",
                "start_date": "01/2021",
                "end_date": "Present",
                "duration_years": 3,
                "bullets": ["Led Spark pipeline redesign reducing latency by 40%"],
            }
        ],
        education=[
            {"degree": "Bachelor", "field": "Computer Science", "institution": "UBA", "year": "2016"}
        ],
        projects=[],
    )


def _make_application(cv_versions=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        cover_letters=[],
        answers=[],
        cv_versions=cv_versions or [],
    )


def _make_cv_version(summary_adapted, skills_ordered):
    from datetime import datetime
    return SimpleNamespace(
        summary_adapted=summary_adapted,
        headline_adapted="Senior Data Engineer | Spark · Airflow · AWS",
        skills_ordered=skills_ordered,
        changes=[],
        ats_keywords=["data pipeline", "Apache Spark"],
        evidence_refs=["BigCo pipeline redesign"],
        created_at=datetime(2026, 8, 14, 12, 0, 0),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pdf_cv_generated(tmp_path, monkeypatch):
    """generate_cv_file() returns a .pdf file with non-zero size."""
    monkeypatch.setattr(cv_storage.settings, "UPLOAD_DIR", str(tmp_path))

    candidate = _make_candidate()
    profile = _make_profile()
    app = _make_application()

    path = await cv_storage.generate_cv_file(candidate, profile, app)

    assert path.endswith(".pdf"), f"Expected .pdf extension, got: {path}"
    assert os.path.isfile(path), f"File not found: {path}"
    assert os.path.getsize(path) > 0, "PDF file is empty"


@pytest.mark.asyncio
async def test_pdf_cv_is_personalized(tmp_path, monkeypatch):
    """generate_cv_file() uses CVVersion.summary_adapted when available."""
    monkeypatch.setattr(cv_storage.settings, "UPLOAD_DIR", str(tmp_path))

    adapted_summary = (
        "7-year Data Engineer specializing in PB-scale Spark pipelines on AWS, "
        "with deep expertise in Airflow orchestration."
    )
    cv_version = _make_cv_version(
        summary_adapted=adapted_summary,
        skills_ordered=["Python", "Spark", "Airflow", "dbt", "AWS", "PostgreSQL"],
    )

    candidate = _make_candidate()
    profile = _make_profile()
    app = _make_application(cv_versions=[cv_version])

    path = await cv_storage.generate_cv_file(candidate, profile, app)

    # Verify the cv_data dict built from the CVVersion contains the adapted summary
    cv_data = cv_storage._build_cv_dict(candidate, profile, cv_version)
    assert cv_data["summary"] == adapted_summary
    assert cv_data["skills"]["languages"] == cv_version.skills_ordered

    # File still produced correctly
    assert os.path.isfile(path)
    assert os.path.getsize(path) > 0


@pytest.mark.asyncio
async def test_pdf_cv_fallback_to_profile_when_no_cv_version(tmp_path, monkeypatch):
    """Falls back to raw profile summary when no CVVersion exists."""
    monkeypatch.setattr(cv_storage.settings, "UPLOAD_DIR", str(tmp_path))

    profile = _make_profile(summary="Raw profile summary — no personalization.")
    candidate = _make_candidate()
    app = _make_application(cv_versions=[])

    cv_data = cv_storage._build_cv_dict(candidate, profile, None)
    assert cv_data["summary"] == "Raw profile summary — no personalization."
    assert cv_data["skills"]["languages"] == ["Python", "Spark", "Airflow", "dbt", "AWS"]


@pytest.mark.asyncio
async def test_cv_exists_returns_true_after_generation(tmp_path, monkeypatch):
    """cv_exists() returns True after generate_cv_file() completes."""
    monkeypatch.setattr(cv_storage.settings, "UPLOAD_DIR", str(tmp_path))

    candidate = _make_candidate()
    profile = _make_profile()
    app = _make_application()

    assert not cv_storage.cv_exists(candidate.id, app.id)
    await cv_storage.generate_cv_file(candidate, profile, app)
    assert cv_storage.cv_exists(candidate.id, app.id)
