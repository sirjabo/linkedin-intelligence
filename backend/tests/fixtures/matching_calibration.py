"""Labeled matching calibration pairs for measuring match scoring accuracy.

Each entry is a (candidate_snapshot, job_snapshot, expected_decision) triple.
expected_decision is one of: "apply", "skip", "stretch"

Used to measure:
  - False positive rate (FP): "apply" predicted when expected is "skip"
  - False negative rate (FN): "skip" predicted when expected is "apply"
  - Precision / Recall over the BLOCKER threshold

Run via: pytest tests/test_matching_calibration.py
"""
from dataclasses import dataclass, field
from typing import Literal

Decision = Literal["apply", "skip", "stretch"]


@dataclass
class CandidateSnapshot:
    name: str
    skills: list[str]
    years_experience: float
    location: str
    work_authorization: str  # "authorized" | "visa_required" | "citizen"
    salary_min_usd: int
    seniority: str  # "junior" | "mid" | "senior" | "staff" | "principal"


@dataclass
class JobSnapshot:
    title: str
    company: str
    location: str
    remote: bool
    required_skills: list[str]
    nice_to_have_skills: list[str]
    min_years_experience: float
    salary_max_usd: int | None
    requires_sponsorship: bool  # True = employer will sponsor
    seniority: str


@dataclass
class CalibrationPair:
    label: str
    candidate: CandidateSnapshot
    job: JobSnapshot
    expected: Decision
    rationale: str = ""


# ── Candidate archetypes ──────────────────────────────────────────────────────

_SENIOR_DE = CandidateSnapshot(
    name="Alice Smith",
    skills=["Python", "SQL", "Spark", "Airflow", "AWS", "PostgreSQL", "dbt"],
    years_experience=7,
    location="Buenos Aires, Argentina",
    work_authorization="visa_required",
    salary_min_usd=95_000,
    seniority="senior",
)

_MID_DE = CandidateSnapshot(
    name="Bob Jones",
    skills=["Python", "SQL", "Pandas", "Docker"],
    years_experience=3,
    location="Buenos Aires, Argentina",
    work_authorization="visa_required",
    salary_min_usd=65_000,
    seniority="mid",
)

_JUNIOR_DE = CandidateSnapshot(
    name="Carlos Ruiz",
    skills=["Python", "SQL"],
    years_experience=1,
    location="Córdoba, Argentina",
    work_authorization="authorized",
    salary_min_usd=35_000,
    seniority="junior",
)

_AUTHORIZED_SENIOR_DE = CandidateSnapshot(
    name="Diana Wang",
    skills=["Python", "SQL", "Spark", "Airflow", "Kubernetes", "dbt", "Snowflake"],
    years_experience=9,
    location="San Francisco, CA",
    work_authorization="citizen",
    salary_min_usd=140_000,
    seniority="staff",
)

_FRONTEND_DEV = CandidateSnapshot(
    name="Elena Torres",
    skills=["React", "TypeScript", "CSS", "GraphQL", "Next.js"],
    years_experience=5,
    location="Madrid, Spain",
    work_authorization="authorized",
    salary_min_usd=75_000,
    seniority="senior",
)

_BACKEND_DEV = CandidateSnapshot(
    name="Felipe Moreno",
    skills=["Java", "Spring Boot", "Kafka", "MySQL", "Redis"],
    years_experience=6,
    location="São Paulo, Brazil",
    work_authorization="visa_required",
    salary_min_usd=80_000,
    seniority="senior",
)

_DATA_SCIENTIST = CandidateSnapshot(
    name="Grace Kim",
    skills=["Python", "SQL", "scikit-learn", "TensorFlow", "R", "statistics"],
    years_experience=4,
    location="New York, NY",
    work_authorization="citizen",
    salary_min_usd=110_000,
    seniority="mid",
)


# ── Job archetypes ────────────────────────────────────────────────────────────

_SENIOR_DE_JOB_BUENOS_AIRES = JobSnapshot(
    title="Senior Data Engineer",
    company="TechCorp",
    location="Buenos Aires, Argentina",
    remote=True,
    required_skills=["Python", "SQL", "Spark"],
    nice_to_have_skills=["Airflow", "AWS", "dbt"],
    min_years_experience=5,
    salary_max_usd=120_000,
    requires_sponsorship=True,
    seniority="senior",
)

