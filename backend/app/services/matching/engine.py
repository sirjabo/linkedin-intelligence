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

RequirementStatus = Literal["MATCHED", "PARTIAL", "MISSING", "BLOCKER", "UNCERTAIN"]
RequirementImportance = Literal["MUST", "NICE_TO_HAVE"]


@dataclass
class HardConstraintResult:
    blocked: bool
    blockers: list[str] = field(default_factory=list)


@dataclass
class RequirementMatch:
    """Per-requirement breakdown of match status."""
    text: str
    requirement_type: str          # must_have | nice_to_have
    importance: RequirementImportance
    candidate_status: RequirementStatus
    match_score: float             # 0.0–1.0
    evidence_ref: str | None = None


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
    requirement_matches: list[RequirementMatch] = field(default_factory=list)
    domain_score: float | None = None  # None when domain cannot be determined


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


# Transferable skill mappings: candidate skill A partially qualifies for requirement B.
# Key = candidate skill; value = list of requirement terms it partially fulfills.
TRANSFERABLE_SKILLS: dict[str, list[str]] = {
    "machine learning": ["data science", "deep learning", "nlp", "computer vision", "ai", "ai/ml"],
    "data science": ["machine learning", "statistics", "analytics", "data analysis"],
    "devops": ["sre", "site reliability engineering", "platform engineering", "cloud infrastructure"],
    "sre": ["devops", "infrastructure", "platform engineering", "cloud operations"],
    "full stack": ["backend", "frontend", "web development", "software engineering"],
    "backend": ["full stack", "api development", "server-side", "software engineering"],
    "frontend": ["full stack", "web development", "ui engineering", "software engineering"],
    "mobile": ["ios", "android", "react native", "flutter", "cross-platform"],
    "ios": ["mobile development", "mobile", "cross-platform"],
    "android": ["mobile development", "mobile", "cross-platform"],
    "data engineering": ["etl", "data pipeline", "big data", "analytics engineering"],
    "cybersecurity": ["security engineering", "information security", "infosec", "appsec"],
    "nlp": ["machine learning", "ai", "text processing", "conversational ai", "ai/ml"],
    "computer vision": ["machine learning", "image processing", "ai", "ai/ml"],
    "embedded systems": ["firmware development", "hardware engineering", "iot"],
}

# Reverse map: requirement keyword → candidate skills that transfer into it
_TRANSFERABLE_REVERSE: dict[str, list[str]] = {}
for _src_skill, _target_reqs in TRANSFERABLE_SKILLS.items():
    for _t in _target_reqs:
        _TRANSFERABLE_REVERSE.setdefault(_t.lower().strip(), []).append(_src_skill.lower().strip())


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


def _classify_requirement_status(
    description: str,
    candidate_skills: set[str],
    req_type: str,
) -> RequirementMatch:
    """Classify a single requirement against candidate skills with MATCHED/PARTIAL/MISSING/BLOCKER."""
    matched = _skill_in_text(candidate_skills, description)
    # Partial: a synonym group that partially overlaps but is not a strong match
    # We use substring-in-text as the bar — if true, MATCHED; if false, consider PARTIAL
    # by checking if any candidate skill is conceptually related (first token match)
    if matched:
        status: RequirementStatus = "MATCHED"
        score = 1.0
    else:
        # Check for weak partial match: first word of requirement matches a candidate skill
        first_token = description.lower().split()[0] if description else ""
        weak = first_token and any(first_token in sk for sk in candidate_skills)
        if weak:
            status = "PARTIAL"
            score = 0.5
        else:
            # Check transferable skills: candidate skill A can partially fulfill requirement B
            req_lower = _norm(description)
            transferred = False
            for req_token in [req_lower, *req_lower.split()]:
                transferable_from = _TRANSFERABLE_REVERSE.get(req_token, [])
                if any(tf in candidate_skills for tf in transferable_from):
                    transferred = True
                    break
            if transferred:
                status = "PARTIAL"
                score = 0.35
            elif req_type == "must_have":
                status = "BLOCKER"
                score = 0.0
            else:
                status = "MISSING"
                score = 0.0

    importance: RequirementImportance = "MUST" if req_type == "must_have" else "NICE_TO_HAVE"
    return RequirementMatch(
        text=description,
        requirement_type=req_type,
        importance=importance,
        candidate_status=status,
        match_score=score,
    )


