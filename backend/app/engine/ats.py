"""ATS Score Engine — docs/09-ATS_ENGINE.md + tasks/cursor-sprint-001.md."""

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

# Hardcoded role keywords for MVP — tasks/cursor-sprint-001.md
ROLE_KEYWORDS: dict[str, list[dict[str, float | str]]] = {
    "ai_engineer": [
        {"name": "Python", "weight": 1.0},
        {"name": "LangChain", "weight": 0.90},
        {"name": "LangGraph", "weight": 0.85},
        {"name": "FastAPI", "weight": 0.80},
        {"name": "RAG", "weight": 0.80},
        {"name": "SQL", "weight": 0.75},
        {"name": "Docker", "weight": 0.70},
        {"name": "OpenAI API", "weight": 0.70},
        {"name": "Embeddings", "weight": 0.65},
        {"name": "Vector Database", "weight": 0.65},
        {"name": "Prompt Engineering", "weight": 0.60},
        {"name": "REST API", "weight": 0.60},
        {"name": "Git", "weight": 0.55},
        {"name": "AWS", "weight": 0.50},
        {"name": "PostgreSQL", "weight": 0.50},
    ],
    "data_engineer": [
        {"name": "Python", "weight": 1.0},
        {"name": "SQL", "weight": 0.95},
        {"name": "Spark", "weight": 0.85},
        {"name": "Airflow", "weight": 0.80},
        {"name": "dbt", "weight": 0.75},
        {"name": "AWS", "weight": 0.75},
        {"name": "Kafka", "weight": 0.70},
        {"name": "Docker", "weight": 0.65},
        {"name": "PostgreSQL", "weight": 0.60},
        {"name": "Git", "weight": 0.55},
    ],
    "analytics_engineer": [
        {"name": "SQL", "weight": 1.0},
        {"name": "dbt", "weight": 0.90},
        {"name": "Python", "weight": 0.85},
        {"name": "Looker", "weight": 0.70},
        {"name": "BigQuery", "weight": 0.70},
        {"name": "Snowflake", "weight": 0.65},
        {"name": "Git", "weight": 0.60},
        {"name": "Airflow", "weight": 0.55},
        {"name": "Tableau", "weight": 0.50},
    ],
    "ml_engineer": [
        {"name": "Python", "weight": 1.0},
        {"name": "PyTorch", "weight": 0.90},
        {"name": "TensorFlow", "weight": 0.85},
        {"name": "Docker", "weight": 0.75},
        {"name": "Kubernetes", "weight": 0.70},
        {"name": "MLflow", "weight": 0.70},
        {"name": "SQL", "weight": 0.60},
        {"name": "AWS", "weight": 0.55},
        {"name": "Git", "weight": 0.50},
    ],
}

# Alias map for MVP matching (case-insensitive)
KEYWORD_ALIASES: dict[str, list[str]] = {
    "Python": ["python", "python3"],
    "LangChain": ["langchain", "lang-chain"],
    "LangGraph": ["langgraph", "lang-graph"],
    "FastAPI": ["fastapi", "fast-api"],
    "RAG": ["rag", "retrieval augmented", "retrieval-augmented generation"],
    "SQL": ["sql", "t-sql", "plsql"],
    "Docker": ["docker", "containers"],
    "OpenAI API": ["openai", "openai api", "gpt", "gpt-4", "gpt4"],
    "Embeddings": ["embeddings", "embedding"],
    "Vector Database": [
        "vector database",
        "vector db",
        "vectordb",
        "pgvector",
        "pinecone",
        "weaviate",
        "chroma",
        "qdrant",
    ],
    "Prompt Engineering": ["prompt engineering", "prompting"],
    "REST API": ["rest api", "rest", "restful", "apis rest"],
    "Git": ["git", "github", "gitlab"],
    "AWS": ["aws", "amazon web services"],
    "PostgreSQL": ["postgresql", "postgres", "psql"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Airflow": ["airflow", "apache airflow"],
    "dbt": ["dbt", "data build tool"],
    "Kafka": ["kafka", "apache kafka"],
    "Looker": ["looker", "lookml"],
    "BigQuery": ["bigquery", "big query", "bq"],
    "Snowflake": ["snowflake"],
    "Tableau": ["tableau"],
    "PyTorch": ["pytorch", "torch"],
    "TensorFlow": ["tensorflow", "tf"],
    "MLflow": ["mlflow"],
    "Kubernetes": ["kubernetes", "k8s"],
}

CRITICAL_WEIGHT_THRESHOLD = 0.9
CRITICAL_PENALTY_POINTS = 10
SEMANTIC_WEIGHT_THRESHOLD = 0.7
SEMANTIC_SIMILARITY_THRESHOLD = 0.85

SEMANTIC_GROUPS: list[frozenset[str]] = [
    frozenset({"llm", "llms", "gpt", "claude", "openai", "openai api", "large language model"}),
    frozenset({"rag", "retrieval augmented generation", "retrieval-augmented"}),
    frozenset(
        {"vector database", "vector db", "pgvector", "pinecone", "weaviate", "chroma", "embeddings"}
    ),
    frozenset({"aws", "amazon web services"}),
    frozenset({"langchain", "langgraph", "llamaindex"}),
    frozenset({"rest api", "rest", "restful"}),
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
    if any(x in name for x in ("project", "rag", "demo", "portfolio", "vector")):
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


def role_keywords_to_weighted(role: str) -> list[WeightedKeyword]:
    raw = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["ai_engineer"])
    keywords: list[WeightedKeyword] = []
    for item in raw:
        name = str(item["name"])
        weight = float(item["weight"])
        aliases = list(KEYWORD_ALIASES.get(name, [name.lower()]))
        keywords.append(WeightedKeyword(name=name, weight=weight, aliases=aliases))
    return keywords


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

        seen: set[str] = set()
        unique: list[Recommendation] = []
        for rec in sorted(recommendations, key=lambda r: (r.priority, r.message)):
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
        suffix = f", aplicando {', '.join(top)}" if top else ""
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
        """MVP uses hardcoded ROLE_KEYWORDS from cursor-sprint-001.md."""
        return role_keywords_to_weighted(role)

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
            section_match = self.matcher.match(
                parsed.skills, match.all_keywords, cv_text=content
            )
            if section == "skills":
                scores[section] = calculate_ats_score(section_match)
            else:
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
            found.append(
                KeywordFound(keyword=kw.name, count=max(1, count), weight=kw.weight)
            )

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
