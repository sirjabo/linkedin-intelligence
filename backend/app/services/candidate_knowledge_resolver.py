"""CandidateKnowledgeResolver — maps semantic field types to candidate data.

All values are TRACEABLE to candidate context. Never invents data.
Resolution sources:
  DIRECT      — taken verbatim from candidate/application record
  COMPUTED    — derived from candidate data (e.g. sum of experience years)
  FROM_KB     — found in CandidateAnswer KB (stored human responses)
  GENERATED   — LLM call grounded in candidate context (custom essays only)
  HUMAN_REQUIRED — no source available; must be provided by the user
"""
import re
from dataclasses import dataclass
from typing import Literal

import anthropic

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.application import Application, CoverLetter
from app.services.form_intelligence import classify_field

logger = get_logger(__name__)

ResolutionSource = Literal["DIRECT", "COMPUTED", "FROM_KB", "GENERATED", "HUMAN_REQUIRED"]

# Semantic types that can NEVER be auto-filled without explicit human data
_ALWAYS_HUMAN = {"phone", "gender", "race_ethnicity", "veteran_status", "disability_status"}

# Semantic types that require LLM generation grounded in candidate context
_LLM_GENERATED = {"custom_essay"}


@dataclass
class FieldResolution:
    semantic_type: str
    value: str | None
    source: ResolutionSource
    confidence: float
    evidence: str
    human_hint: str | None = None  # hint shown when source=HUMAN_REQUIRED


