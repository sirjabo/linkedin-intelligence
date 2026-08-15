"""Deterministic matching engine.

Pure functions — no I/O, no async, no LLM. Testable in isolation.
"""
from dataclasses import dataclass, field
from typing import Literal

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


# ── Result types ──────────────────────────────────────────────────────────────

ApplicationDecision = Literal[
    "APPLY", "APPLY_WITH_CUSTOMIZATION", "STRETCH", "LOW_FIT", "DO_NOT_APPLY", "BLOCKED"
]


@dataclass
class HardConstraintResult:
    blocked: bool
    blockers: list[str] = field(default_factory=list)


@dataclass
class DeterministicResult:
    skill_overlap_score: float
    experience_score: float
    location_score: float
    education_score: float
    salary_score: float | None  # None when salary data is unavailable
    overall_score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    career_fit_score: float | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

# Skill synonym groups — any term within a group is treated as equivalent.
# Each inner list is a family of aliases for the same technology/concept.
SKILL_SYNONYMS: list[list[str]] = [
    ["javascript", "js", "ecmascript", "node.js", "nodejs", "node"],
    ["typescript", "ts"],
    ["python", "py"],
    ["machine learning", "ml"],
    ["artificial intelligence", "ai"],
    ["natural language processing", "nlp"],
    ["deep learning", "dl"],
    ["large language model", "llm", "large language models"],
    ["kubernetes", "k8s"],
    ["postgresql", "postgres", "pg"],
    ["amazon web services", "aws"],
    ["google cloud", "gcp", "google cloud platform"],
    ["microsoft azure", "azure"],
    ["continuous integration", "ci/cd", "ci", "cd"],
    ["react.js", "react", "reactjs"],
    ["vue.js", "vue", "vuejs"],
    ["next.js", "nextjs"],
    ["fastapi", "fast api"],
    ["spring boot", "spring"],
    ["c++", "cpp"],
    ["c#", "csharp", "c sharp"],
    ["elastic search", "elasticsearch"],
    ["redis", "redis cache"],
    ["mongodb", "mongo"],
    ["graphql", "graph ql"],
    ["rest api", "rest", "restful", "restful api"],
]

# Build a lookup: normalized term → set of synonyms (including itself)
_SYNONYM_MAP: dict[str, frozenset[str]] = {}
for _group in SKILL_SYNONYMS:
    _normed = frozenset(s.lower().strip() for s in _group)
    for _term in _normed:
        _SYNONYM_MAP[_term] = _normed


def _expand_skill(skill: str) -> frozenset[str]:
    """Return the synonym group for a skill, or a singleton if not found."""
    n = skill.lower().strip()
    return _SYNONYM_MAP.get(n, frozenset({n}))


def _norm(s: str) -> str:
    return s.lower().strip()


def _skill_in_text(candidate_skills: set[str], text: str) -> bool:
    text_lower = _norm(text)
    # Direct substring match
    if any(sk and (sk in text_lower or text_lower in sk) for sk in candidate_skills):
        return True
    # Synonym expansion: expand the requirement text and check against expanded candidate skills
    req_synonyms = _expand_skill(text_lower)
    for sk in candidate_skills:
        if not sk:
            continue
        sk_synonyms = _expand_skill(sk)
        if req_synonyms & sk_synonyms:
            return True
    return False


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

    return {0: 1.00, 1: 0.85, 2: 0.60}.get(distance, 0.30)


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


def _score_salary(
    job_salary_max: int | None,
    candidate_salary_pref_min: int | None,
) -> float | None:
    """Return a salary compatibility score or None when data is unavailable.

    1.0  — salary max meets or exceeds candidate's minimum
    0.75 — salary max is 0–10% below candidate minimum (close enough)
    0.50 — salary max is 10–30% below (worth discussing)
    0.20 — salary max is >30% below (likely dealbreaker)
    """
    if job_salary_max is None or candidate_salary_pref_min is None:
        return None
    if job_salary_max >= candidate_salary_pref_min:
        return 1.0
    ratio = job_salary_max / candidate_salary_pref_min
    if ratio >= 0.90:
        return 0.75
    if ratio >= 0.70:
        return 0.50
    return 0.20


# ── Hard Constraints Layer ─────────────────────────────────────────────────────