def _score_skill_overlap(
    profile_skills: list[dict],
    requirements: list,       # list of JobRequirement ORM objects
    tech_stack: list[str] | None,
) -> tuple[float, list[str], list[str], list[RequirementMatch]]:
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
    req_matches: list[RequirementMatch] = []

    if must_have_tech:
        for req in must_have_tech:
            rm = _classify_requirement_status(req.description, candidate_skills, "must_have")
            req_matches.append(rm)
            if rm.candidate_status == "MATCHED":
                matched.append(req.description)
            elif rm.candidate_status != "PARTIAL":
                missing.append(req.description)
        score = len(matched) / len(must_have_tech) if must_have_tech else 0.7
    elif tech_stack:
        # Fall back to tech_stack when no explicit technical requirements
        ts_norm = [_norm(t) for t in tech_stack]
        for t in ts_norm:
            if _skill_in_text(candidate_skills, t):
                matched.append(t)
                req_matches.append(RequirementMatch(
                    text=t, requirement_type="must_have", importance="MUST",
                    candidate_status="MATCHED", match_score=1.0,
                ))
            else:
                missing.append(t)
                req_matches.append(RequirementMatch(
                    text=t, requirement_type="must_have", importance="MUST",
                    candidate_status="MISSING", match_score=0.0,
                ))
        score = len(matched) / len(ts_norm) if ts_norm else 0.7
    else:
        score = 0.70  # neutral — no technical criteria to evaluate

    # Bonus from nice-to-have matches (capped at +0.10)
    if nice_to_have_tech and candidate_skills:
        bonus_matched = 0
        for req in nice_to_have_tech:
            rm = _classify_requirement_status(req.description, candidate_skills, "nice_to_have")
            req_matches.append(rm)
            if rm.candidate_status == "MATCHED":
                bonus_matched += 1
        score = min(1.0, score + 0.10 * (bonus_matched / len(nice_to_have_tech)))

    return round(score, 3), matched, missing, req_matches


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


# Domain keyword sets — used to align candidate industry experience with job context.
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "fintech": ["fintech", "finance", "financial", "banking", "payment", "payments", "trading",
                "lending", "insurance", "insurtech", "wealth management", "crypto", "blockchain", "neobank"],
    "healthtech": ["healthtech", "health", "healthcare", "medical", "clinical", "pharma",
                   "biotech", "hospital", "patient", "ehr", "telemedicine", "medtech"],
    "edtech": ["edtech", "education", "learning", "e-learning", "elearning", "school",
               "university", "lms", "training", "curriculum", "online course"],
    "ecommerce": ["ecommerce", "e-commerce", "retail", "marketplace", "shopping",
                  "fulfillment", "inventory", "direct-to-consumer", "dtc"],
    "gaming": ["gaming", "game", "games", "mobile game", "video game", "esports", "gamedev"],
    "adtech": ["adtech", "advertising", "ad tech", "programmatic", "dsp", "ssp",
               "martech", "marketing technology", "attribution"],
    "logistics": ["logistics", "supply chain", "shipping", "freight", "last-mile",
                  "warehouse", "transportation", "fleet"],
    "proptech": ["proptech", "real estate", "property", "realty", "mortgage", "construction tech"],
    "cybersecurity": ["cybersecurity", "security", "infosec", "threat", "vulnerability",
                      "soc", "appsec", "zero trust", "endpoint"],
    "ai": ["artificial intelligence", "machine learning", "deep learning", "nlp",
           "ai/ml", "llm", "generative ai", "computer vision", "ai company", "ai startup"],
    "data": ["data platform", "analytics", "big data", "business intelligence", "bi",
             "data infrastructure", "data warehouse"],
    "saas": ["saas", "software as a service", "cloud platform", "b2b software", "enterprise software"],
    "devtools": ["developer tools", "devtools", "developer platform", "sdk", "api company",
                 "open source", "infrastructure software"],
}


def _score_domain(
    candidate_industries: list[str] | None,
    job_text: str | None,
) -> float | None:
    """Score domain alignment between candidate industry experience and job context.

    Returns 1.0 for explicit domain match, 0.5 for inferred match,
    0.0 for no overlap, or None when inputs are insufficient.
    """
    if not candidate_industries or not job_text:
        return None

    job_lower = job_text.lower()
    candidate_lower = {c.lower().strip() for c in candidate_industries if c}

    # Detect which domains the job signals
    job_domains: set[str] = set()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in job_lower for kw in keywords):
            job_domains.add(domain)

    if not job_domains:
        return None

    # Check if candidate industry labels match the job's domain keywords
    direct_match = any(
        any(kw in ci for kw in _DOMAIN_KEYWORDS.get(domain, []))
        for domain in job_domains
        for ci in candidate_lower
    )
    if direct_match:
        return 1.0

    # Fallback: candidate industry name appears verbatim in job text
    inferred_match = any(ci in job_lower for ci in candidate_lower if len(ci) >= 4)
    if inferred_match:
        return 0.5

    return 0.0


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
    candidate_industries: list[str] | None = None,
    job_text: str | None = None,
) -> DeterministicResult:
    """Compute deterministic match scores from structured profile + job data.

    Accepts plain Python values so it can be unit-tested without ORM objects.
    When salary data is available, incorporates a 5th salary component.
    Also computes career_fit_score and domain_score (both informational, not weighted).
    """
    skill_score, matched, missing, req_matches = _score_skill_overlap(
        profile_skills, requirements, job_tech_stack
    )
    exp_score = _score_experience(profile_career_level, job_seniority)
    loc_score = _score_location(candidate_location, job_location, job_remote_type)
    edu_score = _score_education(profile_education, requirements)
    sal_score = _score_salary(job_salary_max, candidate_salary_pref_min)
    career_fit = compute_career_fit(
        profile_career_level, candidate_salary_pref_min, job_seniority, job_salary_max
    )
    domain = _score_domain(candidate_industries, job_text)

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
        requirement_matches=req_matches,
        domain_score=domain,
    )
