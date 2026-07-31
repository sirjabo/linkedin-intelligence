import json
import asyncio
from typing import AsyncGenerator
import anthropic
from app.core.config import settings

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

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


async def parse_cv_text(raw_text: str) -> dict:
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=PARSE_SYSTEM,
        messages=[{"role": "user", "content": f"Extract CV data from:\n\n{raw_text}"}],
    )
    content = response.content[0].text.strip()
    # Strip markdown code fences if present
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
    system_prompt = CHAT_SYSTEM_TEMPLATE.replace("{cv_json}", json.dumps(cv_data, ensure_ascii=False, indent=2))

    messages = [
        *[{"role": m["role"], "content": m["content"]} for m in history[-8:]],
        {"role": "user", "content": user_message},
    ]

    TAG_OPEN = "<cv_update>"
    TAG_CLOSE = "</cv_update>"
    text_buffer = ""
    cv_buffer = ""
    in_update = False

    async with client.messages.stream(
        model="claude-sonnet-5",
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for chunk in stream.text_stream:
            if not in_update:
                text_buffer += chunk

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
                cv_buffer += chunk
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
