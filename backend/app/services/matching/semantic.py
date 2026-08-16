"""Semantic matching via dense embeddings and cosine similarity.

All scoring is in-memory — no pgvector or DB required. pgvector columns (on
Job and CandidateProfile models) are available for future batch ANN search.

Returns None gracefully when NullEmbeddingProvider is active (no API key set).
Hybrid formula caller must handle the None case.
"""
import math
from dataclasses import dataclass, field

from app.services.ai.embeddings import EmbeddingProvider, NullEmbeddingProvider
from app.services.claim_validator import EvidenceRecord


@dataclass
class SemanticResult:
    score: float                           # 0.0–1.0 (rescaled cosine similarity)
    top_evidence: list[str] = field(default_factory=list)  # ranked evidence snippets
    profile_text: str = ""
    job_text: str = ""


# ── Text builders ─────────────────────────────────────────────────────────────

def build_profile_text(
    profile_skills: list[dict],
    profile_experience: list[dict] | None,
    profile_projects: list[dict] | None,
) -> str:
    parts: list[str] = []
    for s in profile_skills or []:
        name = s.get("canonical_name") or s.get("name") or ""
        if name:
            parts.append(name)
    for exp in profile_experience or []:
        role = exp.get("role", "")
        company = exp.get("company", "")
        if role or company:
            parts.append(f"{role} at {company}".strip(" at"))
        parts.extend(exp.get("bullets", []))
        parts.extend(exp.get("technologies", []))
    for proj in profile_projects or []:
        if proj.get("description"):
            parts.append(proj["description"])
        parts.extend(proj.get("tech", []))
    return " ".join(filter(None, parts))


def build_job_text(
    job_title: str | None,
    job_company: str | None,
    job_description: str | None,
    requirements: list,
) -> str:
    parts: list[str] = []
    if job_title:
        parts.append(job_title)
    if job_company:
        parts.append(job_company)
    if job_description:
        parts.append(job_description)
    for req in requirements or []:
        desc = (
            req.description if hasattr(req, "description") else req.get("description", "")
        )
        if desc:
            parts.append(desc)
    return " ".join(filter(None, parts))


# ── Math ──────────────────────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _rescale(similarity: float) -> float:
    """Map cosine similarity [-1, 1] → [0, 1]."""
    return (similarity + 1.0) / 2.0


# ── Main entry point ──────────────────────────────────────────────────────────

async def compute_semantic(
    *,
    profile_skills: list[dict],
    profile_experience: list[dict] | None,
    profile_projects: list[dict] | None,
    job_title: str | None,
    job_company: str | None = None,
    job_description: str | None,
    requirements: list,
    evidence_records: list[EvidenceRecord] | None = None,
    embedding_provider: EmbeddingProvider,
    top_k: int = 3,
) -> SemanticResult | None:
    """Compute semantic similarity between candidate profile and job description.

    Returns None when embedding_provider is NullEmbeddingProvider (no API key).
    """
    if isinstance(embedding_provider, NullEmbeddingProvider):
        return None

    profile_text = build_profile_text(profile_skills, profile_experience, profile_projects)
    job_text = build_job_text(job_title, job_company, job_description, requirements)

    if not profile_text.strip() or not job_text.strip():
        return None

    evidence_texts = [rec.content for rec in (evidence_records or []) if rec.content]
    all_texts = [profile_text, job_text, *evidence_texts]

    embeddings = await embedding_provider.embed(all_texts)
    if not embeddings or len(embeddings) < 2:
        return None

    profile_emb = embeddings[0]
    job_emb = embeddings[1]
    evidence_embs = embeddings[2:]

    score = _rescale(_cosine(profile_emb, job_emb))

    top_evidence: list[str] = []
    if evidence_texts and evidence_embs:
        ranked = sorted(
            zip(evidence_texts, evidence_embs, strict=True),
            key=lambda pair: _cosine(pair[1], job_emb),
            reverse=True,
        )
        top_evidence = [text for text, _ in ranked[:top_k]]

    return SemanticResult(
        score=round(score, 4),
        top_evidence=top_evidence,
        profile_text=profile_text,
        job_text=job_text,
    )


# ── Hybrid formula helpers ────────────────────────────────────────────────────

#: Weights when semantic score IS available
HYBRID_WEIGHTS_SEMANTIC = {"det": 0.45, "llm": 0.35, "sem": 0.20}

#: Weights when semantic score is NOT available (preserves existing behaviour)
HYBRID_WEIGHTS_FALLBACK = {"det": 0.60, "llm": 0.40}


def compute_hybrid_score(
    det_score: float,
    llm_score: float,
    semantic_result: SemanticResult | None,
) -> float:
    """Compute three-way hybrid score. Falls back to det+llm when semantic unavailable."""
    if semantic_result is not None:
        w = HYBRID_WEIGHTS_SEMANTIC
        return round(
            det_score * w["det"] + llm_score * w["llm"] + semantic_result.score * w["sem"],
            3,
        )
    w = HYBRID_WEIGHTS_FALLBACK
    return round(det_score * w["det"] + llm_score * w["llm"], 3)
