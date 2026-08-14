"""Profile Optimizer: generate actionable improvement tips from match history.

Reads all MatchAnalysis rows for a candidate, aggregates which skills appear
most often in missing_skills, then uses an LLM to produce a prioritized
improvement plan.
"""
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class SkillGap:
    skill: str
    frequency: int  # how many job matches flagged this skill as missing
    tiers: list[str] = field(default_factory=list)  # which tiers it appeared in


@dataclass
class ProfileOptimizationTip:
    priority: int       # 1 = highest
    category: str       # "skill", "experience", "summary", "profile_completeness"
    tip: str
    evidence: str       # why this tip was generated
    impact: str         # "high" | "medium" | "low"


@dataclass
class OptimizationReport:
    total_analyses_reviewed: int
    top_skill_gaps: list[SkillGap]
    tips: list[ProfileOptimizationTip]
    summary: str


def _aggregate_skill_gaps(analyses: list[dict]) -> list[SkillGap]:
    """Count how often each skill appears in missing_skills across all matches."""
    skill_counter: Counter[str] = Counter()
    skill_tiers: dict[str, list[str]] = {}

    for analysis in analyses:
        tier = analysis.get("match_tier", "unknown")
        for skill in (analysis.get("missing_skills") or []):
            if isinstance(skill, str) and skill.strip():
                normalized = skill.strip().lower()
                skill_counter[normalized] += 1
                skill_tiers.setdefault(normalized, []).append(tier)

    return [
        SkillGap(skill=skill, frequency=count, tiers=skill_tiers.get(skill, []))
        for skill, count in skill_counter.most_common(20)
    ]


def _deterministic_tips(
    skill_gaps: list[SkillGap],
    profile_data: dict,
) -> list[ProfileOptimizationTip]:
    """Generate improvement tips from skill gaps without LLM."""
    tips: list[ProfileOptimizationTip] = []
    priority = 1

    # Top missing skills
    for gap in skill_gaps[:5]:
        tiers_str = ", ".join(sorted(set(gap.tiers))) if gap.tiers else "multiple"
        tips.append(ProfileOptimizationTip(
            priority=priority,
            category="skill",
            tip=f"Add '{gap.skill}' to your skills — it appeared in {gap.frequency} job analyses as a gap.",
            evidence=f"Missing in {gap.frequency} match analyses (tiers: {tiers_str}).",
            impact="high" if gap.frequency >= 3 else "medium",
        ))
        priority += 1

    # Check profile completeness
    if not profile_data.get("summary"):
        tips.append(ProfileOptimizationTip(
            priority=priority,
            category="profile_completeness",
            tip="Add a professional summary to your profile to improve match quality.",
            evidence="Profile summary is empty — the matching engine uses it for LLM reasoning.",
            impact="high",
        ))
        priority += 1

    if not profile_data.get("experience"):
        tips.append(ProfileOptimizationTip(
            priority=priority,
            category="experience",
            tip="Add your work experience to unlock accurate experience and seniority scoring.",
            evidence="No experience records found in profile.",
            impact="high",
        ))
        priority += 1

    if not profile_data.get("skills"):
        tips.append(ProfileOptimizationTip(
            priority=priority,
            category="profile_completeness",
            tip="Add your technical skills to improve ATS keyword matching.",
            evidence="Skills list is empty — this directly lowers the deterministic match score.",
            impact="high",
        ))
        priority += 1

    return tips


async def generate_optimization_report(
    analyses: list[dict],
    profile_data: dict,
    model: str = "claude-haiku-4-5-20251001",
) -> OptimizationReport:
    """Generate a full optimization report.

    Uses deterministic tips first; enriches with LLM summary if available.
    """
    skill_gaps = _aggregate_skill_gaps(analyses)
    tips = _deterministic_tips(skill_gaps, profile_data)

    # Build a short LLM summary if we have enough data
    summary = _default_summary(len(analyses), skill_gaps, tips)
    if analyses and skill_gaps:
        try:
            summary = await _llm_summary(analyses, skill_gaps, tips, model)
        except Exception:
            pass  # fallback to deterministic summary

    return OptimizationReport(
        total_analyses_reviewed=len(analyses),
        top_skill_gaps=skill_gaps[:10],
        tips=tips,
        summary=summary,
    )


def _default_summary(
    total: int,
    skill_gaps: list[SkillGap],
    tips: list[ProfileOptimizationTip],
) -> str:
    if total == 0:
        return "No match analyses found yet. Run match analysis on some jobs first to get personalized tips."
    if not skill_gaps:
        return f"Reviewed {total} job match(es). No consistent skill gaps detected — your profile looks well-rounded."
    top = skill_gaps[0].skill
    return (
        f"Reviewed {total} job match(es). "
        f"Top gap: '{top}' (missing in {skill_gaps[0].frequency} analyses). "
        f"Found {len(tips)} improvement tip(s)."
    )


async def _llm_summary(
    analyses: list[dict],
    skill_gaps: list[SkillGap],
    tips: list[ProfileOptimizationTip],
    model: str,
) -> str:
    import anthropic
    from app.core.config import settings

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    gaps_text = ", ".join(f"{g.skill} ({g.frequency}x)" for g in skill_gaps[:8])
    tips_text = "\n".join(f"- {t.tip}" for t in tips[:5])

    resp = await client.messages.create(
        model=model,
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": (
                f"A candidate has {len(analyses)} job match analyses. "
                f"Top skill gaps (skill: frequency): {gaps_text}. "
                f"Generated tips:\n{tips_text}\n\n"
                f"Write a 2-sentence actionable summary for the candidate. Be direct and specific."
            ),
        }],
    )
    return resp.content[0].text.strip()
