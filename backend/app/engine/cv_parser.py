"""CV text parser — extracts structured sections from plain-text CVs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)

SECTION_HEADERS: dict[str, list[str]] = {
    "summary": [
        r"summary",
        r"profile",
        r"about",
        r"resumen",
        r"perfil",
        r"objective",
        r"objetivo",
    ],
    "experience": [
        r"experience",
        r"experiencia",
        r"work\s+history",
        r"employment",
        r"trayectoria",
    ],
    "skills": [
        r"skills",
        r"habilidades",
        r"competencias",
        r"tecnolog[ií]as",
        r"tech\s+stack",
        r"herramientas",
    ],
    "education": [
        r"education",
        r"educaci[oó]n",
        r"formación",
        r"formacion",
        r"academic",
    ],
    "projects": [
        r"projects",
        r"proyectos",
        r"portfolio",
        r"side\s+projects",
    ],
    "certifications": [
        r"certifications?",
        r"certificaciones",
        r"certificates?",
    ],
    "contact": [
        r"contact",
        r"contacto",
    ],
}

# Common tech skills for heuristic extraction (MVP without spaCy model)
KNOWN_SKILLS: frozenset[str] = frozenset(
    {
        "python",
        "sql",
        "javascript",
        "typescript",
        "java",
        "go",
        "rust",
        "scala",
        "r",
        "pandas",
        "numpy",
        "spark",
        "hadoop",
        "airflow",
        "dbt",
        "kafka",
        "flink",
        "fastapi",
        "django",
        "flask",
        "langchain",
        "langgraph",
        "llamaindex",
        "openai",
        "anthropic",
        "claude",
        "gpt",
        "rag",
        "llm",
        "llms",
        "transformers",
        "pytorch",
        "tensorflow",
        "scikit-learn",
        "sklearn",
        "huggingface",
        "vector db",
        "pgvector",
        "pinecone",
        "weaviate",
        "chroma",
        "qdrant",
        "postgresql",
        "postgres",
        "mysql",
        "mongodb",
        "redis",
        "elasticsearch",
        "aws",
        "gcp",
        "azure",
        "docker",
        "kubernetes",
        "k8s",
        "terraform",
        "ci/cd",
        "git",
        "github",
        "gitlab",
        "n8n",
        "power bi",
        "tableau",
        "looker",
        "snowflake",
        "bigquery",
        "databricks",
        "mlflow",
        "celery",
        "rabbitmq",
        "graphql",
        "rest",
        "api",
        "apis",
        "microservices",
        "etl",
        "elt",
        "data pipeline",
        "prompt engineering",
        "agents",
        "mcp",
        "embeddings",
        "semantic search",
        "next.js",
        "react",
        "node.js",
        "nodejs",
    }
)


@dataclass
class ParsedCV:
    contact: str = ""
    summary: str = ""
    experience: str = ""
    skills: list[str] = field(default_factory=list)
    education: str = ""
    projects: str = ""
    certifications: str = ""
    raw_text: str = ""
    experience_bullets: list[str] = field(default_factory=list)


class CVParser:
    """Extracts sections and skills from CV plain text."""

    def parse(self, cv_text: str) -> ParsedCV:
        normalized = cv_text.replace("\r\n", "\n").strip()
        sections = self._split_sections(normalized)

        skills = self._extract_skills(
            sections.get("skills", "") + "\n" + normalized
        )
        bullets = self._extract_bullets(sections.get("experience", ""))

        parsed = ParsedCV(
            contact=sections.get("contact", "") or self._guess_contact(normalized),
            summary=sections.get("summary", ""),
            experience=sections.get("experience", ""),
            skills=skills,
            education=sections.get("education", ""),
            projects=sections.get("projects", ""),
            certifications=sections.get("certifications", ""),
            raw_text=normalized,
            experience_bullets=bullets,
        )
        logger.info(
            "cv_parsed",
            skills_count=len(parsed.skills),
            has_experience=bool(parsed.experience),
            has_projects=bool(parsed.projects),
        )
        return parsed

    def _split_sections(self, text: str) -> dict[str, str]:
        # Find header positions
        header_pattern = re.compile(
            r"(?m)^[\s#*]*(?P<header>[A-Za-zÁÉÍÓÚáéíóúÑñ /&-]{3,40})\s*:?\s*$"
        )
        matches: list[tuple[int, int, str]] = []
        for match in header_pattern.finditer(text):
            header = match.group("header").strip().lower()
            section_name = self._map_header(header)
            if section_name:
                matches.append((match.start(), match.end(), section_name))

        sections: dict[str, str] = {}
        for idx, (_start, end, name) in enumerate(matches):
            content_end = matches[idx + 1][0] if idx + 1 < len(matches) else len(text)
            content = text[end:content_end].strip()
            if name in sections:
                sections[name] = sections[name] + "\n" + content
            else:
                sections[name] = content
        return sections

    def _map_header(self, header: str) -> str | None:
        for section, patterns in SECTION_HEADERS.items():
            for pattern in patterns:
                if re.fullmatch(pattern, header, flags=re.IGNORECASE):
                    return section
        return None

    def _extract_skills(self, text: str) -> list[str]:
        found: list[str] = []
        lower = text.lower()
        for skill in sorted(KNOWN_SKILLS, key=len, reverse=True):
            # Word-boundary-ish match
            pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
            if re.search(pattern, lower):
                found.append(self._canonicalize(skill))
        # Also split comma/pipe lists in skills section
        return list(dict.fromkeys(found))

    def _canonicalize(self, skill: str) -> str:
        mapping = {
            "postgres": "PostgreSQL",
            "postgresql": "PostgreSQL",
            "k8s": "Kubernetes",
            "kubernetes": "Kubernetes",
            "nodejs": "Node.js",
            "node.js": "Node.js",
            "next.js": "Next.js",
            "sklearn": "scikit-learn",
            "scikit-learn": "scikit-learn",
            "llms": "LLM",
            "llm": "LLM",
            "gpt": "GPT",
            "power bi": "Power BI",
            "ci/cd": "CI/CD",
            "vector db": "Vector DB",
            "prompt engineering": "Prompt Engineering",
            "data pipeline": "Data Pipeline",
            "semantic search": "Semantic Search",
            "langchain": "LangChain",
            "langgraph": "LangGraph",
            "llamaindex": "LlamaIndex",
            "fastapi": "FastAPI",
            "aws": "AWS",
            "gcp": "GCP",
            "rag": "RAG",
            "mcp": "MCP",
            "n8n": "n8n",
            "dbt": "dbt",
            "sql": "SQL",
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
        }
        return mapping.get(skill.lower(), skill.title() if len(skill) > 3 else skill.upper())

    def _extract_bullets(self, experience_text: str) -> list[str]:
        bullets: list[str] = []
        for line in experience_text.splitlines():
            stripped = line.strip()
            if re.match(r"^[-•*·]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped):
                cleaned = re.sub(r"^[-•*·]\s+", "", stripped)
                cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
                if len(cleaned) > 20:
                    bullets.append(cleaned)
        return bullets

    def _guess_contact(self, text: str) -> str:
        email = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        phone = re.search(r"(\+?\d[\d\s().-]{7,}\d)", text)
        linkedin = re.search(r"(linkedin\.com/in/[\w\-]+)", text, re.IGNORECASE)
        parts = []
        if email:
            parts.append(email.group(0))
        if phone:
            parts.append(phone.group(0))
        if linkedin:
            parts.append(linkedin.group(0))
        return " | ".join(parts)
