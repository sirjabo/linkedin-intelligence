# LinkedIn Intelligence — Acceptance Criteria: Real Application Agent

> Fecha: 2026-08-14  
> Propósito: Definir exactamente cuándo cada capacidad del Real Application Agent está "done".  
> Regla base: una capacidad sólo está done cuando el test correspondiente pasa con datos reales (no mocks LLM, no SQLite in-memory, no inputs manuales del usuario en el test).

---

## Acceptance Criterion AC-01: Mock ATS Server

**Feature**: Servidor web local que simula un ATS completo para tests E2E.

**Given**: tests E2E están ejecutando  
**When**: `pytest tests/test_e2e_browser.py` corre  
**Then**:
- El mock ATS server levanta en `localhost:8888` automáticamente como fixture de pytest
- La ruta `GET /apply` devuelve un formulario HTML con al menos 12 campos:
  - 3 text fields (first_name, last_name, location)
  - 1 email field
  - 1 tel field
  - 1 URL field (linkedin)
  - 1 select (work_authorization con opciones: US Citizen, Permanent Resident, Require Sponsorship)
  - 1 file input (resume, accept=".pdf,.doc,.docx")
  - 1 textarea (cover_letter)
  - 1 textarea requerida (why_company — siempre human_required)
  - 1 checkbox (relocation_willing)
  - 1 select (years_experience: 0-2, 3-5, 6-10, 10+)
- La ruta `POST /submit` procesa el formulario y redirige a `/confirm`
- La ruta `GET /confirm` devuelve HTML con texto "Your application reference: APP-{uuid}" visible

**Verification test**: `tests/mock_ats/test_server.py::test_mock_ats_serves_form`

---

## Acceptance Criterion AC-02: Form Discovery

**Feature**: El sistema puede detectar la estructura de un formulario real vía browser automation.

**Given**: Mock ATS server corriendo en `localhost:8888`  
**When**: `PlaywrightAdapter.discover_form()` se llama con esa URL  
**Then**:
- Devuelve `RawForm` con exactamente 12 campos detectados
- Cada campo tiene: `label` (texto del label HTML), `type` (input type), `required` (bool), `options` (list para selects)
- El campo `why_company` tiene `required=True`
- El campo `resume` tiene `type="file"`
- El campo `work_authorization` tiene `options=["US Citizen", "Permanent Resident", "Require Sponsorship"]`
- Tiempo de ejecución < 10 segundos

**Verification test**: `tests/test_browser_adapter.py::test_discover_mock_ats_form`

---

## Acceptance Criterion AC-03: Field Semantic Classification

**Feature**: El sistema clasifica correctamente los tipos semánticos de los 12 campos del Mock ATS.

**Given**: `RawForm` con los 12 campos del Mock ATS  
**When**: `FormIntelligenceService.classify_all(raw_form)` se llama  
**Then**:
- `first_name` → semantic_type="first_name", confidence≥0.95
- `email` → semantic_type="email", confidence≥0.95
- `phone` → semantic_type="phone", human_required=True
- `linkedin` → semantic_type="linkedin_url", confidence≥0.85
- `work_authorization` → semantic_type="work_authorization", confidence≥0.90
- `resume` → semantic_type="cv_file", human_required=True
- `why_company` → semantic_type="custom_essay", human_required=True
- `years_experience` → semantic_type="years_experience", confidence≥0.85
- `relocation_willing` → semantic_type="relocation", confidence≥0.80
- Ningún campo se clasifica como "unknown" para los labels del Mock ATS

**Verification test**: `tests/test_form_intelligence.py::test_classify_mock_ats_fields`

---

## Acceptance Criterion AC-04: CandidateKnowledgeResolver

**Feature**: El resolver mapea campos clasificados a datos reales del candidato.

**Given**: Candidato sintético con perfil completo:
```python
candidate = CandidateContext(
    name="María García",
    email="maria@test.com",
    location="Buenos Aires, Argentina",
    work_authorization="citizen",
    salary_min_usd=80000,
    availability="two_weeks",
    linkedin_url="https://linkedin.com/in/maria-garcia",
    experiences=[Experience(company="DataCo", title="Senior DE", duration_years=3)],
    experiences=[Experience(company="StartupX", title="DE", duration_years=2)],
)
```

**When**: `resolver.resolve(semantic_type, field_label, candidate, job)` para cada campo  
**Then**:
- `email` → value="maria@test.com", source=DIRECT, confidence=1.0
- `first_name` → value="María", source=COMPUTED, confidence=1.0
- `last_name` → value="García", source=COMPUTED, confidence=1.0
- `location` → value="Buenos Aires, Argentina", source=DIRECT, confidence=1.0
- `years_experience` → value="5" (3+2 años), source=COMPUTED, confidence=0.85
- `work_authorization` → value="citizen" (o la opción más cercana del select), source=DIRECT
- `phone` → value=None, source=HUMAN_REQUIRED, confidence=0.0
- `why_company` → value=None, source=HUMAN_REQUIRED, suggestion=pre-generada por LLM, confidence=0.0
- `cv_file` → value=path_to_pdf, source=GENERATED (PDF generado)

