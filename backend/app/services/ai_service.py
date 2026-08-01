import json
from typing import AsyncGenerator
import httpx
from app.core.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PARSE_MODEL = "anthropic/claude-haiku-4-5-20251001"
CHAT_MODEL = "anthropic/claude-sonnet-4-5"

PARSE_SYSTEM = """Extract CV/resume data from the provided text and return ONLY a valid JSON object with this exact structure. No explanations, just JSON.

{
  "name": "Full Name",
  "contact": {
    "email": "email@example.com",
    "phone": "+54 11 1234-5678",
    "location": "Buenos Aires, Argentina",
    "linkedin": "linkedin.com/in/username",
    "github": "github.com/username",
    "website": null
  },
  "target_role": "Senior Full-Stack Developer",
  "summary": "Professional summary text here...",
  "experience": [
    {
      "company": "Company Name",
      "role": "Job Title",
      "start_date": "01/2020",
      "end_date": "Present",
      "location": "Buenos Aires",
      "bullets": [
        "Led development of...",
        "Implemented..."
      ]
    }
  ],
  "skills": {
    "languages": ["Python", "TypeScript"],
    "frameworks": ["FastAPI", "React"],
    "cloud": ["AWS", "GCP"],
    "databases": ["PostgreSQL", "Redis"],
    "tools": ["Docker", "Git"],
    "other": []
  },
  "education": [
    {
      "institution": "University Name",
      "degree": "Bachelor",
      "field": "Computer Science",
      "year": "2018",
      "gpa": null
    }
  ],
  "projects": [],
  "certifications": []
}

Rules:
- Use null for missing fields, empty arrays [] for missing lists
- Put experience in reverse chronological order
- Infer target_role from job titles if not explicitly stated
- Separate skills by category as best you can"""

CHAT_SYSTEM_TEMPLATE = """Sos un experto coach de CVs y consultor de carrera especializado en roles tech en Argentina y Latinoamérica. Tu misión es ayudar a candidatos a crear CVs que sean excelentes tanto para sistemas ATS como para reclutadores humanos.

## CV Actual del Candidato

```json
{cv_json}
```

## Tus capacidades

1. **Analizar** el CV y dar feedback específico y accionable
2. **Reescribir** secciones cuando te lo pidan
3. **Optimizar** keywords para roles/empresas específicas
4. **Mejorar** bullet points usando la metodología ATR (Acción → Tarea → Resultado)
5. **Garantizar** compatibilidad ATS (sin tablas, fuentes estándar, secciones bien nombradas)
6. **Cuantificar** logros (%, números, impacto del negocio)

## Protocolo de actualización del CV

Cuando modifiques cualquier parte del CV, incluí la actualización AL FINAL de tu respuesta en este formato exacto:

Para secciones simples:
<cv_update>
{{"section": "summary", "content": "texto del summary actualizado"}}
</cv_update>

Para experiencia (index = posición en el array, comenzando desde 0):
<cv_update>
{{"section": "experience", "index": 0, "field": "bullets", "content": ["Bullet 1 mejorado", "Bullet 2 mejorado"]}}
</cv_update>

Para skills:
<cv_update>
{{"section": "skills", "content": {{"languages": ["Python", "TypeScript"], "frameworks": ["FastAPI", "React"], "cloud": [], "databases": [], "tools": [], "other": []}}}}
</cv_update>

Secciones válidas: "name", "summary", "experience", "skills", "education", "projects", "certifications", "target_role"

## Principios de calidad

**Para bullet points:**
- Comenzar con verbo de acción fuerte (Lideré, Desarrollé, Arquitecté, Optimicé, Implementé)
- Cuantificar: "Reduje tiempo de deploy en 60% implementando CI/CD con GitHub Actions"
- Formato: Verbo + Contexto + Impacto medible

**Para el Summary:**
- 3-4 oraciones máximo
- Sin pronombres personales al inicio
- Incluir: experiencia + especialidad + skills clave + logro destacado

**Para ATS compliance:**
- Usar keywords naturalmente, sin stuffing
- Nombres de secciones estándar
- Sin caracteres especiales raros

Respondé SIEMPRE en el idioma en que el usuario te escribe (español o inglés).
Sé conversacional, específico y alentador. Explicá el POR QUÉ de cada cambio."""


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


async def parse_cv_text(raw_text: str) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers=_headers(),
            json={
                "model": PARSE_MODEL,
                "max_tokens": 4096,
                "messages": [
                    {"role": "system", "content": PARSE_SYSTEM},
                    {"role": "user", "content": f"Extract CV data from:\n\n{raw_text}"},
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)


async def stream_cv_chat(
    cv_data: dict,
    history: list[dict],
    user_message: str,
) -> AsyncGenerator[str, None]:
    system_prompt = CHAT_SYSTEM_TEMPLATE.replace(
        "{cv_json}", json.dumps(cv_data, ensure_ascii=False, indent=2)
    )

    messages = [
        {"role": "system", "content": system_prompt},
        *[{"role": m["role"], "content": m["content"]} for m in history[-8:]],
        {"role": "user", "content": user_message},
    ]

    TAG_OPEN = "<cv_update>"
    TAG_CLOSE = "</cv_update>"
    text_buffer = ""
    cv_buffer = ""
    in_update = False

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            OPENROUTER_URL,
            headers=_headers(),
            json={
                "model": CHAT_MODEL,
                "max_tokens": 4096,
                "messages": messages,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    chunk_text = chunk["choices"][0]["delta"].get("content") or ""
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

                if not chunk_text:
                    continue

                if not in_update:
                    text_buffer += chunk_text

                    while TAG_OPEN in text_buffer:
                        before, _, after = text_buffer.partition(TAG_OPEN)
                        if before:
                            yield f"data: {json.dumps({'type': 'text', 'content': before})}\n\n"
                        in_update = True
                        cv_buffer = after
                        text_buffer = ""

                        if TAG_CLOSE in cv_buffer:
                            json_str, _, rest = cv_buffer.partition(TAG_CLOSE)
                            try:
                                update = json.loads(json_str.strip())
                                yield f"data: {json.dumps({'type': 'cv_update', **update})}\n\n"
                            except json.JSONDecodeError:
                                pass
                            in_update = False
                            text_buffer = rest
                            cv_buffer = ""

                    if not in_update:
                        safe_len = max(0, len(text_buffer) - len(TAG_OPEN))
                        if safe_len > 0:
                            yield f"data: {json.dumps({'type': 'text', 'content': text_buffer[:safe_len]})}\n\n"
                            text_buffer = text_buffer[safe_len:]
                else:
                    cv_buffer += chunk_text
                    if TAG_CLOSE in cv_buffer:
                        json_str, _, rest = cv_buffer.partition(TAG_CLOSE)
                        try:
                            update = json.loads(json_str.strip())
                            yield f"data: {json.dumps({'type': 'cv_update', **update})}\n\n"
                        except json.JSONDecodeError:
                            pass
                        in_update = False
                        text_buffer = rest
                        cv_buffer = ""

    if text_buffer:
        yield f"data: {json.dumps({'type': 'text', 'content': text_buffer})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
