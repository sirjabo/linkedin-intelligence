"""LinkedIn profile analyzer — stateless LLM-based scoring and recommendations."""
import json
import uuid

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ROLE_LABELS = {
    "ai_engineer": "AI Engineer",
    "data_engineer": "Data Engineer",
    "analytics_engineer": "Analytics Engineer",
    "ml_engineer": "ML Engineer",
    "backend_engineer": "Backend Engineer",
    "frontend_engineer": "Frontend Engineer",
    "devops_engineer": "DevOps Engineer",
    "data_scientist": "Data Scientist",
}

_SYSTEM = """\
Sos un experto en optimización de perfiles de LinkedIn para el mercado tech latinoamericano.
Tu tarea es analizar el texto de un perfil y devolver ÚNICAMENTE un JSON válido, sin explicaciones.

Estructura EXACTA del JSON de respuesta:
{
  "current_title": "string — título actual extraído del perfil",
  "section_scores": {
    "title": <0-100>,
    "about": <0-100>,
    "experience": <0-100>,
    "skills": <0-100>,
    "projects": <0-100>,
    "education": <0-100>
  },
  "title_issues": ["lista de problemas con el título actual"],
  "title_variants": [
    "variante 1 del título optimizada",
    "variante 2 del título optimizada",
    "variante 3 del título optimizada"
  ],
  "keyword_gaps": ["skills/keywords del rol objetivo que no aparecen en el perfil"],
  "recommendations": [
    {
      "priority": 1,
      "section": "title|about|experience|skills|projects|education",
      "message": "acción concreta y específica",
      "impact": "very_high|high|medium|low"
    }
  ]
}

Reglas:
- section_scores: 0 si la sección no existe, penalizar fuertemente si no hay keywords del rol objetivo
- title_variants: siempre incluir el rol objetivo + 2-3 tecnologías clave del rol + nivel si se puede inferir
- keyword_gaps: máximo 8 items, los más relevantes para el rol objetivo que faltan
- recommendations: exactamente 5 items ordenados por prioridad descendente
- Responder SOLO el JSON, sin markdown, sin explicaciones\
"""


def _user_prompt(profile_text: str, role_label: str) -> str:
    return (
        f"Rol objetivo: {role_label}\n\n"
        f"Texto del perfil de LinkedIn:\n\n{profile_text[:6000]}"
    )


def _parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return json.loads(text)


def _compute_overall(section_scores: dict) -> int:
    weights = {
        "title": 0.25,
        "about": 0.20,
        "experience": 0.25,
        "skills": 0.15,
        "projects": 0.10,
        "education": 0.05,
    }
    total = sum(section_scores.get(k, 0) * w for k, w in weights.items())
    return round(total)


async def analyze_linkedin_profile(
    profile_text: str,
    target_role: str,
) -> dict:
    """Analyze a LinkedIn profile text and return scores + recommendations."""
    role_label = ROLE_LABELS.get(target_role, target_role.replace("_", " ").title())

    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OpenRouter no configurado. Configurá OPENROUTER_API_KEY.")

    payload = {
        "model": "openai/gpt-4o-mini",
        "max_tokens": 1500,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _user_prompt(profile_text, role_label)},
        ],
    }
    async with httpx.AsyncClient(timeout=60) as http:
        resp = await http.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    try:
        parsed = _parse_llm_json(raw)
    except Exception as exc:
        logger.error("linkedin_analyzer_parse_error", error=str(exc), raw=raw[:200])
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    section_scores = parsed.get("section_scores", {})
    overall = _compute_overall(section_scores)

    return {
        "analysis_id": str(uuid.uuid4()),
        "overall_score": overall,
        "target_role": target_role,
        "section_scores": section_scores,
        "title_analysis": {
            "current": parsed.get("current_title", ""),
            "issues": parsed.get("title_issues", []),
            "suggested_variants": parsed.get("title_variants", []),
        },
        "keyword_gaps": parsed.get("keyword_gaps", []),
        "recommendations": parsed.get("recommendations", []),
    }
