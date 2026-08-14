# LinkedIn Intelligence — Roadmap: Real Application Agent

> Fecha: 2026-08-14  
> Objetivo: `USER PROFILE + JOB → HIGH-QUALITY SUBMITTED APPLICATION`  
> Estado anterior: Backend Foundation (181 tests, 12 migraciones, ~30 endpoints)  
> Nuevo Definition of Done: El agente puede navegar, llenar y enviar un formulario de empresa real.

---

## Definition of Done (DoD)

Una capacidad está **completa** cuando:
1. Funciona con datos reales (candidato real, formulario real o mock ATS)
2. Tiene tests unitarios + integración + E2E (donde aplica)
3. Frontend conectado y usable
4. Manejo de errores, estados vacíos y carga
5. Seguridad: ownership, auth, no injection
6. No inventa datos — todo traceable a candidate context

Una capacidad NO está completa porque:
- Un endpoint existe (puede nunca ser llamado)
- Los tests pasan con mocks LLM
- La lógica está en el backend pero el frontend no la consume
- Funciona con SQLite in-memory pero no con datos reales

---

## Milestone 0 (ya completado): Backend Foundation

✅ Auth (register, login, refresh tokens)  
✅ Candidate Knowledge Base básico  
✅ Source ingestion (PDF, manual)  
✅ Profile extraction (LLM, mockeado)  
✅ Job parsing (LLM structured output)  
✅ Matching híbrido (determinístico + LLM)  
✅ Hard Constraints Layer  
✅ Career Fit Score  
✅ Application Decision Engine  
✅ Application workspace (strategy, CV, cover letter)  
✅ Form Intelligence (clasificación regex, no discovery)  
✅ Submission workflow (registro manual, no browser)  
✅ Learning Loop (análisis estadístico)  
✅ AI Evaluation Framework  
✅ Seguridad básica (rate limiting, SSRF, headers)  
✅ CI/CD (GitHub Actions)  

---

## Milestone 1: Mock ATS + Infrastructure (≈5 días)

> Objetivo: tener la infraestructura de browser automation lista y un ambiente de test controlado.

### 1.1 Mock ATS server local

Servidor FastAPI/HTML que simula un formulario de aplicación de empresa:

**Campos obligatorios incluidos:**
- Text: first_name, last_name, current_location, current_company, current_title
- Email: email
- Tel: phone
- URL: linkedin_url, portfolio_url
- Select: years_experience (0-2, 3-5, 6-10, 10+), work_authorization, education_level
- File: resume (PDF), cover_letter_file (opcional)
- Textarea: cover_letter (texto), why_company (requerida)
- Checkbox: relocation_willing, remote_ok
- Radio: employment_type (full-time, part-time, contract)
- Multi-step: página 1 personal info → página 2 professional → página 3 questions → confirmación

**Página de confirmación:**
- Extrae confirmation_id: `APP-{uuid4}`
- Texto: "Your application has been received. Reference: APP-..."

**Acceptance criteria:**
- Server corre en `localhost:8888` durante tests
- `/apply` devuelve el formulario
- `POST /submit` procesa y redirige a `/confirm`
- Fixture pytest levanta y destruye el server

### 1.2 BrowserAutomationAdapter

Implementar `PlaywrightAdapter` en `backend/app/services/browser/playwright_adapter.py`:

```
backend/app/services/browser/
├── __init__.py
├── adapter.py        # BrowserAutomationAdapter Protocol
├── playwright_adapter.py
├── form_extractor.py # DOM → RawForm
└── confirmation_detector.py
```

**Acceptance criteria:**
- `PlaywrightAdapter.open_url(url)` abre Chromium y devuelve PageState
- `PlaywrightAdapter.discover_form()` extrae todos los campos del mock ATS: labels, types, required, options
- `PlaywrightAdapter.fill_text(field_id, value)` llena un campo
- `PlaywrightAdapter.upload_file(field_id, path)` sube un archivo
- `PlaywrightAdapter.click_submit()` hace click en submit
- `PlaywrightAdapter.is_confirmation_page()` devuelve True en la página de confirmación
- `PlaywrightAdapter.extract_confirmation_id()` devuelve "APP-xxx" de la página