class CandidateKnowledgeResolver:
    """Resolves semantic field types to candidate-sourced values.

    Never invents data — all resolutions are traceable to the candidate record.
    """

    def __init__(self, llm_model: str = "claude-haiku-4-5-20251001"):
        self._llm_model = llm_model

    async def resolve(
        self,
        semantic_type: str,
        field_label: str,
        field_options: list[str] | None,
        candidate: Candidate,
        profile: CandidateProfile | None,
        application: Application,
    ) -> FieldResolution:
        """Resolve a semantic field type to a candidate-sourced value."""
        # Always-human fields
        if semantic_type in _ALWAYS_HUMAN:
            return FieldResolution(
                semantic_type=semantic_type,
                value=None,
                source="HUMAN_REQUIRED",
                confidence=1.0,
                evidence=f"'{semantic_type}' always requires human input",
                human_hint=f"Please provide your {field_label.lower()}",
            )

        resolver = getattr(self, f"_resolve_{semantic_type}", None)
        if resolver:
            return await resolver(
                field_label=field_label,
                field_options=field_options,
                candidate=candidate,
                profile=profile,
                application=application,
            )

        # Unknown semantic type → HUMAN_REQUIRED
        return FieldResolution(
            semantic_type=semantic_type,
            value=None,
            source="HUMAN_REQUIRED",
            confidence=0.5,
            evidence=f"No resolver for semantic type '{semantic_type}'",
            human_hint=f"Please provide: {field_label}",
        )

    # ── Direct resolvers ──────────────────────────────────────────────────────

    async def _resolve_full_name(self, *, candidate: Candidate, **_) -> FieldResolution:
        if candidate.name:
            return FieldResolution("full_name", candidate.name, "DIRECT", 0.98, "candidate.name")
        return FieldResolution("full_name", None, "HUMAN_REQUIRED", 1.0, "candidate.name is empty", "Your full name")

    async def _resolve_first_name(self, *, candidate: Candidate, **_) -> FieldResolution:
        if candidate.name:
            first = candidate.name.strip().split()[0]
            return FieldResolution("first_name", first, "COMPUTED", 0.95, f"split(candidate.name)[0] = '{first}'")
        return FieldResolution("first_name", None, "HUMAN_REQUIRED", 1.0, "candidate.name is empty", "Your first name")

    async def _resolve_last_name(self, *, candidate: Candidate, **_) -> FieldResolution:
        if candidate.name:
            parts = candidate.name.strip().split()
            if len(parts) >= 2:
                last = parts[-1]
                return FieldResolution("last_name", last, "COMPUTED", 0.95, f"split(candidate.name)[-1] = '{last}'")
        return FieldResolution("last_name", None, "HUMAN_REQUIRED", 1.0, "candidate.name missing or single word", "Your last name")

    async def _resolve_email(self, *, candidate: Candidate, **_) -> FieldResolution:
        if candidate.email:
            return FieldResolution("email", candidate.email, "DIRECT", 0.99, "candidate.email")
        return FieldResolution("email", None, "HUMAN_REQUIRED", 1.0, "candidate.email is empty", "Your email address")

    async def _resolve_phone(self, **_) -> FieldResolution:
        return FieldResolution("phone", None, "HUMAN_REQUIRED", 1.0, "phone always requires human input", "Your phone number")

    async def _resolve_location(self, *, candidate: Candidate, **_) -> FieldResolution:
        if candidate.location:
            return FieldResolution("location", candidate.location, "DIRECT", 0.97, "candidate.location")
        return FieldResolution("location", None, "HUMAN_REQUIRED", 0.9, "candidate.location is empty", "Your current location")

    async def _resolve_linkedin_url(self, *, candidate: Candidate, **_) -> FieldResolution:
        for src in (candidate.sources or []):
            if src.source_type == "linkedin" and src.source_url:
                return FieldResolution("linkedin_url", src.source_url, "DIRECT", 0.99, f"candidate_sources[type=linkedin].source_url")
        return FieldResolution("linkedin_url", None, "HUMAN_REQUIRED", 0.9, "no LinkedIn source found", "Your LinkedIn profile URL")

    async def _resolve_portfolio_url(self, *, candidate: Candidate, **_) -> FieldResolution:
        for src in (candidate.sources or []):
            if src.source_type == "portfolio" and src.source_url:
                return FieldResolution("portfolio_url", src.source_url, "DIRECT", 0.99, "candidate_sources[type=portfolio].source_url")
        return FieldResolution("portfolio_url", None, "HUMAN_REQUIRED", 0.8, "no portfolio source found", "Your portfolio URL (optional)")

    async def _resolve_github_url(self, *, candidate: Candidate, **_) -> FieldResolution:
        for src in (candidate.sources or []):
            if src.source_type == "github" and src.source_url:
                return FieldResolution("github_url", src.source_url, "DIRECT", 0.99, "candidate_sources[type=github].source_url")
        return FieldResolution("github_url", None, "HUMAN_REQUIRED", 0.8, "no GitHub source found", "Your GitHub profile URL (optional)")

    async def _resolve_work_authorization(
        self, *, candidate: Candidate, field_options: list[str] | None, **_
    ) -> FieldResolution:
        if not candidate.work_authorization:
            return FieldResolution("work_authorization", None, "HUMAN_REQUIRED", 1.0, "candidate.work_authorization is empty", "Your work authorization status")

        raw = candidate.work_authorization
        # Map candidate values to common form option patterns
        value = _match_select_option(raw, field_options) or raw
        return FieldResolution("work_authorization", value, "DIRECT", 0.95, f"candidate.work_authorization = '{raw}'")

    async def _resolve_salary_expectation(self, *, candidate: Candidate, **_) -> FieldResolution:
        if candidate.salary_min_usd:
            return FieldResolution("salary_expectation", str(candidate.salary_min_usd), "DIRECT", 0.90, f"candidate.salary_min_usd = {candidate.salary_min_usd}")
        return FieldResolution("salary_expectation", None, "HUMAN_REQUIRED", 0.9, "candidate.salary_min_usd is empty", "Your expected salary (USD/year)")

    async def _resolve_years_experience(
        self, *, profile: CandidateProfile | None, field_options: list[str] | None, **_
    ) -> FieldResolution:
        total = _compute_total_years(profile)
        if total is None:
            return FieldResolution("years_experience", None, "HUMAN_REQUIRED", 0.8, "no experience data in profile", "Your total years of experience")

        bucket = _years_to_bucket(total)
        value = _match_select_option(bucket, field_options) or bucket
        return FieldResolution(
            "years_experience", value, "COMPUTED", 0.85,
            f"sum(experience.duration_years) = {total:.1f} → bucket '{bucket}'",
        )

    async def _resolve_current_company(self, *, profile: CandidateProfile | None, **_) -> FieldResolution:
        company = _get_current_company(profile)
        if company:
            return FieldResolution("current_company", company, "COMPUTED", 0.90, f"profile.experience[0].company = '{company}'")
        return FieldResolution("current_company", None, "HUMAN_REQUIRED", 0.8, "no experience in profile", "Your current company")

    async def _resolve_current_title(self, *, profile: CandidateProfile | None, **_) -> FieldResolution:
        title = _get_current_title(profile)
        if title:
            return FieldResolution("current_title", title, "COMPUTED", 0.90, f"profile.experience[0].title = '{title}'")
        return FieldResolution("current_title", None, "HUMAN_REQUIRED", 0.8, "no experience in profile", "Your current job title")

    async def _resolve_availability(self, *, candidate: Candidate, **_) -> FieldResolution:
        if candidate.availability:
            return FieldResolution("availability", candidate.availability, "DIRECT", 0.92, "candidate.availability")
        return FieldResolution("availability", None, "HUMAN_REQUIRED", 0.9, "candidate.availability is empty", "When can you start?")

    async def _resolve_cover_letter(
        self, *, application: Application, **_
    ) -> FieldResolution:
        letters = sorted(application.cover_letters or [], key=lambda c: c.created_at, reverse=True)
        if letters:
            return FieldResolution("cover_letter", letters[0].content, "DIRECT", 0.97, "application.cover_letters[-1].content")
        return FieldResolution("cover_letter", None, "HUMAN_REQUIRED", 0.9, "no cover letter generated yet", "Your cover letter text")

    async def _resolve_cv_file(self, **_) -> FieldResolution:
        # cv_file path is resolved externally by cv_storage service
        return FieldResolution("cv_file", None, "HUMAN_REQUIRED", 1.0, "cv_file requires a file path set by cv_storage", "Upload your CV/resume PDF")

    async def _resolve_custom_essay(
        self,
        *,
        field_label: str,
        candidate: Candidate,
        profile: CandidateProfile | None,
        application: Application,
        **_,
    ) -> FieldResolution:
        context = _build_candidate_context(candidate, profile)
        if not context:
            return FieldResolution(
                "custom_essay", None, "HUMAN_REQUIRED", 1.0,
                "no candidate context to generate essay", f"Please answer: {field_label}",
            )

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            msg = await client.messages.create(
                model=self._llm_model,
                max_tokens=300,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Write a concise, honest answer (2-4 sentences) for this application question: "
                            f'"{field_label}"\n\n'
                            f"Candidate context (use ONLY this information — do not invent):\n{context}\n\n"
                            f"Answer in first person. Be specific and grounded in the candidate's actual background."
                        ),
                    }
                ],
            )
            answer = msg.content[0].text.strip()
            logger.info("custom_essay_generated", label=field_label, chars=len(answer))
            return FieldResolution(
                "custom_essay", answer, "GENERATED", 0.70,
                f"LLM({self._llm_model}) grounded in candidate context ({len(context)} chars)",
            )
        except Exception as exc:
            logger.warning("custom_essay_llm_failed", error=str(exc))
            return FieldResolution(
                "custom_essay", None, "HUMAN_REQUIRED", 1.0,
                f"LLM call failed: {exc}", f"Please answer: {field_label}",
            )

    async def _resolve_start_date(self, *, candidate: Candidate, **_) -> FieldResolution:
        avail_map = {
            "immediate": "Immediately",
            "two_weeks": "2 weeks notice",
            "one_month": "1 month notice",
            "three_months": "3 months notice",
        }
        if candidate.availability and candidate.availability in avail_map:
            return FieldResolution("start_date", avail_map[candidate.availability], "COMPUTED", 0.80, f"candidate.availability = '{candidate.availability}'")
        return FieldResolution("start_date", None, "HUMAN_REQUIRED", 0.9, "no availability data", "When can you start?")

    async def _resolve_education_level(
        self, *, profile: CandidateProfile | None, field_options: list[str] | None, **_
    ) -> FieldResolution:
        level = _get_highest_education(profile)
        if level:
            value = _match_select_option(level, field_options) or level
            return FieldResolution("education_level", value, "COMPUTED", 0.85, f"highest degree from profile.education = '{level}'")
        return FieldResolution("education_level", None, "HUMAN_REQUIRED", 0.8, "no education data in profile", "Your highest education level")

    async def _resolve_graduation_year(self, *, profile: CandidateProfile | None, **_) -> FieldResolution:
        year = _get_graduation_year(profile)
        if year:
            return FieldResolution("graduation_year", str(year), "COMPUTED", 0.85, f"profile.education[-1].end_year = {year}")
        return FieldResolution("graduation_year", None, "HUMAN_REQUIRED", 0.8, "no education data", "Your graduation year")


