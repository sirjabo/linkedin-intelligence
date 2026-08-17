"""ClaimValidator: verify generated text claims against candidate evidence records.

Deterministic, no LLM calls — uses keyword overlap and pattern matching.
Produces SUPPORTED / PLAUSIBLE / UNSUPPORTED / CONTRADICTED classifications.

EvidenceBuilder constructs evidence records from the candidate's profile so
the orchestrator can pass real data instead of an empty list.
"""
import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

VerificationStatus = Literal["SUPPORTED", "PLAUSIBLE", "UNSUPPORTED", "CONTRADICTED"]

# Patterns that signal a factual claim worth verifying
_CLAIM_PATTERNS = [
    re.compile(r"\d+\s*(%|years?|months?|\+|\bx\b)", re.IGNORECASE),
    re.compile(r"\$[\d,]+|\d+[kKmM]\b"),
    re.compile(r"\b(reduced|increased|improved|saved|built|led|managed|delivered|launched)\b", re.IGNORECASE),
]

# Patterns that suggest an inflated claim worth checking against the profile
_INFLATION_PATTERNS = [
    re.compile(r"\b(\d+)\+?\s*years?\s+of\s+(\w+)", re.IGNORECASE),  # "5 years of Python"
    re.compile(r"\b(\d+)\+?\s*years?\s+experience", re.IGNORECASE),   # "8 years experience"
]


@dataclass
class EvidenceRecord:
    """A single piece of evidence extracted from the candidate's profile."""
    source_type: str  # experience | education | skill | project | certification
    content: str      # free text describing the evidence
    skills_mentioned: list[str] = field(default_factory=list)
    embedding: list[float] | None = field(default=None, repr=False)
    # backward-compat aliases used by _classify_claim
    claim: str = field(init=False)
    source_text: str = field(init=False)

    def __post_init__(self) -> None:
        self.claim = self.content
        self.source_text = " ".join(self.skills_mentioned)


class EvidenceBuilder:
    """Construct EvidenceRecord list from a CandidateProfile and related data.

    Call build_from_profile() in the orchestrator to replace the empty list
    that was previously passed to validate_claims().
    """

    @staticmethod
    def build_from_profile(profile: object | None, extra_text: str = "") -> list[EvidenceRecord]:
        """Extract evidence records from a CandidateProfile ORM object.

        Handles both the ORM model (with .experience, .skills, .projects, .education)
        and plain dicts with the same keys.
        """
        records: list[EvidenceRecord] = []
        if profile is None:
            return records

        def _get(obj: object, key: str, default: object = None) -> object:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        # ── Experience ────────────────────────────────────────────────────────
        experience: list[Any] = _get(profile, "experience") or []  # type: ignore[assignment]
        for exp in experience:
            if not isinstance(exp, dict):
                continue
            title = exp.get("role") or exp.get("title", "")
            company = exp.get("company", "")
            bullets = exp.get("bullets") or []
            tech = exp.get("technologies") or exp.get("tech") or []
            duration = exp.get("duration_years") or exp.get("years", "")
            text = f"{title} at {company}. " + " ".join(bullets) + " " + " ".join(str(t) for t in tech)
            if duration:
                text += f" ({duration} years)"
            records.append(EvidenceRecord(
                source_type="experience",
                content=text.strip(),
                skills_mentioned=[str(t) for t in tech],
            ))

        # ── Skills ────────────────────────────────────────────────────────────
        skills_raw = _get(profile, "skills") or []
        if isinstance(skills_raw, list):
            for s in skills_raw:
                name = s.get("canonical_name", "") if isinstance(s, dict) else str(s)
                years = s.get("years_experience", "") if isinstance(s, dict) else ""
                evidence_text = f"Skill: {name}" + (f" ({years} years)" if years else "")
                records.append(EvidenceRecord(
                    source_type="skill",
                    content=evidence_text,
                    skills_mentioned=[name] if name else [],
                ))
        elif isinstance(skills_raw, dict):
            for category, skill_list in skills_raw.items():
                for s in (skill_list or []):
                    name = str(s)
                    records.append(EvidenceRecord(
                        source_type="skill",
                        content=f"Skill [{category}]: {name}",
                        skills_mentioned=[name],
                    ))

        # ── Projects ─────────────────────────────────────────────────────────
        projects: list[Any] = _get(profile, "projects") or []  # type: ignore[assignment]
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            name = proj.get("name", "")
            desc = proj.get("description", "")
            tech = proj.get("tech") or proj.get("technologies") or []
            highlights = proj.get("highlights") or []
            text = f"Project: {name}. {desc} " + " ".join(str(t) for t in tech) + " ".join(highlights)
            records.append(EvidenceRecord(
                source_type="project",
                content=text.strip(),
                skills_mentioned=[str(t) for t in tech],
            ))

        # ── Education ─────────────────────────────────────────────────────────
        education: list[Any] = _get(profile, "education") or []  # type: ignore[assignment]
        for edu in education:
            if not isinstance(edu, dict):
                continue
            degree = edu.get("degree", "")
            field_of_study = edu.get("field", "")
            institution = edu.get("institution", "")
            text = " ".join(p for p in [degree, field_of_study, institution] if p).strip()
            records.append(EvidenceRecord(
                source_type="education",
                content=text,
                skills_mentioned=[],
            ))

        # ── Extra text (e.g. summary) ─────────────────────────────────────────
        if extra_text:
            records.append(EvidenceRecord(
                source_type="summary",
                content=extra_text[:500],
                skills_mentioned=[],
            ))

        return records