### 1.3 ATSRegistry + GenericFormAgent

```
backend/app/services/ats/
├── __init__.py
├── registry.py       # ATSRegistry + detect(url)
├── adapter.py        # ATSAdapter Protocol
├── greenhouse.py
├── lever.py
├── ashby.py
└── generic.py        # GenericFormAgent (LLM fallback)
```

**Acceptance criteria:**
- `ATSRegistry.detect("https://boards.greenhouse.io/company/jobs/123")` → `GreenhouseAdapter`
- `ATSRegistry.detect("https://jobs.lever.co/company/uuid")` → `LeverAdapter`
- `ATSRegistry.detect("https://unknown-company.com/apply")` → `GenericFormAgent`

### 1.4 ApplicationAgentSession (Migration 013)

Nueva tabla `application_agent_sessions` con el state machine documentado en ARCHITECTURE_APPLICATION_AGENT.md.

**Acceptance criteria:**
- `alembic upgrade head` aplica migration 013
- Model tiene todos los campos de estado, progress, y evidencia
- State machine tiene transitions válidas

---

## Milestone 2: Core Application Agent (≈7 días)

> Objetivo: el flujo completo funciona con el Mock ATS.

### 2.1 CandidateKnowledgeResolver

Servicio en `backend/app/services/candidate_knowledge_resolver.py`.

Resolvers para los 20 tipos más comunes:

| Semantic Type | Source | Method |
|--------------|--------|--------|
| full_name | candidate.name | DIRECT |
| first_name | candidate.name.split()[0] | COMPUTED |
| last_name | candidate.name.split()[-1] | COMPUTED |
| email | candidate.email | DIRECT |
| phone | None | HUMAN_REQUIRED |
| linkedin_url | candidate.sources[type=linkedin].source_url | DIRECT |
| location | candidate.location | DIRECT |
| years_experience | sum(exp.duration_years for exp in profile.experiences) | COMPUTED |
| salary_expectation | str(candidate.salary_min_usd) | DIRECT |
| work_authorization | candidate.work_authorization | DIRECT |
| education_level | max(profile.education, key=degree_rank) | COMPUTED |
| graduation_year | profile.education[-1].end_year | COMPUTED |
| current_company | profile.experiences[0].company | COMPUTED |
| current_title | profile.experiences[0].title | COMPUTED |
| cover_letter | application.cover_letter.content | DIRECT |
| cv_file | generate PDF from application.cv_version | GENERATED |
| custom_essay | CandidateAnswer KB → LLM fallback | FROM_KB / GENERATED |
| gender | None | HUMAN_REQUIRED |
| relocation | candidate.preferences.relocation_willing | DIRECT |
| availability | candidate.availability | DIRECT |

**Acceptance criteria:**
- `resolver.resolve("email", field, candidate, job)` devuelve candidate.email con source=DIRECT
- `resolver.resolve("years_experience", ...)` suma duración de todas las experiencias
- `resolver.resolve("custom_essay", field_label="Why our company?", ...)` llama a LLM
- `resolver.resolve("phone", ...)` devuelve source=HUMAN_REQUIRED con sugerencia vacía
- `resolver.resolve("gender", ...)` devuelve source=HUMAN_REQUIRED

### 2.2 ApplicationAgentOrchestrator

`backend/app/services/application_agent_orchestrator.py`

Implementa el flujo completo:

```
start() → discover → classify → map → partition(auto/human) → persist → return session
resume() → fill_auto_fields → check_all_ready → return session
submit() → validate_human_confirmed → fill_browser → click_submit → capture_confirmation
```

**Acceptance criteria:**
- `orchestrator.start(application_id, mock_ats_url, candidate_id)`:
  - Crea `ApplicationAgentSession`
  - Abre el Mock ATS en browser
  - Detecta 12 campos del formulario mock
  - Auto-classifica 8 como auto-fill y 4 como human_required
  - Session.status = "awaiting_human"

- `orchestrator.resume(session_id)`:
  - Después de que el usuario responde los 4 campos humanos
  - Session.status = "ready_to_fill"