_SENIOR_DE_JOB_NYC = JobSnapshot(
    title="Senior Data Engineer",
    company="BigBank",
    location="New York, NY",
    remote=False,
    required_skills=["Python", "SQL", "Spark", "Kafka"],
    nice_to_have_skills=["AWS", "Snowflake"],
    min_years_experience=5,
    salary_max_usd=180_000,
    requires_sponsorship=False,
    seniority="senior",
)

_JUNIOR_DE_JOB = JobSnapshot(
    title="Junior Data Engineer",
    company="StartupX",
    location="Buenos Aires, Argentina",
    remote=True,
    required_skills=["Python", "SQL"],
    nice_to_have_skills=["Docker", "Airflow"],
    min_years_experience=0,
    salary_max_usd=50_000,
    requires_sponsorship=True,
    seniority="junior",
)

_STAFF_DE_JOB = JobSnapshot(
    title="Staff Data Engineer",
    company="BigTech",
    location="San Francisco, CA",
    remote=True,
    required_skills=["Python", "Spark", "Kafka", "Kubernetes", "dbt"],
    nice_to_have_skills=["Airflow", "Snowflake", "Terraform"],
    min_years_experience=8,
    salary_max_usd=300_000,
    requires_sponsorship=True,
    seniority="staff",
)

_FRONTEND_JOB = JobSnapshot(
    title="Senior Frontend Engineer",
    company="ProductCo",
    location="Madrid, Spain",
    remote=True,
    required_skills=["React", "TypeScript", "GraphQL"],
    nice_to_have_skills=["Next.js", "Testing Library"],
    min_years_experience=4,
    salary_max_usd=100_000,
    requires_sponsorship=True,
    seniority="senior",
)

_DE_NO_SPONSOR = JobSnapshot(
    title="Data Engineer",
    company="LocalCorp",
    location="Austin, TX",
    remote=False,
    required_skills=["Python", "SQL", "Spark"],
    nice_to_have_skills=["AWS"],
    min_years_experience=3,
    salary_max_usd=130_000,
    requires_sponsorship=False,
    seniority="mid",
)


# ── Calibration dataset ───────────────────────────────────────────────────────