# ── Private helpers ───────────────────────────────────────────────────────────

def _compute_total_years(profile: CandidateProfile | None) -> float | None:
    if not profile or not profile.experience:
        return None
    total = 0.0
    for exp in profile.experience:
        if isinstance(exp, dict):
            total += float(exp.get("duration_years") or exp.get("years", 0) or 0)
    return total if total > 0 else None


def _years_to_bucket(years: float) -> str:
    if years <= 2:
        return "0-2"
    elif years <= 5:
        return "3-5"
    elif years <= 10:
        return "6-10"
    return "10+"


def _get_current_company(profile: CandidateProfile | None) -> str | None:
    if not profile or not profile.experience:
        return None
    exp = profile.experience[0] if isinstance(profile.experience, list) else None
    if exp and isinstance(exp, dict):
        return exp.get("company")
    return None


def _get_current_title(profile: CandidateProfile | None) -> str | None:
    if not profile or not profile.experience:
        return None
    exp = profile.experience[0] if isinstance(profile.experience, list) else None
    if exp and isinstance(exp, dict):
        return exp.get("role") or exp.get("title")
    return None


def _get_highest_education(profile: CandidateProfile | None) -> str | None:
    if not profile or not profile.education:
        return None
    degree_rank = {
        "phd": 5, "doctorate": 5, "doctor": 5,
        "master": 4, "msc": 4, "mba": 4, "ms": 4, "ma": 4,
        "bachelor": 3, "bsc": 3, "bs": 3, "ba": 3, "b.s": 3, "b.a": 3,
        "associate": 2,
        "diploma": 1, "certificate": 1,
    }
    best = None
    best_rank = -1
    for edu in profile.education:
        if not isinstance(edu, dict):
            continue
        degree = (edu.get("degree") or "").lower()
        for key, rank in degree_rank.items():
            if key in degree:
                if rank > best_rank:
                    best_rank = rank
                    best = edu.get("degree")
                break
    return best