- `orchestrator.submit(session_id, human_confirmed=True)`:
  - Llena todos los campos en browser
  - Sube CV PDF
  - Click submit
  - Detecta confirmation page
  - Extrae confirmation_id
  - Crea ApplicationSubmission con el confirmation_id
  - Actualiza application.status = "applied"
  - Session.status = "submitted"

### 2.3 API endpoints del agent

```
POST /applications/{id}/agent/start
GET  /applications/{id}/agent/status
POST /applications/{id}/agent/answer/{field_id}
POST /applications/{id}/agent/preview
POST /applications/{id}/agent/submit
```

**Acceptance criteria:**
- Cada endpoint tiene test de integración
- Auth + ownership checks en todos
- Rate limiting en start (max 5/min por usuario)

### 2.4 File Storage para CVs

Implementar storage de PDFs generados para poder adjuntarlos en formularios.

Estrategia MVP: storage local en `/data/cv_pdfs/{candidate_id}/{application_id}.pdf`

**Acceptance criteria:**
- POST /applications/{id}/cv devuelve URL del PDF generado (no sólo el JSON)
- El PDF es accesible para que BrowserAutomationAdapter lo adjunte
- Path relativo al container, no URL pública (seguridad)

### 2.5 Golden E2E V2 con Mock ATS

Actualizar `tests/test_e2e.py` para incluir el flujo de browser automation:

```python
async def test_golden_e2e_with_browser():
    # Paso 1-13: flujo existente de API (register → submit manual)
    # Paso 14 (nuevo): start agent con mock ATS URL
    # Paso 15: verify 4 campos human_required
    # Paso 16: responder campos humanos
    # Paso 17: agent.submit(confirmed=True)
    # Paso 18: verify application.status == "applied"
    # Paso 19: verify confirmation_id starts with "APP-"
    # Paso 20: verify screenshot captured
```

---

## Milestone 3: ATS Adapters (≈7 días)

> Objetivo: soporte nativo para los 3 ATS más comunes en el mercado tech.

### 3.1 GreenhouseAdapter

- Detectar: `boards.greenhouse.io`
- Handle: GDPR consent checkbox, optional LinkedIn apply
- Sections: Basic Info, Work Experience, Additional Questions, EEOC
- Submit: click submit, detect "Your application has been submitted"

**Test**: smoke test con cuenta sandbox de Greenhouse (no aplicación real)

### 3.2 LeverAdapter

- Detectar: `jobs.lever.co`
- Handle: optional OAuth login, basic form
- Custom fields: variable por empresa

### 3.3 AshbyAdapter

- Detectar: `jobs.ashbyhq.com`
- Handle: multi-step común, campos de "source" (referral)

**Nota de seguridad**: Los smoke tests de ATS usan cuentas de sandbox o URLs de test. NUNCA se envían aplicaciones reales de candidatos reales en tests automatizados.

---

## Milestone 4: Application Knowledge Base (≈3 días)

> Objetivo: el candidato puede pre-guardar respuestas a preguntas frecuentes.

### 4.1 CandidateAnswer entity

Migración 014. CRUD endpoints:
- GET /candidates/me/answers
- POST /candidates/me/answers
- PUT /candidates/me/answers/{id}
- DELETE /candidates/me/answers/{id}

Tipos semánticos iniciales:
- salary_expectation
- work_authorization_text
- relocation_response
- why_interested_general
- greatest_strength
- career_goal_3yr
- notice_period
- remote_preference

### 4.2 Integración en CandidateKnowledgeResolver

- Antes de llamar al LLM para custom_essay: buscar en CandidateAnswer KB
- Si existe answer para el question_type semántico → usar como base para LLM
- Track de `times_used` y `last_used_at`

### 4.3 Frontend: gestión de respuestas

Sección en `/profile` para gestionar las respuestas pre-guardadas.

---

## Milestone 5: Frontend Integration (≈5 días)

> Objetivo: el usuario puede usar el Application Agent desde el browser.

### 5.1 Application Agent UI en workspace

En `/applications/[id]`, nueva sección "Application Agent":

