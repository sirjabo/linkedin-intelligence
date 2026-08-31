"""Generate ready-to-use rewrites for each LinkedIn profile section."""
import json

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SYSTEM = """\
Sos un experto en optimización de perfiles de LinkedIn para el mercado tech latinoamericano.
Se te dará el texto de un perfil de LinkedIn, el rol objetivo y el análisis previo (scores y recomendaciones).
Tu tarea es generar el texto reescrito listo para copiar y pegar en cada sección del perfil.
Devolvé ÚNICAMENTE un JSON válido con esta estructura exacta:

{
  "title": {
    "rewrite": "string — el nuevo título/headline optimizado (máximo 220 caracteres)",
    "rationale": "string — 1 oración explicando por qué este título funciona mejor"
  },
  "about": {
    "rewrite": "string — el nuevo extracto completo (150-280 palabras, primera persona)",
    "rationale": "string — 1 oración"
  },
  "experience": [
    {
      "company": "string",
      "bullets": ["string — bullet point optimizado con métricas si es posible", "..."]
    }
  ],
  "skills": {
    "rewrite": ["skill1", "skill2", "..."],
    "rationale": "string — qué se agregó/reordenó y por qué"
  },
  "summary_of_changes": "string — resumen en 2-3 oraciones de los cambios más impactantes"
}

Reglas:
- Mantener los datos reales del perfil, solo optimizar la redacción y estructura
- Para experience: reescribir bullets con el formato "Verbo de acción + impacto cuantificable + contexto"
- Para skills: priorizar las más relevantes para el rol objetivo, agregar las que faltan del análisis
- Responder SOLO el JSON, sin markdown, sin explicaciones
"""


async def rewrite_linkedin_sections(
    profile_text: str,
    target_role: str,
    analysis: dict,
) -> dict:
    """
    Generate optimized rewrites for each LinkedIn section using OpenRouter.
    Returns a dict with ready-to-copy text per section.
    """
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OpenRouter no configurado. Configurá OPENROUTER_API_KEY.")

    role_label = target_role.replace("_", " ").title()
    analysis_summary = json.dumps({
        "section_scores": analysis.get("section_scores", {}),
        "keyword_gaps": analysis.get("keyword_gaps", []),
        "recommendations": [r.get("message", "") for r in analysis.get("recommendations", [])],
    }, ensure_ascii=False)

    user_content = (
        f"Rol objetivo: {role_label}\n\n"
        f"Análisis previo:\n{analysis_summary}\n\n"
        f"Texto del perfil:\n{profile_text[:6000]}"
    )

    payload = {
        "model": "openai/gpt-4o-mini",
        "max_tokens": 2500,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    resp.raise_for_status()
    data = resp.json()
    raw = data["choices"][0]["message"]["content"].strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        result = json.loads(raw)
    except Exception as exc:
        logger.error("linkedin_rewriter_parse_error", error=str(exc), raw=raw[:200])
        raise ValueError(f"LLM devolvió JSON inválido: {exc}") from exc

    logger.info("linkedin_sections_rewritten", role=target_role)
    return result
