"""Fetch and extract text from a public LinkedIn profile URL using an LLM."""
import json
import re

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_EXTRACT_SYSTEM = """\
Sos un extractor de datos de perfiles de LinkedIn.
Se te dará el HTML de una página de perfil público de LinkedIn.
Extraé toda la información del perfil y devolvé ÚNICAMENTE texto plano estructurado
con el siguiente formato (omitir secciones vacías):

NOMBRE: [nombre completo]
TÍTULO: [headline/título actual]
UBICACIÓN: [ciudad, país]
SOBRE MÍ: [texto del extracto/about]
EXPERIENCIA:
- [Cargo] en [Empresa] ([fechas]): [descripción]
EDUCACIÓN:
- [Título] en [Institución] ([años])
SKILLS: [lista separada por comas]
PROYECTOS:
- [Nombre]: [descripción]
CERTIFICACIONES:
- [Nombre] ([emisor], [año])

Si el HTML no corresponde a un perfil de LinkedIn o está bloqueado, devolvé exactamente: ERROR: perfil_no_accesible
"""


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:12000]


async def _llm_extract(html_text: str) -> str:
    """Use OpenRouter to extract profile text from raw HTML."""
    payload = {
        "model": "openai/gpt-4o-mini",
        "max_tokens": 1200,
        "messages": [
            {"role": "system", "content": _EXTRACT_SYSTEM},
            {"role": "user", "content": f"HTML del perfil:\n\n{html_text}"},
        ],
    }
    async with httpx.AsyncClient(timeout=30) as client:
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
    return data["choices"][0]["message"]["content"].strip()


async def fetch_linkedin_profile(url: str) -> str:
    """
    Fetch a public LinkedIn profile URL and extract its text content.
    Returns structured plain text of the profile.
    Raises ValueError if the profile is inaccessible or URL is invalid.
    """
    url = url.strip()
    if "linkedin.com/in/" not in url:
        raise ValueError("La URL debe ser un perfil de LinkedIn (linkedin.com/in/...)")

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
        html = resp.text
    except Exception as exc:
        logger.warning("linkedin_fetch_error", url=url, error=str(exc))
        raise ValueError("No se pudo acceder al perfil. Verificá la URL o usá el modo de pegado manual.") from exc

    stripped = _strip_html(html)

    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OpenRouter no configurado. Configurá OPENROUTER_API_KEY.")

    extracted = await _llm_extract(stripped)

    if extracted.startswith("ERROR:"):
        raise ValueError(
            "El perfil de LinkedIn no es público o requiere iniciar sesión. "
            "Copiá el texto de tu perfil manualmente."
        )

    logger.info("linkedin_profile_fetched", url=url, chars=len(extracted))
    return extracted