**Verification test**: `tests/test_candidate_knowledge_resolver.py::test_resolve_mock_ats_fields`

---

## Acceptance Criterion AC-05: Auto-fill en Browser

**Feature**: El agente llena automáticamente los campos auto-fill en el browser real.

**Given**:
- Mock ATS server corriendo
- Candidato sintético con perfil completo
- Session en estado "ready_to_fill" (todos los campos human_required ya respondidos)

**When**: `orchestrator.fill_auto_fields(session_id)` se llama  
**Then**:
- El browser tiene los campos de texto llenos con los valores correctos
- El campo `work_authorization` tiene la opción correcta seleccionada
- El campo `years_experience` tiene la opción correcta seleccionada
- El checkbox `relocation_willing` está en el estado correcto
- Ningún campo requerido `human_required` está vacío (todos ya fueron respondidos por el usuario)
- El PDF del CV está adjuntado al campo `resume`
- Screenshot capturado y almacenado

**Verification test**: `tests/test_e2e_browser.py::test_auto_fill_mock_ats`

---

## Acceptance Criterion AC-06: Human-in-the-Loop

**Feature**: El agente identifica correctamente qué campos requieren input humano y espera.

**Given**: Mock ATS con el formulario completo  
**When**: `orchestrator.start(application_id, mock_ats_url, candidate_id)` retorna  
**Then**:
- `session.status = "awaiting_human"`
- `session.fields_human_pending = 3` (phone, why_company, y cualquier otro no resolvible)
- `session.fields_auto_filled = 9` (todos los que tienen fuente en candidate context)
- Los 3 campos human_required tienen `human_suggestion` no vacía (pre-sugerencia del sistema)
- La API response lista exactamente esos 3 campos con sus labels

**When**: El usuario responde los 3 campos y llama `orchestrator.resume(session_id)`  
**Then**:
- `session.status = "ready_to_fill"`
- `session.fields_human_pending = 0`

**Verification test**: `tests/test_e2e_browser.py::test_human_in_the_loop_flow`

---

## Acceptance Criterion AC-07: Submit y Confirmación

**Feature**: El agente envía la aplicación y captura la confirmación.

**Given**: Session en estado "awaiting_confirm" (preview aprobado)  
**When**: `orchestrator.submit(session_id, human_confirmed=True)` se llama  
**Then**:
- Browser hace click en submit
- Browser navega a la página de confirmación del Mock ATS
- `session.status = "submitted"`
- `session.confirmation_id` comienza con "APP-"
- `session.confirmation_text` contiene "Your application reference"
- `session.screenshot_confirmation` tiene un path/URL válido (≥1KB)
- `ApplicationSubmission` fue creada con el `confirmation_id`
- `application.status = "applied"`
- `ApplicationEvent` con `event_type="applied"` creado

**Verification test**: `tests/test_e2e_browser.py::test_golden_e2e_with_mock_ats`

---

## Acceptance Criterion AC-08: ATS Detection

**Feature**: El sistema detecta automáticamente el ATS provider desde la URL.

**Given**: URLs de diferentes ATS providers  
**When**: `ATSRegistry.detect(url)` se llama  
**Then**:
- `https://boards.greenhouse.io/company/jobs/123` → `GreenhouseAdapter`
- `https://jobs.lever.co/company/uuid` → `LeverAdapter`
- `https://jobs.ashbyhq.com/company/uuid` → `AshbyAdapter`
- `https://company.wd1.myworkdayjobs.com/en-US/External` → `WorkdayAdapter`
- `https://careers.smartrecruiters.com/company` → `SmartRecruitersAdapter`
- `https://unknown-company.com/apply` → `GenericFormAgent`

**Verification test**: `tests/test_ats_registry.py::test_ats_detection_by_url`

---

## Acceptance Criterion AC-09: No Inventar Datos

**Feature**: El agente nunca auto-llena un campo con datos que no provienen del candidate context.

**Given**: Campo con `semantic_type="github_url"` y candidato sin `github_url`  
**When**: `resolver.resolve("github_url", ...)` se llama  
**Then**: `resolved.value = None`, `resolved.source = HUMAN_REQUIRED`

**Given**: Campo `custom_essay` con label "Describe your biggest achievement"  
**When**: El candidato no tiene `CandidateAnswer` pre-guardada para ese tipo  
**Then**:
- El resolver llama al LLM con el candidate context completo
- El LLM genera una respuesta BASADA en las experiencias reales del candidato
- La respuesta generada es marcada como `source=GENERATED` con `confidence < 0.8`
- El campo aparece como `human_required=True` (el usuario debe revisar y aprobar)
- El claim validator puede verificar que la respuesta no contiene claims sin evidencia