```
┌─────────────────────────────────────────────────────┐
│  🤖 Application Agent                                 │
│                                                       │
│  Application URL: [input text field]                  │
│  [Start Agent] button                                 │
│                                                       │
│  Status: Discovering form...  [spinner]               │
│                                                       │
│  ──────────────────────────────────────────────────  │
│  Auto-filled (8):                                     │
│  ✓ First Name: "Juan"                                 │
│  ✓ Email: "juan@example.com"                          │
│  ...                                                  │
│                                                       │
│  Pending your input (4):                              │
│  📋 Phone: [input]                                    │
│  📋 Why do you want to work here?: [textarea]         │
│  📋 Current Salary: [input]                           │
│  📋 Resume: [file upload button]                      │
│                                                       │
│  [Continue and Preview] button                        │
└─────────────────────────────────────────────────────┘
```

### 5.2 Preview antes de submit

Modal de confirmación mostrando:
- Screenshot del formulario lleno
- Lista de todos los campos con valores
- Warning si algún campo es incierto
- [Confirmar y Enviar] / [Cancelar]

### 5.3 Submission result

Pantalla de éxito con:
- Confirmation ID
- Screenshot de la página de confirmación
- Opción de guardar las respuestas humanas en CandidateAnswer KB

---

## Milestone 6: Evidence & Quality (≈4 días)

### 6.1 Evidence Graph

Para cada campo auto-llenado, trazar el origen:

```
campo "years_experience = 6"
  ← CandidateKnowledgeResolver.resolve()
  ← ExperienceExtracted("DataCo", "Senior DE", 3 years)
  ← ExperienceExtracted("TechCorp", "DE", 2 years)
  ← ExperienceExtracted("StartupX", "Junior DE", 1 year)
```

Almacenar como `evidence_ref` en `ApplicationFormField`.

### 6.2 FormIntelligenceService V2

- Clasificación con confidence score (0.0–1.0)
- LLM fallback cuando regex confidence < 0.7
- Log de cada clasificación con confidence para calibración futura

### 6.3 Real AI evaluation de form filling

En `tests/test_smoke.py`, agregar smoke test que evalúa form filling con candidato sintético y mock ATS:

```python
async def test_form_filling_quality():
    # Llena el mock ATS con candidato sintético
    # Evalúa que los campos correctos fueron auto-llenados
    # Evalúa que los campos inciertos fueron marcados human_required
    # Evalúa que no inventó datos
```

---

## KPIs del Real Application Agent

| Métrica | Objetivo | Cómo medir |
|---------|----------|-----------|
| Form discovery accuracy | >90% campos detectados | Mock ATS E2E |
| Auto-fill accuracy | >85% campos auto-llenados correctamente | Mock ATS evaluation |
| Human-required precision | >95% (no pide datos que tiene) | Mock ATS evaluation |
| Submit success rate | >95% en formularios soportados | Integration tests |
| Confirmation capture rate | >90% | Integration tests |
| Time to complete form | <30 seg (mock ATS) | Performance test |
| LLM call count per application | <3 | Cost tracking |

---

## Cronograma estimado

| Milestone | Duración | Días acumulados |
|-----------|----------|-----------------|
| M1: Mock ATS + Infrastructure | 5 días | 5 |
| M2: Core Application Agent | 7 días | 12 |
| M3: ATS Adapters | 7 días | 19 |
| M4: Application Knowledge Base | 3 días | 22 |
| M5: Frontend Integration | 5 días | 27 |
| M6: Evidence & Quality | 4 días | 31 |

**Total estimado**: ~6 semanas de desarrollo full-time.

---

## Lo que NO se implementa (por diseño)

- **Scraping de LinkedIn**: violación de ToS. El candidato ingresa su perfil manualmente o vía LinkedIn data export.
- **CAPTCHA solving**: requiere human-in-the-loop siempre.
- **Auto-submit sin confirmación humana**: el usuario siempre confirma antes del submit final.
- **Aplicaciones a sitios no-HTTPS**: sólo HTTPS permitido.
- **Mass application (sin revisión humana)**: el producto es de calidad, no de volumen.