@dataclass
class ClaimVerification:
    claim: str
    status: VerificationStatus
    matched_keywords: list[str] = field(default_factory=list)
    contradiction_source: str | None = None


@dataclass
class ValidationResult:
    verified_claims: list[str] = field(default_factory=list)       # SUPPORTED (backwards compat)
    unverified_claims: list[str] = field(default_factory=list)     # UNSUPPORTED (backwards compat)
    plausible_claims: list[str] = field(default_factory=list)      # PLAUSIBLE
    contradicted_claims: list[str] = field(default_factory=list)   # CONTRADICTED
    detailed: list[ClaimVerification] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.unverified_claims) == 0 and len(self.contradicted_claims) == 0

    def to_dict(self) -> dict:
        return {
            "verified_claims": self.verified_claims,
            "plausible_claims": self.plausible_claims,
            "unverified_claims": self.unverified_claims,
            "contradicted_claims": self.contradicted_claims,
            "is_clean": self.is_clean,
        }


def _extract_claim_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if any(p.search(s) for p in _CLAIM_PATTERNS)]


def _keywords(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"\b\w{3,}\b", text)}


def _tf_vector(text: str) -> dict[str, float]:
    """Term frequency vector for a text string (bag-of-words, normalised)."""
    words = re.findall(r"\b\w{3,}\b", text.lower())
    if not words:
        return {}
    counts: dict[str, float] = {}
    for w in words:
        counts[w] = counts.get(w, 0.0) + 1.0
    total = sum(counts.values())
    return {w: c / total for w, c in counts.items()}


def _semantic_similarity(claim: str, evidence: str) -> float:
    """Term-frequency cosine similarity between claim and evidence text.

    Returns a float in [0.0, 1.0]. Uses no external dependencies.
    A score ≥ 0.10 is treated as a weak semantic match by _classify_claim.
    """
    q = _tf_vector(claim)
    d = _tf_vector(evidence)
    common = set(q) & set(d)
    if not common:
        return 0.0
    dot = sum(q[t] * d[t] for t in common)
    q_norm = math.sqrt(sum(v * v for v in q.values()))
    d_norm = math.sqrt(sum(v * v for v in d.values()))
    if q_norm == 0.0 or d_norm == 0.0:
        return 0.0
    return round(dot / (q_norm * d_norm), 4)


def _temporal_consistency(claim: str, experiences: list) -> bool:
    """Return True if year claims in `claim` are consistent with experience records.

    Checks whether a stated year (e.g. "since 2019", "in 2022") falls within
    the date range of at least one experience record that shares keywords with
    the claim. Returns True (consistent) when no contradiction is found or when
    there is not enough temporal data to make a determination.
    """
    year_match = re.search(r"\b(19|20)(\d{2})\b", claim)
    if not year_match:
        return True  # no year claim — nothing to validate

    claimed_year = int(year_match.group(0))
    claim_words = _keywords(claim)

    for record in experiences:
        ev_text = getattr(record, "content", "") or ""
        ev_words = _keywords(ev_text)
        overlap = claim_words & ev_words - {"years", "experience", "the", "and"}
        if not overlap:
            continue
        # Look for year ranges in the evidence text like "2015–2018" or "2015-2018"
        range_m = re.search(r"\b(19|20)(\d{2})\s*[-–]\s*(19|20)(\d{2})\b", ev_text)
        if range_m:
            start_year = int(f"{range_m.group(1)}{range_m.group(2)}")
            end_year = int(f"{range_m.group(3)}{range_m.group(4)}")
            if claimed_year < start_year or claimed_year > end_year + 1:
                return False  # year falls outside the experience window

    return True


