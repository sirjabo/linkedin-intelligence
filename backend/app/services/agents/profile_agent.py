"""ProfileAgent: extracts and consolidates candidate profile from raw sources.

Uses structured output (tool_use) — never XML tag parsing.
"""
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.sanitize import sanitize_for_prompt
from app.services.ai.model_router import route_model
from app.services.ai.provider import LLMProvider, default_provider

logger = get_logger(__name__)

MODEL_EXTRACT = route_model("simple_extract")
MODEL_CONSOLIDATE = route_model("profile_consolidate")


# ── Output schemas ────────────────────────────────────────────────────────────

class EvidenceRef(BaseModel):
    claim: str
    evidence_type: str = Field(description="experience | skill | project | education | achievement")
    source_text: str
    strength: float = Field(ge=0.0, le=1.0)


class SkillExtracted(BaseModel):
    canonical_name: str
    category: str = Field(description="language | framework | cloud | database | tool | domain | soft")
    proficiency: str = Field(description="beginner | intermediate | advanced | expert")
    years_estimated: float | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class ExperienceExtracted(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str
    location: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    industry: str | None = None
    seniority: str | None = None


class EducationExtracted(BaseModel):
    institution: str
    degree: str
    field: str | None = None
    year: str | None = None
    gpa: str | None = None


class ProjectExtracted(BaseModel):
    name: str
    description: str
    technologies: list[str] = Field(default_factory=list)
    outcome: str | None = None
    url: str | None = None


class CertificationExtracted(BaseModel):
    name: str
    issuer: str
    year: str | None = None
    url: str | None = None


class AchievementExtracted(BaseModel):
    description: str
    metric: str | None = None
    context: str | None = None
    impact: str | None = None


class ExtractedProfile(BaseModel):
    """Structured profile extracted from a single candidate source."""
    name: str | None = None
    email: str | None = None
    location: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    summary: str | None = None
    career_level: str | None = Field(
        None,
        description="intern | junior | mid | senior | staff | principal | lead | manager | director | vp | c-level"
    )
    target_role: str | None = None
    industries: list[str] = Field(default_factory=list)
    skills: list[SkillExtracted] = Field(default_factory=list)
    experience: list[ExperienceExtracted] = Field(default_factory=list)
    education: list[EducationExtracted] = Field(default_factory=list)
    projects: list[ProjectExtracted] = Field(default_factory=list)
    certifications: list[CertificationExtracted] = Field(default_factory=list)
    achievements: list[AchievementExtracted] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class ProfileConflict(BaseModel):
    field: str
    values: list[dict] = Field(description="Each dict has 'source' and 'value' keys")
    recommendation: str


class ConsolidatedProfile(BaseModel):
    """Consolidated profile from multiple sources."""
    summary: str | None = None
    career_level: str | None = None
    professional_identity: dict = Field(default_factory=dict)
    industries: list[str] = Field(default_factory=list)
    competencies: list[str] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    certifications: list[dict] = Field(default_factory=list)
    achievements: list[dict] = Field(default_factory=list)
    conflicts: list[ProfileConflict] = Field(default_factory=list)


# ── System prompts ─────────────────────────────────────────────────────────────

EXTRACT_SYSTEM = """You are an expert at extracting structured professional profile data from resumes and profiles.

Extract all information present in the text. Follow these rules:
- NEVER invent data. If a field is not present, leave it null or empty.
- For skills, include only skills explicitly mentioned or clearly demonstrated, with realistic proficiency levels.
- For experience dates, use the format from the source (don't normalize).
- For achievements, include only quantified or specific outcomes mentioned in the text.
- Set extraction_confidence based on text quality: 1.0 = clear professional document, 0.5 = informal text with gaps.
- evidence.source_text must be a verbatim quote from the input text.

Never hallucinate. Never add skills not in the text."""

CONSOLIDATE_SYSTEM = """You are an expert at consolidating multiple professional profile sources into a single coherent profile.

When sources conflict:
- Flag conflicts explicitly in the 'conflicts' array with both values and your recommendation.
- Do NOT silently pick one value over another for date/role/metric disagreements.
- Prefer more specific data (e.g. a specific date over "around 2020").

For the consolidated profile:
- Merge skills from all sources, deduplicating by canonical_name.
- Combine experience entries, matching by company+title+approximate dates.
- Include all unique projects, education, certifications.
- Write a coherent summary synthesizing all sources.
- career_level should reflect the most senior role across all sources."""


# ── Agent functions ───────────────────────────────────────────────────────────

async def extract_from_source(
    raw_text: str,
    source_type: str = "cv",
    provider: LLMProvider = default_provider,
) -> ExtractedProfile:
    """Extract structured profile data from a single source text."""
    clean_text, injection_detected = sanitize_for_prompt(raw_text, max_length=12000, field_name=source_type)
    if injection_detected:
        logger.warning("profile_agent.injection_detected", source_type=source_type, text_length=len(raw_text))
    logger.info("profile_agent.extract_start", source_type=source_type, text_length=len(raw_text))
    result = await provider.structured_output(
        system=EXTRACT_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Extract profile data from this {source_type}:\n\n{clean_text}"
        }],
        schema=ExtractedProfile,
        model=MODEL_EXTRACT,
    )
    logger.info(
        "profile_agent.extract_done",
        source_type=source_type,
        skills_found=len(result.skills),
        experience_found=len(result.experience),
        confidence=result.extraction_confidence,
    )
    return result


async def consolidate_profiles(
    extracted_profiles: list[tuple[str, ExtractedProfile]],
    provider: LLMProvider = default_provider,
) -> ConsolidatedProfile:
    """Consolidate multiple extracted profiles into one master profile.

    Args:
        extracted_profiles: List of (source_type, profile) tuples
    """
    if len(extracted_profiles) == 1:
        _source_type, profile = extracted_profiles[0]
        return _single_to_consolidated(profile)

    sources_text = "\n\n".join(
        f"=== Source: {stype} ===\n{profile.model_dump_json(indent=2)}"
        for stype, profile in extracted_profiles
    )

    logger.info("profile_agent.consolidate_start", source_count=len(extracted_profiles))
    result = await provider.structured_output(
        system=CONSOLIDATE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Consolidate these {len(extracted_profiles)} profile sources into one master profile:\n\n{sources_text[:15000]}"
        }],
        schema=ConsolidatedProfile,
        model=MODEL_CONSOLIDATE,
    )
    logger.info(
        "profile_agent.consolidate_done",
        conflicts_found=len(result.conflicts),
        skills_merged=len(result.skills),
    )
    return result


def _single_to_consolidated(profile: ExtractedProfile) -> ConsolidatedProfile:
    """Convert a single ExtractedProfile to ConsolidatedProfile without LLM call."""
    return ConsolidatedProfile(
        summary=profile.summary,
        career_level=profile.career_level,
        professional_identity={
            "name": profile.name,
            "email": profile.email,
            "location": profile.location,
            "target_role": profile.target_role,
            "linkedin_url": profile.linkedin_url,
            "github_url": profile.github_url,
        },
        industries=profile.industries,
        competencies=[s.canonical_name for s in profile.skills if s.category in ("domain", "soft")],
        skills=[s.model_dump() for s in profile.skills],
        experience=[e.model_dump() for e in profile.experience],
        education=[e.model_dump() for e in profile.education],
        projects=[p.model_dump() for p in profile.projects],
        certifications=[c.model_dump() for c in profile.certifications],
        achievements=[a.model_dump() for a in profile.achievements],
        conflicts=[],
    )
