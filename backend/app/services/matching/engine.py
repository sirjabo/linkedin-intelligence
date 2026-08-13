"""Deterministic matching engine.

Pure functions — no I/O, no async, no LLM. Testable in isolation.
"""
from dataclasses import dataclass, field

# ── Constants ─────────────────────────────────────────────────────────────────

SENIORITY_RANK: dict[str, int] = {
    "intern": 1, "junior": 2, "mid": 3, "senior": 4,
    "staff": 5, "lead": 5, "principal": 6, "manager": 5,
    "director": 7, "vp": 8, "c-level": 9,
}

WEIGHTS = {
    "skill_overlap": 0.40,
    "experience": 0.30,
    "location": 0.20,
    "education": 0.10,
}

# hybrid = det * DET_WEIGHT + llm * (1 - DET_WEIGHT)
DET_WEIGHT = 0.60

TIER_THRESHOLDS = [
    (0.85, "excellent"),
    (0.70, "strong"),
    (0.55, "moderate"),
    (0.40, "weak"),
    (0.00, "poor"),
]


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class DeterministicResult:
    skill_overlap_score: float
    experience_score: float
    location_score: float
    education_score: float
    overall_score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return s.lower().strip()


def _skill_in_text(candidate_skills: set[str], text: str) -> bool:
    text_lower = _norm(text)
    return any(sk and (sk in text_lower or text_lower in sk) for sk in candidate_skills)


def _score_skill_overlap(
    profile_skills: list[dict],
    requirements: list,       # list of JobRequirement ORM objects
    tech_stack: list[str] | None,
) -> tuple[float, list[str], list[str]]:
    candidate_skills = {_norm(s.get("canonical_name", "")) for s in profile_skills if s.get("canonical_name")}

    must_have_tech = [
        r for r in requirements
        if r.requirement_type == "must_have" and r.category == "technical"
    ]
    nice_to_have_tech = [
        r for r in requirements
        if r.requirement_type == "nice_to_have" and r.category == "technical"
    ]

    matched: list[str] = []
    missing: list[str] = []

    if must_have_tech:
        for req in must_have_tech:
            if _skill_in_text(candidate_skills, req.description):
                matched.append(req.description)
            else:
                missing.append(req.description)
        score = len(matched) / len(must_have_tech) if must_have_tech else 0.7
    elif tech_stack:
        # Fall back to tech_stack when no explicit technical requirements
        ts_norm = [_norm(t) for t in tech_stack]
        matched = [t for t in ts_norm if t in candidate_skills]
        missing = [t for t in ts_norm if t not in candidate_skills]
        score = len(matched) / len(ts_norm) if ts_norm else 0.7
    else:
        score = 0.70  # neutral — no technical criteria to evaluate

    # Bonus from nice-to-have matches (capped at +0.10)
    if nice_to_have_tech and candidate_skills:
        bonus_matched = sum(
            1 for r in nice_to_have_tech if _skill_in_text(candidate_skills, r.description)
        )
        score = min(1.0, score + 0.10 * (bonus_matched / len(nice_to_have_tech)))

    return round(score, 3), matched, missing


def _score_experience(candidate_level: str | None, job_seniority: str | None) -> float:
    if not candidate_level or not job_seniority:
        return 0.65

    c = SENIORITY_RANK.get(_norm(candidate_level), 3)
    j = SENIORITY_RANK.get(_norm(job_seniority), 3)
    distance = abs(c - j)

    if distance == 0:
        return 1.00
    elif distance == 1:
        return 0.85
    elif distance == 2:
        return 0.60
    else:
        return 0.30


def _score_location(
    candidate_location: str | None,
    job_location: str | None,
    remote_type: str | None,
) -> float:
    if remote_type == "remote":
        return 1.0
    if remote_type == "hybrid":
        return 0.75
    if not job_location:
        return 0.65  # unclear — assume flexible
    if candidate_location:
        c_tokens = set(_norm(candidate_location).split())
        j_tokens = set(_norm(job_location).split())
        if c_tokens & j_tokens:
            return 1.0
    return 0.35


def _score_education(profile_education: list | None, requirements: list) -> float:
    edu_reqs = [r for r in requirements if r.category == "education"]
    if not edu_reqs:
        return 1.0
    return 0.85 if profile_education else 0.50


# ── Public API ─────────────────────────────────────────────────────────────────

def tier_from_score(score: float) -> str:
    for threshold, tier in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "poor"


def compute_deterministic(
    profile_skills: list[dict],
    profile_career_level: str | None,
    profile_education: list | None,
    candidate_location: str | None,
    job_seniority: str | None,
    job_location: str | None,
    job_remote_type: str | None,
    job_tech_stack: list[str] | None,
    requirements: list,
) -> DeterministicResult:
    """Compute deterministic match scores from structured profile + job data.

    Accepts plain Python values so it can be unit-tested without ORM objects.
    """
    skill_score, matched, missing = _score_skill_overlap(
        profile_skills, requirements, job_tech_stack
    )
    exp_score = _score_experience(profile_career_level, job_seniority)
    loc_score = _score_location(candidate_location, job_location, job_remote_type)
    edu_score = _score_education(profile_education, requirements)

    overall = (
        skill_score * WEIGHTS["skill_overlap"]
        + exp_score * WEIGHTS["experience"]
        + loc_score * WEIGHTS["location"]
        + edu_score * WEIGHTS["education"]
    )

    return DeterministicResult(
        skill_overlap_score=round(skill_score, 3),
        experience_score=round(exp_score, 3),
        location_score=round(loc_score, 3),
        education_score=round(edu_score, 3),
        overall_score=round(overall, 3),
        matched_skills=matched,
        missing_skills=missing,
    )
