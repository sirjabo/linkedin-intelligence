"""Tests for semantic matching — embeddings, cosine scoring, hybrid formula.

All tests are unit-level (no DB, no API calls). MockEmbeddingProvider provides
deterministic fake embeddings so tests are reproducible without OPENAI_API_KEY.
"""
import math

from app.services.ai.embeddings import (
    MockEmbeddingProvider,
    NullEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.services.claim_validator import EvidenceRecord
from app.services.matching.semantic import (
    SemanticResult,
    _cosine,
    _rescale,
    build_job_text,
    build_profile_text,
    compute_hybrid_score,
    compute_semantic,
)

MOCK = MockEmbeddingProvider(dim=8)
NULL = NullEmbeddingProvider()

_PROFILE_SKILLS = [
    {"canonical_name": "Python"},
    {"canonical_name": "FastAPI"},
    {"canonical_name": "PostgreSQL"},
]
_PROFILE_EXPERIENCE = [
    {
        "role": "Backend Engineer",
        "company": "Acme",
        "bullets": ["Built REST APIs", "Led team of 3"],
        "technologies": ["Python", "Docker"],
    }
]
_PROFILE_PROJECTS = [
    {"description": "Open-source CLI tool for data processing", "tech": ["Python"]}
]
_REQUIREMENTS = [
    type("R", (), {"description": "Python backend experience required"})(),
    type("R", (), {"description": "Experience with SQL databases"})(),
]
_EVIDENCE = [
    EvidenceRecord(source_type="experience", content="Built REST APIs with FastAPI and Python"),
    EvidenceRecord(source_type="skill", content="PostgreSQL database design and query optimisation"),
    EvidenceRecord(source_type="project", content="Open-source data processing CLI"),
]


# ── NullEmbeddingProvider ─────────────────────────────────────────────────────

def test_null_provider_dim_is_zero():
    assert NULL.dim == 0


async def test_null_provider_embed_returns_none():
    result = await NULL.embed(["hello"])
    assert result is None


def test_null_provider_is_embedding_provider_protocol():
    from app.services.ai.embeddings import EmbeddingProvider
    assert isinstance(NULL, EmbeddingProvider)


# ── MockEmbeddingProvider ─────────────────────────────────────────────────────

def test_mock_provider_dim():
    assert MOCK.dim == 8


async def test_mock_provider_returns_unit_vectors():
    vectors = await MOCK.embed(["test text"])
    assert vectors is not None
    assert len(vectors) == 1
    norm = math.sqrt(sum(v * v for v in vectors[0]))
    assert abs(norm - 1.0) < 1e-6


async def test_mock_provider_deterministic():
    v1 = await MOCK.embed(["same text"])
    v2 = await MOCK.embed(["same text"])
    assert v1 == v2


async def test_mock_provider_different_texts_produce_different_vectors():
    vecs = await MOCK.embed(["text one", "text two"])
    assert vecs is not None
    assert vecs[0] != vecs[1]


async def test_mock_provider_empty_input_returns_empty():
    vecs = await MOCK.embed([])
    assert vecs == []


# ── get_embedding_provider ────────────────────────────────────────────────────

def test_get_embedding_provider_returns_null_without_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENAI_API_KEY", "")
    from app.services.ai import embeddings as emb_mod
    emb_mod._default_provider = None
    provider = emb_mod.get_embedding_provider()
    assert isinstance(provider, NullEmbeddingProvider)
    emb_mod._default_provider = None


def test_get_embedding_provider_returns_openai_with_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENAI_API_KEY", "sk-test-key")
    from app.services.ai import embeddings as emb_mod
    emb_mod._default_provider = None
    provider = emb_mod.get_embedding_provider()
    assert isinstance(provider, OpenAIEmbeddingProvider)
    emb_mod._default_provider = None


# ── Math helpers ──────────────────────────────────────────────────────────────

def test_cosine_identical_vectors_is_one():
    v = [1.0, 0.0, 0.0]
    assert abs(_cosine(v, v) - 1.0) < 1e-9


def test_cosine_orthogonal_vectors_is_zero():
    assert abs(_cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_opposite_vectors_is_minus_one():
    v = [1.0, 0.0, 0.0]
    neg = [-1.0, 0.0, 0.0]
    assert abs(_cosine(v, neg) - (-1.0)) < 1e-9


def test_cosine_zero_vector_returns_zero():
    assert _cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_rescale_maps_neg1_to_0():
    assert abs(_rescale(-1.0)) < 1e-9


def test_rescale_maps_0_to_half():
    assert abs(_rescale(0.0) - 0.5) < 1e-9


def test_rescale_maps_1_to_1():
    assert abs(_rescale(1.0) - 1.0) < 1e-9


# ── Text builders ─────────────────────────────────────────────────────────────

def test_build_profile_text_includes_skills():
    text = build_profile_text(_PROFILE_SKILLS, None, None)
    assert "Python" in text
    assert "FastAPI" in text


def test_build_profile_text_includes_experience_bullets():
    text = build_profile_text([], _PROFILE_EXPERIENCE, None)
    assert "Built REST APIs" in text


def test_build_profile_text_includes_project_description():
    text = build_profile_text([], None, _PROFILE_PROJECTS)
    assert "data processing" in text


def test_build_profile_text_empty_inputs_returns_empty():
    text = build_profile_text([], None, None)
    assert text == ""


def test_build_job_text_includes_title_and_requirements():
    text = build_job_text("Senior Engineer", "Acme", None, _REQUIREMENTS)
    assert "Senior Engineer" in text
    assert "Python backend" in text


def test_build_job_text_none_description_is_ok():
    text = build_job_text("Engineer", None, None, [])
    assert text == "Engineer"


# ── compute_semantic ──────────────────────────────────────────────────────────

async def test_compute_semantic_returns_none_for_null_provider():
    result = await compute_semantic(
        profile_skills=_PROFILE_SKILLS,
        profile_experience=_PROFILE_EXPERIENCE,
        profile_projects=_PROFILE_PROJECTS,
        job_title="Backend Engineer",
        job_company="Acme",
        job_description="Python-heavy role",
        requirements=_REQUIREMENTS,
        evidence_records=_EVIDENCE,
        embedding_provider=NULL,
    )
    assert result is None


async def test_compute_semantic_returns_result_with_mock_provider():
    result = await compute_semantic(
        profile_skills=_PROFILE_SKILLS,
        profile_experience=_PROFILE_EXPERIENCE,
        profile_projects=_PROFILE_PROJECTS,
        job_title="Backend Engineer",
        job_company="Acme",
        job_description="Python-heavy role",
        requirements=_REQUIREMENTS,
        evidence_records=_EVIDENCE,
        embedding_provider=MOCK,
    )
    assert isinstance(result, SemanticResult)


async def test_compute_semantic_score_in_range():
    result = await compute_semantic(
        profile_skills=_PROFILE_SKILLS,
        profile_experience=_PROFILE_EXPERIENCE,
        profile_projects=_PROFILE_PROJECTS,
        job_title="Backend Engineer",
        job_company="Acme",
        job_description="Python FastAPI PostgreSQL backend",
        requirements=_REQUIREMENTS,
        embedding_provider=MOCK,
    )
    assert result is not None
    assert 0.0 <= result.score <= 1.0


async def test_compute_semantic_top_evidence_populated():
    result = await compute_semantic(
        profile_skills=_PROFILE_SKILLS,
        profile_experience=_PROFILE_EXPERIENCE,
        profile_projects=_PROFILE_PROJECTS,
        job_title="Python Backend Engineer",
        job_company=None,
        job_description=None,
        requirements=_REQUIREMENTS,
        evidence_records=_EVIDENCE,
        embedding_provider=MOCK,
        top_k=2,
    )
    assert result is not None
    assert len(result.top_evidence) <= 2
    assert all(isinstance(e, str) for e in result.top_evidence)


async def test_compute_semantic_top_evidence_capped_at_k():
    result = await compute_semantic(
        profile_skills=_PROFILE_SKILLS,
        profile_experience=_PROFILE_EXPERIENCE,
        profile_projects=_PROFILE_PROJECTS,
        job_title="Engineer",
        job_company=None,
        job_description="backend",
        requirements=[],
        evidence_records=_EVIDENCE,
        embedding_provider=MOCK,
        top_k=2,
    )
    assert result is not None
    assert len(result.top_evidence) <= 2


async def test_compute_semantic_empty_profile_returns_none():
    result = await compute_semantic(
        profile_skills=[],
        profile_experience=None,
        profile_projects=None,
        job_title="Engineer",
        job_company=None,
        job_description="backend",
        requirements=[],
        embedding_provider=MOCK,
    )
    assert result is None


async def test_compute_semantic_empty_job_returns_none():
    result = await compute_semantic(
        profile_skills=_PROFILE_SKILLS,
        profile_experience=_PROFILE_EXPERIENCE,
        profile_projects=_PROFILE_PROJECTS,
        job_title=None,
        job_company=None,
        job_description=None,
        requirements=[],
        embedding_provider=MOCK,
    )
    assert result is None


# ── compute_hybrid_score ──────────────────────────────────────────────────────

def test_hybrid_without_semantic_uses_det_llm_60_40():
    score = compute_hybrid_score(det_score=0.80, llm_score=0.60, semantic_result=None)
    expected = round(0.80 * 0.60 + 0.60 * 0.40, 3)
    assert abs(score - expected) < 1e-6


def test_hybrid_with_semantic_uses_three_way_weights():
    sem = SemanticResult(score=0.70, top_evidence=[])
    score = compute_hybrid_score(det_score=0.80, llm_score=0.60, semantic_result=sem)
    expected = round(0.80 * 0.45 + 0.60 * 0.35 + 0.70 * 0.20, 3)
    assert abs(score - expected) < 1e-6


def test_hybrid_score_in_range():
    sem = SemanticResult(score=0.50, top_evidence=[])
    score = compute_hybrid_score(0.70, 0.65, sem)
    assert 0.0 <= score <= 1.0


def test_hybrid_without_semantic_score_in_range():
    score = compute_hybrid_score(0.70, 0.65, None)
    assert 0.0 <= score <= 1.0


def test_hybrid_fallback_preserves_existing_weight_contract():
    score = compute_hybrid_score(1.0, 0.0, None)
    assert abs(score - 0.60) < 1e-6

    score2 = compute_hybrid_score(0.0, 1.0, None)
    assert abs(score2 - 0.40) < 1e-6


# ── EvidenceRecord embedding field ────────────────────────────────────────────

def test_evidence_record_embedding_defaults_none():
    rec = EvidenceRecord(source_type="skill", content="Python")
    assert rec.embedding is None


def test_evidence_record_accepts_embedding():
    vec = [0.1, 0.2, 0.3]
    rec = EvidenceRecord(source_type="skill", content="Python", embedding=vec)
    assert rec.embedding == vec


def test_evidence_record_backward_compat_aliases():
    rec = EvidenceRecord(source_type="experience", content="Led team", skills_mentioned=["leadership"])
    assert rec.claim == "Led team"
    assert "leadership" in rec.source_text
