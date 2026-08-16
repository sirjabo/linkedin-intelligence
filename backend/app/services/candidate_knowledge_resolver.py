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
from app.db.models.application import Application
from app.db.models.candidate import Candidate, CandidateProfile

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


@dataclass
class DateRange:
    start_year: float | None
    end_year: float | None  # None = present

    def duration_years(self) -> float:
        import datetime
        end = self.end_year or datetime.datetime.utcnow().year
        start = self.start_year or end
        return max(0.0, end - start)


def _parse_year(s: str | None) -> float | None:
    if not s:
        return None
    s = str(s).strip()
    # Accept "2018", "2018-01", "2018-01-15", "Jan 2018"
    for fmt in ("%Y", "%Y-%m", "%Y-%m-%d"):
        try:
            import datetime
            return float(datetime.datetime.strptime(s[:len(fmt.replace("%Y","0000").replace("%m","00").replace("%d","00"))], fmt).year)
        except ValueError:
            pass
    # Try extracting 4-digit year anywhere in string
    m = re.search(r"\b(19|20)\d{2}\b", s)
    return float(m.group()) if m else None


def _deduplicate_periods(periods: list[DateRange]) -> float:
    """Sum years across periods, merging overlapping spans to avoid double counting."""
    if not periods:
        return 0.0
    import datetime
    current_year = float(datetime.datetime.utcnow().year)
    resolved = sorted(
        [(p.start_year or 0.0, p.end_year or current_year) for p in periods],
        key=lambda t: t[0],
    )
    merged: list[tuple[float, float]] = []
    for start, end in resolved:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return sum(end - start for start, end in merged)


class CandidateKnowledgeResolver:
    """Resolves semantic field types to candidate-sourced values.

    Never invents data — all resolutions are traceable to the candidate record.
    """

    def __init__(self, llm_model: str = "claude-haiku-4-5-20251001"):
        self._llm_model = llm_model
        self._cache: dict[str, FieldResolution] = {}

    async def resolve(
        self,
        semantic_type: str,
        field_label: str,
        field_options: list[str] | None,
        candidate: Candidate,
        profile: CandidateProfile | None,
        application: Application,
        skill_target: str | None = None,
    ) -> FieldResolution:
        """Resolve a semantic field type to a candidate-sourced value.

        Results are cached per (semantic_type, field_label, skill_target) within this
        resolver instance so repeated calls in the same application context are free.
        """
        cache_key = f"{semantic_type}|{field_label}|{skill_target or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = await self._resolve_uncached(
            semantic_type=semantic_type,
            field_label=field_label,
            field_options=field_options,
            candidate=candidate,
            profile=profile,
            application=application,
            skill_target=skill_target,
        )
        self._cache[cache_key] = result
        return result

    def clear_cache(self) -> None:
        self._cache.clear()

    async def _resolve_uncached(
        self,
        semantic_type: str,
        field_label: str,
        field_options: list[str] | None,
        candidate: Candidate,
        profile: CandidateProfile | None,
        application: Application,
        skill_target: str | None = None,
    ) -> FieldResolution:
        """Internal resolver without cache."""
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
                skill_target=skill_target,
            )

        # Unknown semantic type — try FROM_KB before falling back to HUMAN_REQUIRED
        kb_value = _resolve_from_kb(field_label, application)
        if kb_value:
            logger.info("unknown_field_from_kb", semantic_type=semantic_type, label=field_label)
            return FieldResolution(
                semantic_type=semantic_type,
                value=kb_value,
                source="FROM_KB",
                confidence=0.75,
                evidence=f"matched ApplicationAnswer or CoverLetter for label '{field_label}'",
            )

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
                return FieldResolution("linkedin_url", src.source_url, "DIRECT", 0.99, "candidate_sources[type=linkedin].source_url")
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
        # FROM_KB: check previously generated/stored answers before calling LLM
        kb_value = _resolve_from_kb(field_label, application)
        if kb_value:
            logger.info("custom_essay_from_kb", label=field_label, chars=len(kb_value))
            return FieldResolution(
                "custom_essay", kb_value, "FROM_KB", 0.85,
                f"matched ApplicationAnswer or CoverLetter for label '{field_label}'",
            )

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
            _blk = msg.content[0]
            answer = (_blk.text if hasattr(_blk, "text") else "").strip()  # type: ignore[union-attr]
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

    async def _resolve_skill_years(
        self,
        *,
        profile: CandidateProfile | None,
        field_label: str,
        skill_target: str | None = None,
        field_options: list[str] | None = None,
        **_,
    ) -> FieldResolution:
        """Compute years of experience for a specific skill from dated experience entries.

        Deduplicates overlapping periods to avoid inflating the total.
        Falls back to HUMAN_REQUIRED when the skill cannot be found.
        """
        skill = skill_target or _extract_skill_from_label(field_label)
        if not skill:
            return FieldResolution(
                "skill_years", None, "HUMAN_REQUIRED", 0.6,
                "could not determine target skill from field label",
                f"How many years of experience do you have with {field_label}?",
            )

        periods = _extract_skill_periods(skill, profile)
        if not periods:
            return FieldResolution(
                "skill_years", None, "HUMAN_REQUIRED", 0.75,
                f"skill '{skill}' not found in dated experience entries",
                f"How many years of {skill} experience do you have?",
            )

        total = _deduplicate_periods(periods)
        years_str = str(int(total)) if total == int(total) else f"{total:.1f}"
        value = _match_select_option(years_str, field_options) or years_str
        confidence = 0.85 if total > 0 else 0.5
        return FieldResolution(
            "skill_years", value, "COMPUTED", confidence,
            f"found {len(periods)} period(s) with '{skill}' → {total:.1f} deduplicated years",
        )


