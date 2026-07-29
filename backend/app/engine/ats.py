"""ATS Score Engine — docs/09-ATS_ENGINE.md."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.skill_demand import SkillDemand
from app.db.models.skills_catalog import SkillsCatalog
from app.engine.cv_parser import CVParser, ParsedCV
from app.schemas.analyze import (
    KeywordAnalysis,
    KeywordFound,
    KeywordMissing,
    Recommendation,
    SectionScores,
)

logger = get_logger(__name__)

# Fallback keywords when DB has no skill_demand data yet (MVP bootstrap)
FALLBACK_KEYWORDS: dict[str, list[tuple[str, float, list[str]]]] = {
    "ai_engineer": [
        ("Python", 1.0, ["python"]),
        ("LangChain", 0.85, ["langchain", "lang-chain"]),
        ("LangGraph", 0.8, ["langgraph"]),
        ("RAG", 0.8, ["rag", "retrieval augmented"]),
        ("LLM", 0.85, ["llm", "llms", "large language model"]),
        ("FastAPI", 0.75, ["fastapi"]),
        ("SQL", 0.8, ["sql"]),
        ("Vector DB", 0.7, ["pgvector", "pinecone", "weaviate", "chroma", "qdrant", "vector db"]),
        ("Docker", 0.6, ["docker"]),
        ("AWS", 0.55, ["aws", "amazon web services"]),
        ("Embeddings", 0.65, ["embeddings", "embedding"]),
        ("Prompt Engineering", 0.6, ["prompt engineering", "prompting"]),
        ("PyTorch", 0.5, ["pytorch", "torch"]),
        ("OpenAI", 0.55, ["openai", "gpt"]),
        ("Git", 0.5, ["git", "github"]),
    ],
    "data_engineer": [
        ("Python", 1.0, ["python"]),
        ("SQL", 1.0, ["sql"]),
        ("Spark", 0.85, ["spark", "pyspark"]),
        ("Airflow", 0.8, ["airflow"]),
        ("Kafka", 0.75, ["kafka"]),
        ("AWS", 0.7, ["aws"]),
        ("dbt", 0.65, ["dbt"]),
        ("Docker", 0.6, ["docker"]),
        ("PostgreSQL", 0.7, ["postgresql", "postgres"]),
        ("ETL", 0.75, ["etl", "elt"]),
        ("Snowflake", 0.55, ["snowflake"]),
        ("BigQuery", 0.5, ["bigquery"]),
        ("Kubernetes", 0.45, ["kubernetes", "k8s"]),
        ("Terraform", 0.4, ["terraform"]),
        ("Git", 0.5, ["git"]),
    ],
    "analytics_engineer": [
        ("SQL", 1.0, ["sql"]),
        ("dbt", 0.9, ["dbt"]),
        ("Python", 0.85, ["python"]),
        ("Looker", 0.6, ["looker", "lookml"]),
        ("Tableau", 0.55, ["tableau"]),
        ("Power BI", 0.55, ["power bi", "powerbi"]),
        ("Snowflake", 0.7, ["snowflake"]),
        ("BigQuery", 0.65, ["bigquery"]),
        ("Airflow", 0.5, ["airflow"]),
        ("Git", 0.55, ["git"]),
        ("Data Modeling", 0.7, ["data modeling", "dimensional modeling", "star schema"]),
        ("ETL", 0.6, ["etl", "elt"]),
        ("pandas", 0.65, ["pandas"]),
        ("PostgreSQL", 0.5, ["postgresql", "postgres"]),
        ("n8n", 0.4, ["n8n"]),
    ],
}

SECTION_WEIGHTS = {
    "skills": 0.30,
    "experience": 0.30,
    "projects": 0.20,
    "summary": 0.10,
    "education": 0.05,
    "contact": 0.05,
}

CRITICAL_WEIGHT_THRESHOLD = 0.9
CRITICAL_PENALTY_POINTS = 10
SEMANTIC_WEIGHT_THRESHOLD = 0.7
SEMANTIC_SIMILARITY_THRESHOLD = 0.85

# Simple synonym groups for semantic-ish matching without embeddings (MVP)
SEMANTIC_GROUPS: list[frozenset[str]] = [
    frozenset({"llm", "llms", "gpt", "claude", "large language model", "generative ai", "genai"}),
    frozenset({"rag", "retrieval augmented generation", "retrieval-augmented"}),
    frozenset({"vector db", "pgvector", "pinecone", "weaviate", "chroma", "qdrant", "embeddings"}),
    frozenset({"fastapi", "flask", "django", "rest api", "api"}),
    frozenset({"kubernetes", "k8s", "container orchestration"}),
    frozenset({"aws", "amazon web services", "cloud"}),
    frozenset({"etl", "elt", "data pipeline", "pipelines"}),
    frozenset({"langchain", "langgraph", "llamaindex", "llm framework"}),
]


@dataclass
class WeightedKeyword:
    name: str
    weight: float
    aliases: list[str] = field(default_factory=list)
    frequency: float = 0.0


@dataclass
class MatchResult:
    matched: list[WeightedKeyword]
    missing: list[WeightedKeyword]
    match_types: dict[str, Literal["exact", "alias", "semantic"]] = field(default_factory=dict)

    @property
    def all_keywords(self) -> list[WeightedKeyword]:
        return self.matched + self.missing


@dataclass
class ATSAnalysisResult:
    ats_score: int
    keyword_analysis: KeywordAnalysis
    section_scores: SectionScores
    recommendations: list[Recommendation]
    summary: str


def best_section_for_keyword(kw: WeightedKeyword, parsed_cv: ParsedCV) -> str:
    name = kw.name.lower()
    if any(x in name for x in ("project", "rag", "demo", "portfolio")):
        return "projects"
    if not parsed_cv.skills:
        return "skills"
    return "skills"


def frequency_to_weight(frequency: float) -> float:
    if frequency > 0.8:
        return 1.0
    if frequency > 0.5:
        return 0.7
    if frequency > 0.3:
        return 0.5
    return 0.3


def calculate_ats_score(match_result: MatchResult) -> int:
    """
    Score = (matched weights / total weights) * 100
    minus 10 points per critical missing keyword (weight >= 0.9).
    """
    total_weight = sum(k.weight for k in match_result.all_keywords)
    if total_weight <= 0:
        return 0

    matched_weight = sum(k.weight for k in match_result.matched)
    raw_score = (matched_weight / total_weight) * 100

    critical_missing = [k for k in match_result.missing if k.weight >= CRITICAL_WEIGHT_THRESHOLD]
    penalty = len(critical_missing) * CRITICAL_PENALTY_POINTS

    return max(0, min(100, int(raw_score - penalty)))


class ATSMatcher:
    """Exact + alias + semantic matching of CV skills vs role keywords."""

    def match(
        self,
        cv_skills: list[str],
        role_keywords: list[WeightedKeyword],
        cv_text: str = "",
    ) -> MatchResult:
        cv_normalized = {s.lower().strip(): s for s in cv_skills}
        cv_lower_list = list(cv_normalized.keys())
        text_lower = cv_text.lower()

        matched: list[WeightedKeyword] = []
        missing: list[WeightedKeyword] = []
        match_types: dict[str, Literal["exact", "alias", "semantic"]] = {}

        for keyword in role_keywords:
            if self._exact_match(keyword.name, cv_lower_list, text_lower):
                matched.append(keyword)
                match_types[keyword.name] = "exact"
                continue

            if self._alias_match(keyword, cv_lower_list, text_lower):
                matched.append(keyword)
                match_types[keyword.name] = "alias"
                continue

            if keyword.weight >= SEMANTIC_WEIGHT_THRESHOLD:
                similarity = self._semantic_match(keyword.name, cv_lower_list, text_lower)
                if similarity > SEMANTIC_SIMILARITY_THRESHOLD:
                    matched.append(keyword)
                    match_types[keyword.name] = "semantic"
                    continue

            missing.append(keyword)

        return MatchResult(matched=matched, missing=missing, match_types=match_types)

    def _exact_match(self, name: str, cv_skills: list[str], text: str) -> bool:
        needle = name.lower()
        if needle in cv_skills:
            return True
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text))

    def _alias_match(
        self, keyword: WeightedKeyword, cv_skills: list[str], text: str
    ) -> bool:
        for alias in keyword.aliases:
            alias_l = alias.lower()
            if alias_l in cv_skills:
                return True
            if re.search(rf"(?<![a-z0-9]){re.escape(alias_l)}(?![a-z0-9])", text):
                return True
        return False

    def _semantic_match(self, name: str, cv_skills: list[str], text: str) -> float:
        name_l = name.lower()
        for group in SEMANTIC_GROUPS:
            if name_l not in group and not any(name_l in g or g in name_l for g in group):
                continue
            for term in group:
                if term == name_l:
                    continue
                if term in cv_skills or re.search(
                    rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text
                ):
                    return 0.9
        return 0.0


class RecommendationEngine:
    """Generates prioritized recommendations from match gaps."""

    def generate(
        self,
        parsed_cv: ParsedCV,
        missing_keywords: list[WeightedKeyword],
        section_scores: SectionScores,
    ) -> list[Recommendation]:
        recommendations: list[Recommendation] = []

        for kw in sorted(missing_keywords, key=lambda k: k.weight, reverse=True):
            if kw.weight >= 0.8:
                section = best_section_for_keyword(kw, parsed_cv)
                recommendations.append(
                    Recommendation(
                        priority=1,
                        type="add_keyword",
                        section=section,
                        message=f"Agregá '{kw.name}' a tu sección de {section}",
                        impact="high",
                    )
                )

        weak_bullets = self._find_weak_bullets(parsed_cv.experience_bullets)
        for bullet in weak_bullets[:3]:
            rewritten = self._rewrite_bullet_heuristic(bullet, missing_keywords)
            recommendations.append(
                Recommendation(
                    priority=2,
                    type="rewrite_bullet",
                    section="experience",
                    message="Reescribí este bullet con impacto cuantificado y keywords del rol",
                    impact="medium",
                    original=bullet,
                    suggested=rewritten,
                )
            )

        if not parsed_cv.projects.strip():
            recommendations.append(
                Recommendation(
                    priority=3,
                    type="add_section",
                    section="projects",
                    message="Agregá una sección de proyectos con demos de IA / datos",
                    impact="medium",
                )
            )

        # Deduplicate by message, keep top 5
        seen: set[str] = set()
        unique: list[Recommendation] = []
        for rec in sorted(recommendations, key=lambda r: r.priority):
            if rec.message in seen:
                continue
            seen.add(rec.message)
            unique.append(rec)
            if len(unique) >= 5:
                break
        return unique

    def _find_weak_bullets(self, bullets: list[str]) -> list[str]:
        weak: list[str] = []
        for bullet in bullets:
            has_number = bool(re.search(r"\d", bullet))
            has_action = bool(
                re.match(
                    r"^(desarroll|implement|cre|diseñ|optimiz|automatiz|lider|built|designed|led)",
                    bullet,
                    re.IGNORECASE,
                )
            )
            if not has_number or not has_action:
                weak.append(bullet)
        return weak

    def _rewrite_bullet_heuristic(
        self, bullet: str, missing: list[WeightedKeyword]
    ) -> str:
        top = [k.name for k in missing[:2]]
        suffix = ""
        if top:
            suffix = f", aplicando {', '.join(top)}"
        cleaned = bullet.rstrip(".")
        if re.search(r"\d", cleaned):
            return f"{cleaned}{suffix}."
        return f"{cleaned}, reduciendo el tiempo de procesamiento en 40%{suffix}."


class ATSEngine:
    """Orchestrates CV parsing, keyword matching, scoring and recommendations."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self.db = db
        self.parser = CVParser()
        self.matcher = ATSMatcher()
        self.recommender = RecommendationEngine()

    async def analyze(self, cv_text: str, target_role: str) -> ATSAnalysisResult:
        parsed = self.parser.parse(cv_text)
        keywords = await self.get_role_keywords(target_role)
        match_result = self.matcher.match(parsed.skills, keywords, cv_text=parsed.raw_text)
        score = calculate_ats_score(match_result)
        section_scores = self._score_sections(parsed, match_result)
        recommendations = self.recommender.generate(
            parsed, match_result.missing, section_scores
        )
        keyword_analysis = self._to_keyword_analysis(match_result, parsed)
        summary = self._build_summary(score, match_result, target_role)

        logger.info(
            "ats_analyzed",
            score=score,
            role=target_role,
            matched=len(match_result.matched),
            missing=len(match_result.missing),
        )
        return ATSAnalysisResult(
            ats_score=score,
            keyword_analysis=keyword_analysis,
            section_scores=section_scores,
            recommendations=recommendations,
            summary=summary,
        )

    async def get_role_keywords(self, role: str) -> list[WeightedKeyword]:
        if self.db is not None:
            db_keywords = await self._load_keywords_from_db(role)
            if db_keywords:
                return db_keywords
        return self._fallback_keywords(role)

    async def _load_keywords_from_db(self, role: str) -> list[WeightedKeyword]:
        assert self.db is not None
        try:
            stmt = (
                select(SkillDemand, SkillsCatalog)
                .join(SkillsCatalog, SkillDemand.skill_id == SkillsCatalog.id)
                .where(SkillDemand.role_category == role)
                .where(SkillsCatalog.is_active.is_(True))
                .order_by(SkillDemand.frequency_pct.desc())
                .limit(100)
            )
            result = await self.db.execute(stmt)
            rows = result.all()
        except Exception as exc:
            logger.warning("skill_demand_query_failed", role=role, error=str(exc))
            return []

        if not rows:
            return []

        keywords: list[WeightedKeyword] = []
        for demand, skill in rows:
            freq = float(demand.frequency_pct) / 100.0
            keywords.append(
                WeightedKeyword(
                    name=skill.display_name,
                    weight=frequency_to_weight(freq),
                    aliases=list(skill.aliases or []) + [skill.name, skill.slug],
                    frequency=freq,
                )
            )
        return keywords

    def _fallback_keywords(self, role: str) -> list[WeightedKeyword]:
        raw = FALLBACK_KEYWORDS.get(role, FALLBACK_KEYWORDS["ai_engineer"])
        return [
            WeightedKeyword(name=name, weight=weight, aliases=aliases)
            for name, weight, aliases in raw
        ]

    def _score_sections(self, parsed: ParsedCV, match: MatchResult) -> SectionScores:
        text_parts = {
            "skills": " ".join(parsed.skills),
            "experience": parsed.experience,
            "projects": parsed.projects,
            "summary": parsed.summary,
            "education": parsed.education,
            "contact": parsed.contact,
        }

        scores: dict[str, int] = {}
        for section, content in text_parts.items():
            if section == "contact":
                scores[section] = 100 if parsed.contact else 40
                continue
            if not content.strip():
                scores[section] = 20
                continue
            section_match = self.matcher.match(parsed.skills, match.all_keywords, cv_text=content)
            if section == "skills":
                scores[section] = calculate_ats_score(section_match)
            else:
                # Presence + keyword density heuristic
                base = 50 if content.strip() else 20
                bonus = min(50, len(section_match.matched) * 8)
                scores[section] = min(100, base + bonus)

        return SectionScores(
            contact=scores["contact"],
            summary=scores["summary"],
            experience=scores["experience"],
            skills=scores["skills"],
            education=scores["education"],
            projects=scores["projects"],
        )

    def _to_keyword_analysis(
        self, match: MatchResult, parsed: ParsedCV
    ) -> KeywordAnalysis:
        text_lower = parsed.raw_text.lower()
        found: list[KeywordFound] = []
        for kw in match.matched:
            pattern = re.escape(kw.name.lower())
            count = len(re.findall(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text_lower))
            if count == 0:
                for alias in kw.aliases:
                    count += len(
                        re.findall(
                            rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])",
                            text_lower,
                        )
                    )
            found.append(KeywordFound(keyword=kw.name, count=max(1, count), weight=kw.weight))

        missing = [
            KeywordMissing(
                keyword=kw.name,
                weight=kw.weight,
                suggested_section=best_section_for_keyword(kw, parsed),
            )
            for kw in match.missing
        ]
        return KeywordAnalysis(found=found, missing=missing)

    def _build_summary(self, score: int, match: MatchResult, role: str) -> str:
        role_label = role.replace("_", " ")
        top_missing = [k.name for k in match.missing[:3]]
        if score >= 75:
            return (
                f"Tu CV tiene buen alineamiento para {role_label}. "
                f"Potencial de mejora en: {', '.join(top_missing) or 'detalles menores'}."
            )
        if score >= 60:
            return (
                f"Tu CV tiene un nivel aceptable para {role_label} pero le faltan "
                f"keywords clave: {', '.join(top_missing)}."
            )
        return (
            f"Tu CV necesita optimización para pasar filtros ATS de {role_label}. "
            f"Priorizá agregar: {', '.join(top_missing)}."
        )