**Verification test**: `tests/test_candidate_knowledge_resolver.py::test_no_hallucination_on_missing_data`

---

## Acceptance Criterion AC-10: Golden E2E Completo

**Feature**: El flujo completo de principio a fin funciona sin intervención manual en el test.

**Given**:
- Mock ATS server corriendo
- Candidato sintético "María García" con perfil completo en DB
- Job "Senior Data Engineer" en DB

**When**: El test `test_golden_e2e_with_mock_ats` corre (sin ANTHROPIC_API_KEY real, usando mocks sólo donde necesario)  
**Then** (secuencia):
1. Register + Login → JWT token
2. PUT /candidates/me → profile con datos de María
3. POST /jobs → job con JD completa
4. POST /jobs/{id}/match → match con score > 0.6
5. POST /applications → application en draft
6. POST /applications/{id}/strategy → strategy generada
7. POST /applications/{id}/cv → CV personalizado con PDF
8. POST /applications/{id}/cover-letter → cover letter generada
9. POST /applications/{id}/agent/start → session status="awaiting_human", 3 campos pending
10. POST /applications/{id}/agent/answer/{phone_field_id} → phone respondido
11. POST /applications/{id}/agent/answer/{why_field_id} → why_company respondido
12. POST /applications/{id}/agent/answer/{salary_field_id} → salary respondido
13. POST /applications/{id}/agent/preview → FillPreview con screenshot
14. POST /applications/{id}/agent/submit con confirmed=True → session status="submitted"
15. GET /applications/{id} → application.status=="applied"
16. GET /applications/{id}/agent/status → confirmation_id starts with "APP-"
17. GET /stats/summary → funnel.applied == 1

**Todo el test debe correr en < 120 segundos** (el browser es la parte lenta)

**Verification test**: `tests/test_e2e_browser.py::test_golden_e2e_with_mock_ats`

---

## Acceptance Criterion AC-11: Frontend Application Agent UI

**Feature**: El usuario puede usar el Application Agent desde el browser.

**Given**: Usuario autenticado con application en estado "ready"  
**When**: Abre `/applications/[id]` → sección "Application Agent"  
**Then**:
- Ve un input para la URL del formulario de aplicación
- Puede hacer click en "Start Agent"
- Ve un spinner con "Descubriendo formulario..."
- Ve la lista de campos auto-llenados (con valores)
- Ve la lista de campos pendientes (con inputs para responder)
- Puede responder los campos pendientes
- Puede hacer click en "Continuar"
- Ve un preview del formulario lleno
- Puede hacer click en "Confirmar y Enviar"
- Ve la confirmación con el confirmation_id

**Verification**: manual en browser (no automatizable sin Playwright en el frontend también)

---

## Acceptance Criterion AC-12: Security — No Submit Sin Confirmación

**Feature**: El agente NUNCA envía una aplicación sin confirmación explícita del usuario.

**Given**: Session en cualquier estado antes de "submitting"  
**When**: Cualquier código interno llama a `browser.click_submit()`  
**Then**: El método lanza `SubmitWithoutConfirmationError` si `session.human_confirmed != True`

**Given**: POST /applications/{id}/agent/submit sin body `{confirmed: true}`  
**When**: El endpoint procesa el request  
**Then**: Devuelve 422 con detail "Human confirmation required before submit"

**Verification test**: `tests/test_application_agent.py::test_submit_requires_human_confirmation`

---

## Acceptance Criterion AC-13: Idempotencia del Agent

**Feature**: Si el browser falla a mitad del proceso, el estado se puede recuperar.

**Given**: Session en estado "filling" y el browser crashea  
**When**: Se vuelve a llamar `POST /applications/{id}/agent/start`  
**Then**:
- El sistema detecta que ya existe una session para esa application
- Devuelve la session existente (no crea una nueva)
- `session.status` refleja el último estado conocido
- El usuario puede decidir si continuar o reiniciar

**Verification test**: `tests/test_application_agent.py::test_agent_recovery_after_browser_crash`

---

## Acceptance Criterion AC-14: File Storage de CVs

**Feature**: Los CVs generados están disponibles como archivos para adjuntar.

**Given**: CV generado para una application  
**When**: `resolver.resolve("cv_file", ...)` se llama  
**Then**:
- Existe un archivo PDF en el path esperado (`/data/cv_pdfs/{candidate_id}/{application_id}.pdf`)
- El archivo tiene tamaño > 5KB (contiene contenido real)
- El archivo es un PDF válido (magic bytes: `%PDF`)
- `BrowserAutomationAdapter.upload_file(field_id, path)` puede adjuntarlo sin error

**Verification test**: `tests/test_candidate_knowledge_resolver.py::test_cv_file_available_for_attachment`
