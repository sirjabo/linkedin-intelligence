"""LinkedIn Profile Engine — docs/10-LINKEDIN_ENGINE.md + Sprint 002 brief."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.core.logging import get_logger
from app.engine.ats import ROLE_KEYWORDS

logger = get_logger(__name__)

SECTION_WEIGHTS = {
    "title": 0.25,
    "about": 0.20,
    "skills": 0.20,
    "experience": 0.20,
    "projects": 0.10,
    "education": 0.05,
}

ROLE_TITLE_KEYWORDS: dict[str, list[str]] = {
    "ai_engineer": [
        "ai engineer",
        "llm engineer",
        "genai engineer",
        "applied ai engineer",
        "machine learning engineer",
    ],
    "data_engineer": ["data engineer", "etl engineer", "platform engineer"],
    "analytics_engineer": ["analytics engineer", "data analyst", "bi engineer"],
    "ml_engineer": ["ml engineer", "mlops engineer", "machine learning engineer"],
}

TITLE_VARIANTS: dict[str, list[str]] = {
    "ai_engineer": [
        "AI Engineer | Analytics Engineer | LLMs · RAG · LangChain · Python · FastAPI · SQL",
        "Analytics Engineer → AI Engineer | LLMs · RAG · Python · FastAPI · GenAI",
        "Data & AI Engineer | LangChain · LangGraph · Python · SQL · Cloud",
        "AI Engineer | Python · LangChain · LangGraph · SQL · RAG · FastAPI",
        "Applied AI Engineer | LLMs · RAG · Embeddings · Python · FastAPI",
    ],
    "data_engineer": [
        "Data Engineer | Python · Spark · Airflow · dbt · AWS",
        "Senior Data Engineer | ETL · Kafka · Spark · dbt · PostgreSQL",
        "Data Engineer | Airflow · dbt · Python · SQL · Cloud",
    ],
    "analytics_engineer": [
        "Analytics Engineer | dbt · SQL · Python · Looker · BigQuery",
        "Analytics Engineer | dbt · BigQuery · Python · Snowflake · Looker",
        "Data & Analytics Engineer | SQL · dbt · Python · BI · Cloud",
    ],
    "ml_engineer": [
        "ML Engineer | Python · TensorFlow · PyTorch · MLflow · AWS",
        "MLOps Engineer | Python · Kubeflow · MLflow · Docker · Kubernetes",
    ],
}

CTA_SIGNALS = (
    "abierto a",
    "open to",
    "looking for",
    "busco",
    "interested in",
    "disponible",
    "available for",
    "contact me",
    "contáctame",
    "let's connect",
    "conectemos",
    "hiring",
    "opportunities",
    "oportunidades",
)

ImpactType = Literal["very_high", "high", "medium", "low"]


@dataclass
class ParsedProfile:
    title: str = ""
    about: str = ""
    skills: list[str] = field(default_factory=list)
    experience: str = ""
    projects: str = ""
    education: str = ""
    raw_text: str = ""


@dataclass
class TitleScore:
    score: float
    checks: dict[str, bool | int]
    issues: list[str]


@dataclass
class AboutScore:
    score: float
    checks: dict[str, bool | int]
    issues: list[str]


@dataclass
class SectionScores:
    title: float
    about: float
    experience: float
    skills: float
    projects: float
    education: float


@dataclass
class Recommendation:
    priority: int
    section: str
    message: str
    impact: ImpactType


@dataclass
class TitleAnalysisDict:
    current: str
    issues: list[str]
    suggested_variants: list[str]


@dataclass
class ProfileAnalysisResult:
    overall_score: float
    section_scores: SectionScores
    title_analysis: TitleAnalysisDict
    recommendations: list[Recommendation]


def _role_tech_names(target_role: str) -> list[str]:
    raw = ROLE_KEYWORDS.get(target_role) or ROLE_KEYWORDS.get("ai_engineer", [])
    return [str(item["name"]) for item in raw]


def _count_tech_in_text(text: str, target_role: str) -> int:
    lower = text.lower()
    count = 0
    for name in _role_tech_names(target_role):
        pattern = r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, lower):
            count += 1
    return count


class ProfileParser:
    """Extract LinkedIn profile sections from pasted plain text."""

    SECTION_HEADERS: dict[str, list[str]] = {
        "about": [r"about", r"acerca de", r"resumen", r"summary"],
        "experience": [r"experience", r"experiencia", r"work experience"],
        "skills": [r"skills", r"habilidades", r"aptitudes"],
        "projects": [r"projects", r"proyectos"],
        "education": [r"education", r"educaci[oó]n", r"formación", r"formacion"],
    }

    def parse(self, profile_text: str) -> ParsedProfile:
        text = profile_text.replace("\r\n", "\n").strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        title = self._extract_title(lines)
        sections = self._split_sections(text)

        skills_raw = sections.get("skills", "")
        skills = self._parse_skills(skills_raw)

        parsed = ParsedProfile(
            title=title,
            about=sections.get("about", ""),
            skills=skills,
            experience=sections.get("experience", ""),
            projects=sections.get("projects", ""),
            education=sections.get("education", ""),
            raw_text=text,
        )
        logger.info(
            "profile_parsed",
            has_title=bool(parsed.title),
            skills_count=len(parsed.skills),
            about_len=len(parsed.about),
        )
        return parsed

    def _extract_title(self, lines: list[str]) -> str:
        # Prefer a line that looks like a headline / role (not email, not "About")
        for line in lines[:8]:
            cleaned = re.sub(
                r"^(title|headline|titular)\s*:\s*",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()
            lower = cleaned.lower()
            if lower in {"about", "experience", "skills", "education", "projects"}:
                continue
            if "@" in cleaned or lower.startswith("http"):
                continue
            if any(
                kw in lower
                for role_kws in ROLE_TITLE_KEYWORDS.values()
                for kw in role_kws
            ) or "|" in cleaned or "—" in cleaned or " - " in cleaned or "en " in lower:
                return cleaned[:220]
        # Fallback: second non-empty line (name then title), else first
        if len(lines) >= 2:
            return lines[1][:220]
        return lines[0][:220] if lines else ""

    def _split_sections(self, text: str) -> dict[str, str]:
        # Header alone on a line, or "Skills: python · sql" inline content
        header_re = re.compile(
            r"(?m)^[\s#*]*(?P<header>[A-Za-zÁÉÍÓÚáéíóúÑñ /&-]{3,40})\s*:"
            r"?\s*(?P<inline>.*)$"
        )
        matches: list[tuple[int, int, str, str]] = []
        for match in header_re.finditer(text):
            header = match.group("header").strip().lower()
            inline = (match.group("inline") or "").strip()
            for section, patterns in self.SECTION_HEADERS.items():
                if any(re.fullmatch(p, header, flags=re.IGNORECASE) for p in patterns):
                    matches.append((match.start(), match.end(), section, inline))
                    break

        sections: dict[str, str] = {}
        for idx, (_start, end, name, inline) in enumerate(matches):
            content_end = matches[idx + 1][0] if idx + 1 < len(matches) else len(text)
            content = text[end:content_end].strip()
            if inline:
                content = f"{inline}\n{content}".strip()
            sections[name] = (sections.get(name, "") + "\n" + content).strip()
        return sections

    def _parse_skills(self, skills_text: str) -> list[str]:
        if not skills_text:
            return []
        parts = re.split(r"[,·•\|\n]+", skills_text)
        return [p.strip() for p in parts if p.strip() and len(p.strip()) < 60]


class TitleScorer:
    """Score a LinkedIn headline 0–90 (hard to reach 100 by design)."""

    def score(self, title: str, target_role: str) -> TitleScore:
        title = title or ""
        lower = title.lower().strip()
        role_kws = ROLE_TITLE_KEYWORDS.get(target_role, [])

        role_mentioned = any(kw in lower for kw in role_kws)
        tech_count = _count_tech_in_text(title, target_role)
        length_ok = len(title) <= 220
        role_first = False
        if role_mentioned and lower:
            role_first = any(lower.startswith(kw) for kw in role_kws)

        score = 0
        if role_mentioned:
            score += 30
        score += min(40, tech_count * 10)
        if length_ok:
            score += 10
        if role_first:
            score += 10
        score = min(90, score)

        issues: list[str] = []
        if not role_mentioned:
            issues.append("No menciona el rol objetivo")
        if tech_count < 3:
            issues.append("Incluí al menos 3 tecnologías clave en el título")
        if not length_ok:
            issues.append("El título supera el límite de 220 caracteres de LinkedIn")
        if role_mentioned and not role_first:
            issues.append("Empezá el título con el rol objetivo (no con el empleador)")
        if re.search(r"\ben\b\s+\w+$", lower) and not role_mentioned:
            issues.append("El título parece centrado en la empresa, no en el rol")

        checks: dict[str, bool | int] = {
            "role_mentioned": role_mentioned,
            "tech_keywords_count": tech_count,
            "length_ok": length_ok,
            "role_first": role_first,
        }
        return TitleScore(score=float(score), checks=checks, issues=issues)


class AboutScorer:
    """Score a LinkedIn About section 0–100."""

    def score(self, about: str, target_role: str) -> AboutScore:
        about = about or ""
        if not about.strip():
            return AboutScore(
                score=0.0,
                checks={
                    "has_hook": False,
                    "tech_keywords_count": 0,
                    "has_quantified_results": False,
                    "optimal_length": False,
                    "has_cta": False,
                },
                issues=["La sección About está vacía"],
            )

        hook = about[:200].lower()
        role_kws = ROLE_TITLE_KEYWORDS.get(target_role, [])
        tech_names = [n.lower() for n in _role_tech_names(target_role)]
        has_hook = any(kw in hook for kw in role_kws) or any(t in hook for t in tech_names[:5])

        tech_count = _count_tech_in_text(about, target_role)
        has_quantified = bool(
            re.search(r"\d+\s*%|\d+\s*(años?|years?|x|meses?)", about, flags=re.I)
        )
        optimal_length = 200 <= len(about) <= 2600
        tail = about[-200:].lower()
        has_cta = any(signal in tail for signal in CTA_SIGNALS)

        score = 0
        if has_hook:
            score += 20
        score += min(40, tech_count * 8)
        if has_quantified:
            score += 15
        if optimal_length:
            score += 10
        if has_cta:
            score += 15
        score = min(100, score)

        issues: list[str] = []
        if not has_hook:
            issues.append("Las primeras líneas no mencionan el rol ni keywords clave")
        if tech_count < 3:
            issues.append("Agregá más keywords técnicas del rol en el About")
        if not has_quantified:
            issues.append("Incluí logros cuantificados (números, %, años)")
        if not optimal_length:
            issues.append("El About debería tener entre 200 y 2600 caracteres")
        if not has_cta:
            issues.append("Cerrá el About con un CTA (roles que buscás / abierto a)")

        return AboutScore(
            score=float(score),
            checks={
                "has_hook": has_hook,
                "tech_keywords_count": tech_count,
                "has_quantified_results": has_quantified,
                "optimal_length": optimal_length,
                "has_cta": has_cta,
            },
            issues=issues,
        )


class ProfileScorer:
    """Weighted overall LinkedIn profile score + recommendations."""

    def __init__(self) -> None:
        self.title_scorer = TitleScorer()
        self.about_scorer = AboutScorer()

    def score(self, parsed: ParsedProfile, target_role: str) -> ProfileAnalysisResult:
        title_result = self.title_scorer.score(parsed.title, target_role)
        about_result = self.about_scorer.score(parsed.about, target_role)

        skills_score = self._score_skills(parsed.skills, target_role)
        experience_score = self._score_text_section(parsed.experience, target_role, base=40)
        projects_score = self._score_text_section(parsed.projects, target_role, base=30)
        education_score = 70.0 if parsed.education.strip() else 25.0

        section_scores = SectionScores(
            title=title_result.score,
            about=about_result.score,
            experience=experience_score,
            skills=skills_score,
            projects=projects_score,
            education=education_score,
        )

        overall = (
            section_scores.title * SECTION_WEIGHTS["title"]
            + section_scores.about * SECTION_WEIGHTS["about"]
            + section_scores.skills * SECTION_WEIGHTS["skills"]
            + section_scores.experience * SECTION_WEIGHTS["experience"]
            + section_scores.projects * SECTION_WEIGHTS["projects"]
            + section_scores.education * SECTION_WEIGHTS["education"]
        )

        variants = TITLE_VARIANTS.get(target_role, TITLE_VARIANTS["ai_engineer"])
        recommendations = self._build_recommendations(
            section_scores, title_result, about_result, target_role
        )

        logger.info(
            "profile_scored",
            overall=round(overall, 1),
            role=target_role,
            title_score=title_result.score,
        )

        return ProfileAnalysisResult(
            overall_score=round(overall, 1),
            section_scores=section_scores,
            title_analysis=TitleAnalysisDict(
                current=parsed.title,
                issues=title_result.issues,
                suggested_variants=variants[:5],
            ),
            recommendations=recommendations,
        )

    def _score_skills(self, skills: list[str], target_role: str) -> float:
        if not skills:
            return 15.0
        joined = " ".join(skills)
        tech_count = _count_tech_in_text(joined, target_role)
        return float(min(100, 25 + tech_count * 12 + min(20, len(skills) * 3)))

    def _score_text_section(self, text: str, target_role: str, base: float) -> float:
        if not text.strip():
            return 20.0
        tech_count = _count_tech_in_text(text, target_role)
        return float(min(100, base + tech_count * 10))

    def _build_recommendations(
        self,
        section_scores: SectionScores,
        title_result: TitleScore,
        about_result: AboutScore,
        target_role: str,
    ) -> list[Recommendation]:
        weighted = {
            "title": section_scores.title * SECTION_WEIGHTS["title"],
            "about": section_scores.about * SECTION_WEIGHTS["about"],
            "skills": section_scores.skills * SECTION_WEIGHTS["skills"],
            "experience": section_scores.experience * SECTION_WEIGHTS["experience"],
            "projects": section_scores.projects * SECTION_WEIGHTS["projects"],
            "education": section_scores.education * SECTION_WEIGHTS["education"],
        }
        # Weakest section by score × weight first
        ordered = sorted(weighted.items(), key=lambda item: item[1])

        messages: dict[str, tuple[str, ImpactType]] = {
            "title": (
                "Reemplazá el título por uno con el rol objetivo + tecnologías clave",
                "very_high",
            ),
            "about": (
                "Reescribí el About con hook, stack técnico, logros cuantificados y CTA",
                "high",
            ),
            "skills": (
                "Actualizá Skills con las keywords más demandadas del rol objetivo",
                "high",
            ),
            "experience": (
                "En Experience, usá títulos de cargo alineados al rol y bullets con keywords",
                "medium",
            ),
            "projects": (
                "Agregá proyectos con demos de IA/datos y keywords técnicas",
                "medium",
            ),
            "education": (
                "Completá Education con títulos o certificaciones relevantes",
                "low",
            ),
        }

        recommendations: list[Recommendation] = []
        for priority, (section, _w) in enumerate(ordered, start=1):
            message, impact = messages[section]
            if section == "title" and title_result.issues:
                message = title_result.issues[0]
            if section == "about" and about_result.issues:
                message = about_result.issues[0]
            recommendations.append(
                Recommendation(
                    priority=priority,
                    section=section,
                    message=message,
                    impact=impact,
                )
            )
            if len(recommendations) >= 5:
                break

        # Ensure first recommendation is weakest weighted section
        if recommendations:
            weakest = ordered[0][0]
            if recommendations[0].section != weakest:
                recommendations.sort(
                    key=lambda r: 0 if r.section == weakest else r.priority
                )
                for idx, rec in enumerate(recommendations, start=1):
                    rec.priority = idx

        return recommendations