def _get_graduation_year(profile: CandidateProfile | None) -> int | None:
    if not profile or not profile.education:
        return None
    latest = None
    for edu in profile.education:
        if not isinstance(edu, dict):
            continue
        year_str = edu.get("end_year") or edu.get("year")
        try:
            year = int(str(year_str))
            if latest is None or year > latest:
                latest = year
        except (TypeError, ValueError):
            pass
    return latest


def _match_select_option(value: str, options: list[str] | None) -> str | None:
    """Find the best matching option from a select field's option list.

    Matches by value prefix or contained substring (case-insensitive).
    Returns None if options is empty or no match found.
    """
    if not options or not value:
        return None
    v = value.lower().strip()
    # Exact match first
    for opt in options:
        if opt.lower().strip() == v:
            return opt
    # Prefix match (e.g. "0-2" matches "0-2 years" or "0–2 years")
    v_clean = re.sub(r"[^a-z0-9]", "", v)
    for opt in options:
        opt_clean = re.sub(r"[^a-z0-9]", "", opt.lower())
        if opt_clean.startswith(v_clean) or v_clean.startswith(opt_clean):
            return opt
    # Substring match — only for tokens long enough to avoid false positives
    for opt in options:
        opt_lower = opt.lower()
        if len(opt_lower) >= 3 and opt_lower in v:
            return opt
        if len(v) >= 3 and v in opt_lower:
            return opt
    return None


def _build_candidate_context(candidate: Candidate, profile: CandidateProfile | None) -> str:
    """Build a brief, factual candidate context string for LLM grounding."""
    lines = []
    if candidate.name:
        lines.append(f"Name: {candidate.name}")
    if candidate.location:
        lines.append(f"Location: {candidate.location}")
    if profile:
        if profile.summary:
            lines.append(f"Summary: {profile.summary[:300]}")
        if profile.experience:
            exp_lines = []
            for exp in (profile.experience or [])[:3]:
                if isinstance(exp, dict):
                    title = exp.get("role") or exp.get("title", "")
                    company = exp.get("company", "")
                    exp_lines.append(f"  - {title} at {company}")
            if exp_lines:
                lines.append("Experience:\n" + "\n".join(exp_lines))
        if profile.skills:
            if isinstance(profile.skills, list):
                skills_flat = profile.skills[:10]
            elif isinstance(profile.skills, dict):
                skills_flat = [s for lst in profile.skills.values() for s in (lst or [])][:10]
            else:
                skills_flat = []
            if skills_flat:
                lines.append(f"Skills: {', '.join(str(s) for s in skills_flat)}")
        if candidate.career_goals:
            lines.append(f"Career goals: {candidate.career_goals[:200]}")
    return "\n".join(lines)
