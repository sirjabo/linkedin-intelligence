"""LinkedIn About section writer — generates 3 optimized variants via LLM."""
import json
import uuid
import anthropic
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

_SYSTEM = """\
Sos un experto en copywriting para LinkedIn orientado al mercado tech latinoamericano.
Tu tarea es escribir 3 variantes de la sección "Acerca de / About" de un perfil de LinkedIn.
Devolvé ÚNICAMENTE un JSON válido sin explicaciones adicionales.

Reglas:
- Cada variante tiene entre 150 y 280 palabras
- Escritas en primera persona
- Incluyen keywords del rol objetivo de forma natural (no keyword-stuffing)
- Tono profesional pero humano, no corporativo
- Primera oración debe enganchar al lector inmediatamente
- Incluir logros concretos (con números si los hay en el input)
- Terminar con una llamada a la acción suave (open to opportunities, etc.)

Estructura EXACTA del JSON:
{
  "variants": [
    {
      "id": 1,
      "tone": "string — tono de esta variante (ej: 'técnico y directo', 'narrativo y humano', 'orientado a resultados')",
      "text": "string — texto completo del About"
    },
    {
      "id": 2,
      "tone": "...",
      "text": "..."
    },
    {
      "id": 3,
      "tone": "...",
      "text": "..."
    }
  ],
  "tips": ["consejo 1 para mejorar", "consejo 2", "consejo 3"]
}
"""


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"About writer returned invalid JSON: {exc}") from exc


async def write_about_section(
    profile_summary: str,
    target_role: str,
    current_about: str | None = None,
    key_skills: list[str] | None = None,
    achievements: list[str] | None = None,
) -> dict:
    """Generate 3 optimized LinkedIn About variants for the given profile context."""
    context_parts = [f"Rol objetivo: {target_role}"]
    if profile_summary:
        context_parts.append(f"Resumen del perfil / experiencia:\n{profile_summary}")
    if current_about:
        context_parts.append(f"About actual (a mejorar):\n{current_about}")
    if key_skills:
        context_parts.append(f"Skills clave: {', '.join(key_skills)}")
    if achievements:
        context_parts.append(f"Logros destacados:\n" + "\n".join(f"- {a}" for a in achievements))

    user_prompt = "\n\n".join(context_parts)

    msg = await _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    block = msg.content[0]
    if not hasattr(block, "text"):
        raise ValueError("Unexpected response type from LLM")
    raw = block.text  # type: ignore[union-attr]
    data = _parse_json(raw)

    return {
        "writer_id": str(uuid.uuid4()),
        "target_role": target_role,
        "variants": data.get("variants", []),
        "tips": data.get("tips", []),
    }