# ── Private helpers ───────────────────────────────────────────────────────────

_COVER_LETTER_TRIGGERS = {"motivat", "interest", "why", "about yourself", "cover"}


def _resolve_from_kb(field_label: str, application: Application) -> str | None:
    """Check stored ApplicationAnswer and CoverLetter content for a matching answer.

    Deterministic substring match — no LLM involved.
    Returns the matched answer string, or None if no match found.
    """
    label_lower = field_label.lower().strip()

    # 1. Search ApplicationAnswer rows for a question similar to the field label
    for answer in (application.answers or []):
        q_lower = (answer.question or "").lower().strip()
        if not q_lower or not answer.answer:
            continue
        if label_lower in q_lower or q_lower in label_lower:
            return answer.answer

    # 2. Cover letter content for motivation / interest / "why" fields
    if any(trigger in label_lower for trigger in _COVER_LETTER_TRIGGERS):
        letters = sorted(
            (application.cover_letters or []),
            key=lambda c: c.created_at,
            reverse=True,
        )
        if letters and letters[0].content:
            return letters[0].content[:500]

    return None


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


def _extract_skill_from_label(label: str) -> str | None:
    """Extract the target skill name from a form field label.

    Examples:
      "Years of Python experience" → "python"
      "How many years of SQL?" → "sql"
      "React experience (years)" → "react"
    """
    label_lower = label.lower()
    # Pattern: "years of X" / "X experience" / "experience with X"
    patterns = [
        re.compile(r"years?\s+of\s+([a-z][a-z0-9+#.\s/-]{1,30}?)(?:\s+experience|\s*\?|$)", re.IGNORECASE),
        re.compile(r"([a-z][a-z0-9+#.\s/-]{1,30}?)\s+experience\s*\(?years?\)?", re.IGNORECASE),
        re.compile(r"experience\s+(?:with|in)\s+([a-z][a-z0-9+#.\s/-]{1,30}?)(?:\s*\?|$|\s+years?)", re.IGNORECASE),
    ]
    for pat in patterns:
        m = pat.search(label_lower)
        if m:
            return m.group(1).strip().lower()
    return None


def _extract_skill_periods(skill: str, profile: CandidateProfile | None) -> list[DateRange]:
    """Find all dated experience entries that mention the given skill."""
    if not profile or not profile.experience:
        return []

    skill_lower = skill.lower().strip()
    periods: list[DateRange] = []

    # Also check synonyms from the matching engine's synonym groups
    try:
        from app.services.matching.engine import _expand_skill
        skill_synonyms = _expand_skill(skill_lower)
    except Exception:
        skill_synonyms = frozenset({skill_lower})

    for exp in profile.experience:
        if not isinstance(exp, dict):
            continue

        # Check if this experience mentions the skill
        text_to_search = " ".join(filter(None, [
            exp.get("title", ""),
            exp.get("role", ""),
            exp.get("description", ""),
            " ".join(exp.get("bullets", [])) if isinstance(exp.get("bullets"), list) else "",
            " ".join(str(s) for s in (exp.get("technologies") or exp.get("tech") or [])),
        ])).lower()

        skill_mentioned = (
            skill_lower in text_to_search
            or any(syn in text_to_search for syn in skill_synonyms)
        )
        if not skill_mentioned:
            continue

        # Also check skills[] list on the experience entry if present
        exp_skills = [str(s).lower() for s in (exp.get("skills") or [])]
        if exp_skills and not any(
            skill_lower in s or any(syn in s for syn in skill_synonyms)
            for s in exp_skills
        ):
            skill_mentioned = False

        if not skill_mentioned:
            continue

        start = _parse_year(exp.get("start_date") or exp.get("start_year"))
        end = _parse_year(exp.get("end_date") or exp.get("end_year"))
        # "Present" / "current" / None end_date means still active
        end_str = str(exp.get("end_date") or "").lower()
        if end_str in ("present", "current", "now", "", "none"):
            end = None  # will be resolved to current year in deduplicate

        # Fall back to duration_years when dates aren't parseable
        if start is None and end is None:
            dur = float(exp.get("duration_years") or exp.get("years") or 0)
            if dur > 0:
                import datetime
                now = float(datetime.datetime.utcnow().year)
                periods.append(DateRange(start_year=now - dur, end_year=None))
            continue

        periods.append(DateRange(start_year=start, end_year=end))

    return periods


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
