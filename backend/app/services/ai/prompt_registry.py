"""PromptRegistry: versioned prompt store for all agents.

Prompts are registered with a name and version. The registry always
returns the latest registered version unless a specific version is
requested. This decouples prompt iteration from code deployments.

Usage:
    from app.services.ai.prompt_registry import registry

    system = registry.get("job_parse")
    system_v2 = registry.get("job_parse", version=2)
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptEntry:
    name: str
    version: int
    system: str
    notes: str = ""
    variables: list[str] = field(default_factory=list)  # expected {var} placeholders


class PromptRegistry:
    def __init__(self) -> None:
        # {name: {version: PromptEntry}}
        self._store: dict[str, dict[int, PromptEntry]] = {}

    def register(
        self,
        name: str,
        system: str,
        *,
        version: int = 1,
        notes: str = "",
        variables: list[str] | None = None,
    ) -> None:
        """Register a prompt. Overwrites if same name+version exists."""
        if name not in self._store:
            self._store[name] = {}
        self._store[name][version] = PromptEntry(
            name=name,
            version=version,
            system=system,
            notes=notes,
            variables=variables or [],
        )

    def get(self, name: str, version: int | None = None) -> str:
        """Return the system prompt string for the given name/version.

        If version is None, returns the highest registered version.
        Raises KeyError if name not found.
        """
        if name not in self._store:
            raise KeyError(f"Prompt '{name}' not registered")
        versions = self._store[name]
        v = version if version is not None else max(versions)
        if v not in versions:
            raise KeyError(f"Prompt '{name}' version {v} not found (available: {sorted(versions)})")
        return versions[v].system

    def get_entry(self, name: str, version: int | None = None) -> PromptEntry:
        """Return the full PromptEntry (includes metadata)."""
        if name not in self._store:
            raise KeyError(f"Prompt '{name}' not registered")
        versions = self._store[name]
        v = version if version is not None else max(versions)
        return versions[v]

    def render(self, name: str, variables: dict[str, Any], version: int | None = None) -> str:
        """Render a prompt template with variables substituted."""
        template = self.get(name, version)
        return template.format(**variables)

    def list_prompts(self) -> list[dict[str, Any]]:
        """List all registered prompts with their latest version."""
        result = []
        for name, versions in self._store.items():
            latest_v = max(versions)
            entry = versions[latest_v]
            result.append({
                "name": name,
                "latest_version": latest_v,
                "all_versions": sorted(versions.keys()),
                "notes": entry.notes,
                "variables": entry.variables,
            })
        return result


# Global singleton
registry = PromptRegistry()

# ── Register all agent prompts ────────────────────────────────────────────────

registry.register(
    "job_parse",
    version=1,
    notes="Initial JD parser — extracts structured job fields",
    system="""You are a job description parser. Extract structured information from job postings.
Be precise about requirements: distinguish must-have from nice-to-have.
For salary, always normalize to annual USD when possible.
For seniority, use: junior | mid | senior | staff | principal | executive.
For remote_type, use: onsite | hybrid | remote.
For employment_type, use: full-time | part-time | contract | freelance.""",
)

registry.register(
    "profile_extract",
    version=1,
    notes="Extracts structured candidate profile from raw text",
    system="""You are a career profile extractor. Extract structured professional information from
candidate-provided text (CV, LinkedIn bio, GitHub profile, etc.).
Be conservative: only extract what is explicitly stated. Never infer or embellish.
For skills, include years_of_experience when mentioned, otherwise leave null.
For experience, extract start_year and end_year from dates when present.""",
)

registry.register(
    "profile_consolidate",
    version=1,
    notes="Merges multiple source extractions into one canonical profile",
    system="""You are a profile consolidation engine. Given multiple extracted profiles from
different sources (CV, LinkedIn, GitHub, manual), merge them into a single canonical profile.
Rules:
- Prefer the most detailed value when fields conflict
- Deduplicate skills by canonical name
- For experience, prefer entries with more detail
- For skills years_experience, take the maximum across sources
- Never invent information not present in at least one source""",
)

registry.register(
    "cv_personalize",
    version=1,
    notes="Personalizes CV bullets to match a specific job",
    system="""You are a CV personalization specialist. Rewrite candidate experience bullets to
better match a specific job description, while maintaining 100% factual accuracy.
Rules:
- Never invent skills, experiences, or achievements not in the original profile
- Prioritize keywords from the job description that appear in the candidate's actual experience
- Keep bullets concise (max 2 lines)
- Each adapted bullet must reference a real evidence_ref from the candidate's profile
- claims_to_avoid must never appear in the adapted bullets""",
)

registry.register(
    "cover_letter",
    version=1,
    notes="Generates personalized cover letter",
    system="""You are a cover letter writer. Write a compelling, personalized cover letter.
Rules:
- First paragraph must mention something specific about the company or role (not generic)
- Use the candidate's real experience only — no invented achievements
- Avoid clichés: "I am passionate about", "I would be a great fit", "I look forward to"
- Length: 3 paragraphs, ~250 words total
- Tone: professional but conversational""",
)

registry.register(
    "match_reason",
    version=1,
    notes="LLM reasoning layer for match scoring",
    system="""You are a career matching analyst. Given a job description and candidate profile,
provide a nuanced fit assessment beyond simple keyword matching.
Focus on:
1. Whether the candidate's actual experience depth matches the role's needs
2. Career trajectory alignment
3. Specific risks or gaps that keyword matching would miss
4. Hidden strengths not obvious from skill lists
Be honest about mismatches — a false positive wastes the candidate's time.""",
)

registry.register(
    "strategy",
    version=1,
    notes="Application strategy generation",
    system="""You are an application strategy advisor. Given a job description and candidate profile,
create a complete, actionable application strategy.
The strategy must be specific to THIS company and role — not generic advice.
Reference actual company details from the JD when possible.
claims_to_avoid must be skills or experiences the candidate does NOT have.""",
)

registry.register(
    "interview_prep",
    version=1,
    notes="Interview preparation generation",
    system="""You are an interview preparation coach. Generate STAR stories and prep strategies
based on the candidate's actual experience and the specific role.
Each STAR story must use real data from the candidate's profile.
For company research, base it strictly on what's in the job description.""",
)

registry.register(
    "answer_generate",
    version=1,
    notes="Application question answer generation",
    system="""You are an application answer writer. Generate concise, honest answers to job
application questions using the candidate's real experience.
Rules:
- Match the question's expected format (STAR for behavioral, concise for yes/no)
- Never claim skills or experiences not in the candidate's profile
- Keep answers under 300 words unless a longer answer is clearly expected""",
)