CALIBRATION_PAIRS: list[CalibrationPair] = [
    # ── True positives (strong match → apply) ────────────────────────────────
    CalibrationPair(
        label="senior_de_perfect_match",
        candidate=_SENIOR_DE,
        job=_SENIOR_DE_JOB_BUENOS_AIRES,
        expected="apply",
        rationale="Skills, seniority, location, and salary all align; employer sponsors",
    ),
    CalibrationPair(
        label="authorized_staff_de_matches_staff_job",
        candidate=_AUTHORIZED_SENIOR_DE,
        job=_STAFF_DE_JOB,
        expected="apply",
        rationale="9-year staff DE meets all requirements; authorized; salary fits",
    ),
    CalibrationPair(
        label="frontend_dev_matches_frontend_job",
        candidate=_FRONTEND_DEV,
        job=_FRONTEND_JOB,
        expected="apply",
        rationale="Frontend skills are a direct match; location matches; authorized",
    ),
    CalibrationPair(
        label="junior_de_matches_junior_job",
        candidate=_JUNIOR_DE,
        job=_JUNIOR_DE_JOB,
        expected="apply",
        rationale="1yr experience fits junior requirements; location matches; employer sponsors",
    ),

    # ── True negatives (poor match → skip) ───────────────────────────────────
    CalibrationPair(
        label="visa_required_no_sponsorship",
        candidate=_MID_DE,
        job=_DE_NO_SPONSOR,
        expected="skip",
        rationale="Employer does not sponsor and candidate requires visa — hard blocker",
    ),
    CalibrationPair(
        label="junior_applies_to_staff_role",
        candidate=_JUNIOR_DE,
        job=_STAFF_DE_JOB,
        expected="skip",
        rationale="1yr experience vs 8yr requirement; missing most required skills",
    ),
    CalibrationPair(
        label="frontend_dev_applies_to_data_engineering",
        candidate=_FRONTEND_DEV,
        job=_SENIOR_DE_JOB_BUENOS_AIRES,
        expected="skip",
        rationale="Frontend skills don't overlap with data engineering requirements",
    ),
    CalibrationPair(
        label="salary_below_candidate_min",
        candidate=_AUTHORIZED_SENIOR_DE,
        job=_JUNIOR_DE_JOB,
        expected="skip",
        rationale="Max salary $50k far below candidate's $140k minimum; seniority mismatch",
    ),
    CalibrationPair(
        label="data_scientist_applying_to_pure_de_role",
        candidate=_DATA_SCIENTIST,
        job=_SENIOR_DE_JOB_NYC,
        expected="skip",
        rationale="ML-focused profile lacks Kafka/Spark required for this DE role",
    ),

    # ── Stretch cases (partial match → stretch) ───────────────────────────────
    CalibrationPair(
        label="mid_de_stretches_to_senior_role",
        candidate=_MID_DE,
        job=_SENIOR_DE_JOB_BUENOS_AIRES,
        expected="stretch",
        rationale="Missing Spark/Airflow/AWS but has core Python+SQL; 3yr vs 5yr required",
    ),
    CalibrationPair(
        label="senior_de_overqualified_for_junior_role",
        candidate=_SENIOR_DE,
        job=_JUNIOR_DE_JOB,
        expected="stretch",
        rationale="Skills far exceed requirements; salary max $50k vs $95k minimum",
    ),
    CalibrationPair(
        label="backend_dev_pivoting_to_data_engineering",
        candidate=_BACKEND_DEV,
        job=_SENIOR_DE_JOB_BUENOS_AIRES,
        expected="stretch",
        rationale="Java/Kafka experience relevant but missing Python/Spark specifically",
    ),
    CalibrationPair(
        label="senior_de_no_sponsorship_remote_ok",
        candidate=_SENIOR_DE,
        job=_DE_NO_SPONSOR,
        expected="skip",
        rationale="No sponsorship + candidate is visa_required — hard blocker regardless of remote",
    ),
    CalibrationPair(
        label="authorized_senior_de_matches_no_sponsor_role",
        candidate=_AUTHORIZED_SENIOR_DE,
        job=_DE_NO_SPONSOR,
        expected="apply",
        rationale="Authorized to work; skills match; salary within range",
    ),
    CalibrationPair(
        label="senior_de_nyc_relocation_required",
        candidate=_SENIOR_DE,
        job=_SENIOR_DE_JOB_NYC,
        expected="skip",
        rationale="visa_required + no sponsorship is a hard blocker regardless of skill match or relocation",
    ),
    CalibrationPair(
        label="data_scientist_to_staff_de",
        candidate=_DATA_SCIENTIST,
        job=_STAFF_DE_JOB,
        expected="skip",
        rationale="DS profile lacks distributed systems (Spark/Kafka/K8s); 4yr vs 8yr required",
    ),
    CalibrationPair(
        label="mid_de_junior_role_visa",
        candidate=_MID_DE,
        job=_JUNIOR_DE_JOB,
        expected="apply",
        rationale="Mid DE exceeds junior requirements; employer sponsors; salary matches",
    ),
    CalibrationPair(
        label="frontend_to_staff_de",
        candidate=_FRONTEND_DEV,
        job=_STAFF_DE_JOB,
        expected="skip",
        rationale="Completely different domain; no relevant skills overlap",
    ),
    CalibrationPair(
        label="authorized_de_frontend_job",
        candidate=_AUTHORIZED_SENIOR_DE,
        job=_FRONTEND_JOB,
        expected="skip",
        rationale="Data engineering skills don't match frontend requirements",
    ),
    CalibrationPair(
        label="backend_dev_no_sponsor",
        candidate=_BACKEND_DEV,
        job=_DE_NO_SPONSOR,
        expected="skip",
        rationale="visa_required + no sponsorship = hard blocker; also backend vs DE skills",
    ),
]

assert len(CALIBRATION_PAIRS) >= 20, f"Need ≥20 pairs, got {len(CALIBRATION_PAIRS)}"