def check_hard_constraints(
    candidate_career_level: str | None,
    candidate_salary_pref_min: int | None,
    job_seniority: str | None,
    job_salary_max: int | None,
    candidate_work_authorization: str | None = None,
    job_visa_sponsorship: bool | None = None,
) -> HardConstraintResult:
    """Return blocked=True if any hard constraint fires.

    Hard constraints prevent application regardless of skill match:
    - Seniority gap > 2 levels (candidate too junior for the role)
    - Salary gap > 30% (job pays far below candidate's minimum)
    - Work authorization: candidate needs sponsorship but job doesn't offer it
    """
    blockers: list[str] = []

    # Seniority blocker
    if candidate_career_level and job_seniority:
        c_rank = SENIORITY_RANK.get(_norm(candidate_career_level), 3)
        j_rank = SENIORITY_RANK.get(_norm(job_seniority), 3)
        if j_rank - c_rank > 2:
            blockers.append(
                f"Seniority gap: candidate is {candidate_career_level} (rank {c_rank}), "
                f"job requires {job_seniority} (rank {j_rank})"
            )

    # Salary blocker (> 30% below minimum)
    if (
        job_salary_max is not None
        and candidate_salary_pref_min is not None
        and candidate_salary_pref_min > 0
        and job_salary_max < candidate_salary_pref_min * 0.70
    ):
        gap_pct = round((1 - job_salary_max / candidate_salary_pref_min) * 100, 1)
        blockers.append(
            f"Salary gap: job max ${job_salary_max:,} is {gap_pct}% below "
            f"candidate minimum ${candidate_salary_pref_min:,}"
        )

    # Work authorization blocker
    # Blocked only when candidate explicitly needs sponsorship AND job explicitly does not offer it
    if candidate_work_authorization == "visa_required" and job_visa_sponsorship is False:
        blockers.append(
            "Work authorization: candidate requires visa sponsorship but job does not offer it"
        )

    return HardConstraintResult(blocked=bool(blockers), blockers=blockers)


# ── Career Fit Score ───────────────────────────────────────────────────────────

def compute_career_fit(
    candidate_career_level: str | None,
    candidate_salary_pref_min: int | None,
    job_seniority: str | None,
    job_salary_max: int | None,
) -> float:
    """Compute career fit score [0.0, 1.0].

    Measures how well the job fits the candidate's career trajectory,
    independent of current skill match. Ideal: job is 0–1 levels above candidate.
    """
    scores: list[float] = []

    if candidate_career_level and job_seniority:
        c_rank = SENIORITY_RANK.get(_norm(candidate_career_level), 3)
        j_rank = SENIORITY_RANK.get(_norm(job_seniority), 3)
        gap = j_rank - c_rank
        if gap == 1:
            scores.append(1.00)   # one step up — ideal growth
        elif gap == 0:
            scores.append(0.90)   # lateral — solid
        elif gap == -1:
            scores.append(0.65)   # slight step down (intentional pivot?)
        elif gap == 2:
            scores.append(0.55)   # stretch goal
        elif gap < -1:
            scores.append(0.40)   # significant step down
        else:
            scores.append(0.15)   # gap > 2 — hard-blocked anyway

    sal = _score_salary(job_salary_max, candidate_salary_pref_min)
    if sal is not None:
        scores.append(sal)

    return round(sum(scores) / len(scores), 3) if scores else 0.70


# ── Application Decision Engine ────────────────────────────────────────────────

def decide_application(
    overall_score: float,
    hard_constraint: HardConstraintResult,
    missing_skills: list[str],
) -> ApplicationDecision:
    """Return an actionable recommendation for this candidate/job pair.

    BLOCKED              → hard constraint fired (seniority or salary gap)
    DO_NOT_APPLY         → overall score < 0.40
    LOW_FIT              → 0.40 ≤ score < 0.55
    STRETCH              → 0.55 ≤ score < 0.70
    APPLY_WITH_CUSTOMIZATION → score ≥ 0.70 but has missing skills
    APPLY                → score ≥ 0.70 and no missing skills
    """
    if hard_constraint.blocked:
        return "BLOCKED"
    if overall_score >= 0.70:
        return "APPLY_WITH_CUSTOMIZATION" if missing_skills else "APPLY"
    if overall_score >= 0.55:
        return "STRETCH"
    if overall_score >= 0.40:
        return "LOW_FIT"
    return "DO_NOT_APPLY"


# ── Public API ─────────────────────────────────────────────────────────────────

def tier_from_score(score: float) -> str:
    for threshold, tier in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "poor"


SALARY_WEIGHT = 0.10
BASE_WEIGHTS_WITH_SALARY = {
    "skill_overlap": 0.36,
    "experience": 0.27,
    "location": 0.18,
    "education": 0.09,
    "salary": SALARY_WEIGHT,
}


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
    job_salary_max: int | None = None,
    candidate_salary_pref_min: int | None = None,
) -> DeterministicResult:
    """Compute deterministic match scores from structured profile + job data.

    Accepts plain Python values so it can be unit-tested without ORM objects.
    When salary data is available, incorporates a 5th salary component.
    Also computes career_fit_score (separate from job-fit score).
    """
    skill_score, matched, missing = _score_skill_overlap(
        profile_skills, requirements, job_tech_stack
    )
    exp_score = _score_experience(profile_career_level, job_seniority)
    loc_score = _score_location(candidate_location, job_location, job_remote_type)
    edu_score = _score_education(profile_education, requirements)
    sal_score = _score_salary(job_salary_max, candidate_salary_pref_min)
    career_fit = compute_career_fit(
        profile_career_level, candidate_salary_pref_min, job_seniority, job_salary_max
    )

    if sal_score is not None:
        w = BASE_WEIGHTS_WITH_SALARY
        overall = (
            skill_score * w["skill_overlap"]
            + exp_score * w["experience"]
            + loc_score * w["location"]
            + edu_score * w["education"]
            + sal_score * w["salary"]
        )
    else:
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
        salary_score=round(sal_score, 3) if sal_score is not None else None,
        overall_score=round(overall, 3),
        matched_skills=matched,
        missing_skills=missing,
        career_fit_score=career_fit,
    )
