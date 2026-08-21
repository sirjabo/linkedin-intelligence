"""Sprint A — Real Personalized CV Engine acceptance tests.

Verifies:
1. CVChange schema completeness (bullet_index, reason, job_requirement, evidence_refs, confidence)
2. PersonalizedCV has experience_personalized and projects_personalized
3. PDF reconstruction uses projects_personalized descriptions
4. Differentiation score >= 0.60 across 3 CVs for a single candidate
5. Every CVChange references at least one evidence_ref (no invented claims)
"""
import os
import uuid
from datetime import UTC
from types import SimpleNamespace

import pytest

from app.services import cv_storage
from app.services.agents.cv_agent import (
    BulletChange,
    CVChange,
    ExperiencePersonalized,
    PersonalizedCV,
    ProjectPersonalized,
)
from app.services.ai_evaluation import (
    cv_changes_have_evidence,
    cv_differentiation_score,
    evaluate,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

CANDIDATE_PROFILE = {
    "name": "Ana García",
    "summary": "Data Engineer with 6 years building ETL pipelines and ML platforms.",
    "career_level": "Senior",
    "skills": ["Python", "Spark", "Airflow", "dbt", "AWS", "SQL", "Kafka", "Docker"],
    "experience": [
        {
            "company": "FinTech SA",
            "role": "Senior Data Engineer",
            "start_date": "01/2022",
            "end_date": "Present",
            "bullets": [
                (
                    "Designed real-time streaming pipeline ingesting 500k events/day"
                    " using Kafka and Spark Structured Streaming."
                ),
                "Reduced data warehouse query latency by 60% via dbt incremental models.",
                "Automated ML feature store refresh with Airflow DAGs, saving 15h/week.",
            ],
        },
        {
            "company": "Retail Corp",
            "role": "Data Engineer",
            "start_date": "06/2019",
            "end_date": "12/2021",
            "bullets": [
                "Built AWS Glue jobs to process 2TB daily e-commerce logs.",
                "Led migration from on-premise Hadoop to AWS EMR.",
            ],
        },
    ],
    "projects": [
        {
            "name": "OpenPipeline",
            "description": "Open-source Airflow DAG framework",
            "tech": ["Python", "Airflow"],
        },
        {
            "name": "MLPlatform",
            "description": "Internal ML feature store",
            "tech": ["Python", "Redis", "Postgres"],
        },
    ],
}

JD_AI_ENGINEER = {
    "title": "AI Engineer",
    "company": "AI Startup",
    "tech_stack": ["Python", "LangChain", "FastAPI", "PostgreSQL", "Redis"],
    "must_have": ["LLM integration", "API development", "Python"],
}

JD_DATA_ENGINEER = {
    "title": "Data Engineer",
    "company": "Scale Corp",
    "tech_stack": ["Spark", "Kafka", "AWS", "Airflow", "dbt"],
    "must_have": ["Kafka", "Spark Streaming", "AWS"],
}

JD_ML_ENGINEER = {
    "title": "ML Engineer",
    "company": "ML Co",
    "tech_stack": ["Python", "Docker", "Kubernetes", "MLflow", "Airflow"],
    "must_have": ["MLOps", "feature store", "pipeline automation"],
}


def _make_bullet_change(original: str, adapted: str, job_req: str) -> BulletChange:
    return BulletChange(
        original=original,
        adapted=adapted,
        reason=f"Emphasizes {job_req[:30]}",
        job_requirement=job_req,
        evidence_ref="FinTech SA — Senior Data Engineer",
        confidence=0.85,
    )


def _make_cv_for_jd(jd_key: str) -> PersonalizedCV:
    """Construct a mock PersonalizedCV with job-specific bullet adaptations."""
    if jd_key == "ai":
        bullets = [
            _make_bullet_change(
                "Designed real-time streaming pipeline ingesting 500k events/day"
                " using Kafka and Spark.",
                "Built data ingestion pipeline for LLM training datasets processing"
                " 500k records/day using Python.",
                "LLM integration",
            ),
            _make_bullet_change(
                "Automated ML feature store refresh with Airflow DAGs, saving 15h/week.",
                "Automated AI model serving pipeline with FastAPI and Airflow,"
                " enabling 99.9% uptime.",
                "API development",
            ),
        ]
        changes = [
            CVChange(
                section="summary",
                bullet_index=None,
                original=(
                    "Data Engineer with 6 years building ETL pipelines and ML platforms."
                ),
                adapted=(
                    "Data Engineer with LLM integration experience,"
                    " building AI-ready data pipelines."
                ),
                reason="Highlights AI/LLM relevance for the role",
                job_requirement="LLM integration",
                evidence_refs=["MLPlatform project — feature store"],
                confidence=0.85,
            )
        ]
        proj = [
            ProjectPersonalized(
                name="MLPlatform",
                description_original="Internal ML feature store",
                description_adapted=(
                    "Internal ML feature store powering LLM inference"
                    " with Redis caching and FastAPI serving."
                ),
                reason="Demonstrates LLM-adjacent infrastructure experience",
            )
        ]
    elif jd_key == "data":
        bullets = [
            _make_bullet_change(
                "Designed real-time streaming pipeline ingesting 500k events/day"
                " using Kafka and Spark.",
                "Architected Kafka + Spark Structured Streaming pipeline processing"
                " 500k events/day at sub-second latency.",
                "Kafka streaming",
            ),
            _make_bullet_change(
                "Reduced data warehouse query latency by 60% via dbt incremental models.",
                "Cut data warehouse query latency 60% through dbt incremental model"
                " optimization on AWS Redshift.",
                "dbt + AWS",
            ),
        ]
        changes = [
            CVChange(
                section="summary",
                bullet_index=None,
                original=(
                    "Data Engineer with 6 years building ETL pipelines and ML platforms."
                ),
                adapted=(
                    "Senior Data Engineer specializing in Kafka streaming"
                    " and AWS-scale Spark pipelines."
                ),
                reason="Matches streaming and cloud focus of the role",
                job_requirement="Kafka, Spark Streaming, AWS",
                evidence_refs=["FinTech SA — real-time streaming pipeline"],
                confidence=0.9,
            )
        ]
        proj = [
            ProjectPersonalized(
                name="OpenPipeline",
                description_original="Open-source Airflow DAG framework",
                description_adapted=(
                    "Open-source Airflow DAG framework for orchestrating"
                    " large-scale Spark and Kafka jobs."
                ),
                reason="Demonstrates orchestration experience central to the data engineering role",
            )
        ]
    else:  # ml
        bullets = [
            _make_bullet_change(
                "Automated ML feature store refresh with Airflow DAGs, saving 15h/week.",
                "Built MLOps pipeline for automated feature store refresh and model"
                " retraining via Airflow, cutting ops time by 15h/week.",
                "MLOps pipeline automation",
            ),
            _make_bullet_change(
                "Designed real-time streaming pipeline ingesting 500k events/day"
                " using Kafka and Spark.",
                "Delivered real-time feature ingestion pipeline for ML models"
                " using Kafka, containerized with Docker.",
                "feature store + Docker",
            ),
        ]
        changes = [
            CVChange(
                section="summary",
                bullet_index=None,
                original=(
                    "Data Engineer with 6 years building ETL pipelines and ML platforms."
                ),
                adapted=(
                    "ML Engineer with 6 years building MLOps platforms,"
                    " feature stores, and model-serving infrastructure."
                ),
                reason="Reframes experience around ML engineering and MLOps",
                job_requirement="MLOps, feature store",
                evidence_refs=["MLPlatform project", "FinTech SA — feature store refresh"],
                confidence=0.82,
            )
        ]
        proj = [
            ProjectPersonalized(
                name="MLPlatform",
                description_original="Internal ML feature store",
                description_adapted=(
                    "Internal ML feature store with automated model retraining pipelines,"
                    " deployed via Docker and MLflow."
                ),
                reason=(
                    "Directly demonstrates MLOps and feature store experience"
                    " required for the role"
                ),
            )
        ]

    return PersonalizedCV(
        summary_adapted=changes[0].adapted,
        headline_adapted=f"Senior Engineer for {jd_key.upper()} Role",
        skills_ordered=["Python", "Airflow", "Spark"],
        changes=changes,
        experience_personalized=[
            ExperiencePersonalized(
                company="FinTech SA",
                title="Senior Data Engineer",
                bullets_original=[b.original for b in bullets],
                bullets_adapted=bullets,
            )
        ],
        projects_personalized=proj,
    )


# ── Schema tests ───────────────────────────────────────────────────────────────

class TestCVChangeSchema:
    def test_has_all_sprint_a_fields(self):
        change = CVChange(
            section="experience",
            bullet_index=1,
            original="Built pipelines.",
            adapted="Built AWS Spark pipelines processing 500k events/day.",
            reason="Highlights cloud scale relevant to the role",
            job_requirement="AWS Spark streaming",
            evidence_refs=["FinTech SA — pipeline project"],
            confidence=0.87,
        )
        assert change.section == "experience"
        assert change.bullet_index == 1
        assert change.original == "Built pipelines."
        assert change.adapted is not None
        assert change.reason != ""
        assert change.job_requirement != ""
        assert len(change.evidence_refs) >= 1
        assert 0.0 <= change.confidence <= 1.0

    def test_backward_compat_evidence_ref_property(self):
        change = CVChange(
            section="summary", original="x", adapted="y",
            reason="test", evidence_refs=["ref1", "ref2"],
        )
        assert change.evidence_ref == "ref1"

    def test_backward_compat_rationale_property(self):
        change = CVChange(section="summary", original="x", adapted="y", reason="my reason")
        assert change.rationale == "my reason"

    def test_evidence_ref_none_when_empty_list(self):
        change = CVChange(section="skills", original="x", adapted="y", reason="r")
        assert change.evidence_ref is None

    def test_bullet_index_optional(self):
        change = CVChange(section="summary", original="x", adapted="y", reason="r")
        assert change.bullet_index is None

    def test_confidence_bounds(self):
        with pytest.raises(Exception, match="confidence"):
            CVChange(
                section="summary", original="x", adapted="y", reason="r", confidence=1.5
            )


class TestPersonalizedCVSchema:
    def test_has_experience_personalized(self):
        cv = _make_cv_for_jd("data")
        assert len(cv.experience_personalized) >= 1
        exp = cv.experience_personalized[0]
        assert len(exp.bullets_adapted) >= 1

    def test_bullet_change_has_all_fields(self):
        cv = _make_cv_for_jd("ai")
        bc = cv.experience_personalized[0].bullets_adapted[0]
        assert bc.original != ""
        assert bc.adapted != ""
        assert bc.reason != ""
        assert bc.job_requirement != ""
        assert bc.confidence > 0.0

    def test_has_projects_personalized(self):
        cv = _make_cv_for_jd("ml")
        assert len(cv.projects_personalized) >= 1
        pp = cv.projects_personalized[0]
        assert pp.description_adapted != ""
        assert pp.reason != ""


# ── Differentiation tests ──────────────────────────────────────────────────────

class TestCVDifferentiation:
    def test_three_jd_cvs_differentiation_gte_60pct(self):
        cvs = [_make_cv_for_jd("ai"), _make_cv_for_jd("data"), _make_cv_for_jd("ml")]
        score = cv_differentiation_score(cvs)
        assert score >= 0.60, (
            f"Expected pairwise differentiation >= 60%, got {score:.0%}. "
            "CVs for different JDs must have materially different bullets."
        )

    def test_identical_cvs_have_zero_differentiation(self):
        cv = _make_cv_for_jd("data")
        score = cv_differentiation_score([cv, cv])
        assert score == 0.0

    def test_single_cv_returns_one(self):
        cv = _make_cv_for_jd("ai")
        assert cv_differentiation_score([cv]) == 1.0

    def test_empty_list_returns_one(self):
        assert cv_differentiation_score([]) == 1.0


# ── Evidence / factuality tests ────────────────────────────────────────────────

class TestEvidenceRefs:
    def test_all_changes_have_evidence_refs(self):
        cv = _make_cv_for_jd("data")
        criterion = cv_changes_have_evidence(cv)
        report = evaluate(cv, [criterion])
        assert report.passed, report.summary()

    def test_change_without_evidence_fails_criterion(self):
        cv = PersonalizedCV(
            changes=[
                CVChange(
                    section="summary", original="x", adapted="y",
                    reason="test", evidence_refs=[],
                )
            ]
        )
        criterion = cv_changes_have_evidence(cv)
        report = evaluate(cv, [criterion])
        assert not report.passed


# ── PDF reconstruction with projects_personalized ─────────────────────────────

class TestCVStorageProjectsPersonalized:
    def _make_candidate(self):
        return SimpleNamespace(
            id=uuid.uuid4(), name="Ana García",
            email="ana@example.com", location="Buenos Aires", sources=[],
        )

    def _make_profile(self):
        return SimpleNamespace(
            summary="Data Engineer with 6 years.",
            skills=["Python", "Spark"],
            experience=[{
                "company": "FinTech SA", "role": "Senior Data Engineer",
                "start_date": "01/2022", "end_date": "Present", "bullets": [],
            }],
            education=[],
            projects=[
                {"name": "MLPlatform", "description": "Original description", "tech": ["Python"]},
                {"name": "OpenPipeline", "description": "Original DAG framework", "tech": ["Airflow"]},
            ],
        )

    def _make_cv_version(self, projects_personalized: list | None = None):
        from datetime import datetime
        return SimpleNamespace(
            summary_adapted="Adapted summary",
            headline_adapted="Senior Data Engineer",
            skills_ordered=["Python", "Spark", "Airflow"],
            changes=[],
            ats_keywords=[],
            evidence_refs=[],
            experience_personalized=[],
            projects_personalized=projects_personalized,
            created_at=datetime(2026, 8, 16, 10, 0, 0, tzinfo=UTC),
        )

    def test_projects_personalized_replaces_description(self):
        cv_version = self._make_cv_version(
            projects_personalized=[{
                "name": "MLPlatform",
                "description_original": "Internal ML feature store",
                "description_adapted": "Personalized: ML feature store for LLM inference.",
                "reason": "Matches LLM role",
                "highlights_adapted": ["Sub-100ms latency", "Redis caching"],
            }]
        )
        cv_data = cv_storage._build_cv_dict(
            self._make_candidate(), self._make_profile(), cv_version
        )
        ml_proj = next(p for p in cv_data["projects"] if p["name"] == "MLPlatform")
        assert ml_proj["description"] == "Personalized: ML feature store for LLM inference."
        assert ml_proj["highlights"] == ["Sub-100ms latency", "Redis caching"]

    def test_non_personalized_project_uses_original(self):
        cv_version = self._make_cv_version(
            projects_personalized=[{
                "name": "MLPlatform",
                "description_adapted": "Personalized description",
                "reason": "r",
                "highlights_adapted": [],
            }]
        )
        cv_data = cv_storage._build_cv_dict(
            self._make_candidate(), self._make_profile(), cv_version
        )
        open_proj = next(p for p in cv_data["projects"] if p["name"] == "OpenPipeline")
        assert open_proj["description"] == "Original DAG framework"

    def test_no_cv_version_uses_raw_profile(self):
        cv_data = cv_storage._build_cv_dict(
            self._make_candidate(), self._make_profile(), None
        )
        ml_proj = next(p for p in cv_data["projects"] if p["name"] == "MLPlatform")
        assert ml_proj["description"] == "Original description"

    @pytest.mark.asyncio
    async def test_pdf_generated_with_projects_personalized(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cv_storage.settings, "UPLOAD_DIR", str(tmp_path))
        cv_version = self._make_cv_version(
            projects_personalized=[{
                "name": "MLPlatform",
                "description_adapted": "Adapted for AI role",
                "reason": "r",
                "highlights_adapted": [],
            }]
        )
        app = SimpleNamespace(
            id=uuid.uuid4(), candidate_id=uuid.uuid4(),
            cover_letters=[], answers=[], cv_versions=[cv_version],
        )
        path = await cv_storage.generate_cv_file(
            self._make_candidate(), self._make_profile(), app
        )
        assert path.endswith(".pdf")
        assert os.path.getsize(path) > 0