def _check_contradiction(claim: str, evidence_records: list) -> str | None:
    """Detect if a years-of-experience claim contradicts computed evidence.

    Returns the contradiction explanation string, or None if no contradiction.
    Only triggers when the claim states a HIGHER number than any evidence supports.
    """
    for pat in _INFLATION_PATTERNS:
        m = pat.search(claim)
        if not m:
            continue
        claimed_years = int(m.group(1))
        # Look for years data in evidence that mentions the same tech/skill
        claim_words = _keywords(claim)
        for record in evidence_records:
            ev_text = getattr(record, "content", "") or getattr(record, "claim", "") or ""
            ev_words = _keywords(ev_text)
            # Overlap in non-stopwords suggests they're talking about the same skill
            overlap = claim_words & ev_words - {"years", "experience", "the", "and", "for", "with", "have", "has"}
            if not overlap:
                continue
            # Check if evidence explicitly states fewer years
            ev_years_match = re.search(r"\b(\d+)\s*(?:\.|years?)", ev_text, re.IGNORECASE)
            if ev_years_match:
                ev_years = int(ev_years_match.group(1))
                if ev_years > 0 and claimed_years > ev_years * 1.5 + 1:
                    return (
                        f"claim states {claimed_years} years but evidence record "
                        f"for '{', '.join(list(overlap)[:3])}' indicates ~{ev_years} years"
                    )
    return None


def _classify_claim(claim: str, evidence_records: list) -> ClaimVerification:
    """Classify a claim as SUPPORTED, PLAUSIBLE, UNSUPPORTED, or CONTRADICTED.

    CONTRADICTED: claim's numeric assertion is inconsistent with evidence
    SUPPORTED  : ≥ 3 keyword matches across evidence records
    PLAUSIBLE  : 1–2 keyword matches (consistent but not strongly confirmed)
    UNSUPPORTED: 0 keyword matches or no evidence records
    """
    if not evidence_records:
        return ClaimVerification(claim=claim, status="UNSUPPORTED")

    # Check for contradiction first
    contradiction = _check_contradiction(claim, evidence_records)
    if contradiction:
        return ClaimVerification(
            claim=claim, status="CONTRADICTED",
            contradiction_source=contradiction,
        )

    claim_words = _keywords(claim)
    best_overlap: list[str] = []
    best_semantic: float = 0.0

    for record in evidence_records:
        evidence_text = getattr(record, "content", "") or getattr(record, "claim", "") or ""
        source_text = getattr(record, "source_text", "") or ""
        combined = evidence_text + " " + source_text
        evidence_words = _keywords(combined)
        overlap = list(claim_words & evidence_words)
        if len(overlap) > len(best_overlap):
            best_overlap = overlap
        sim = _semantic_similarity(claim, combined)
        if sim > best_semantic:
            best_semantic = sim

    # Temporal consistency check (returns True when there is nothing to flag)
    experience_records = [r for r in evidence_records if getattr(r, "source_type", "") == "experience"]
    temporally_ok = _temporal_consistency(claim, experience_records)
    if not temporally_ok:
        return ClaimVerification(
            claim=claim, status="CONTRADICTED",
            contradiction_source="year claim is outside the recorded experience window",
        )

    n = len(best_overlap)
    if n >= 3:
        status: VerificationStatus = "SUPPORTED"
    elif n >= 1:
        status = "PLAUSIBLE"
    elif best_semantic >= 0.10:
        # Weak semantic similarity without keyword hits → PLAUSIBLE
        status = "PLAUSIBLE"
    else:
        status = "UNSUPPORTED"

    return ClaimVerification(claim=claim, status=status, matched_keywords=best_overlap)


def validate_claims(text: str, evidence_records: list) -> ValidationResult:
    """Check generated text claims against candidate evidence records.

    Returns categorized claims with SUPPORTED/PLAUSIBLE/UNSUPPORTED/CONTRADICTED status.
    Pass evidence_records built by EvidenceBuilder.build_from_profile() for real validation.
    """
    claims = _extract_claim_sentences(text)
    result = ValidationResult()

    for claim in claims:
        verification = _classify_claim(claim, evidence_records)
        result.detailed.append(verification)

        if verification.status == "SUPPORTED":
            result.verified_claims.append(claim)
        elif verification.status == "PLAUSIBLE":
            result.plausible_claims.append(claim)
        elif verification.status == "CONTRADICTED":
            result.contradicted_claims.append(claim)
        else:
            result.unverified_claims.append(claim)

    return result
