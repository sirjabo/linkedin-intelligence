# LinkedIn Intelligence — Product Completion Gap Analysis

> Fecha: 2026-08-14  
> Branch: `claude/new-session-ce0sct`  
> Tests: 181 pasando, 5 skipped (smoke, sin API key)  
> Auditor: análisis directo del código fuente — ningún ítem es inferido

---

## Premisa central

**Los 181 tests demuestran que la FUNDACIÓN BACKEND funciona.**  
No demuestran que el producto pueda convertir `USER PROFILE + JOB → HIGH-QUALITY SUBMITTED APPLICATION`.

Este documento distingue rigurosamente:

| Término | Significado |
|---------|------------|
| **BACKEND FOUNDATION** | Código que funciona en tests unitarios/integración con SQLite en memoria |
| **REAL PRODUCT CAPABILITY** | Capacidad que funciona con datos reales, sitios externos, formularios reales |

---

## Definición de estados

| Estado | Significado |
|--------|------------|
| `IMPLEMENTED` | Funciona end-to-end con datos reales. Unit + integration tests. Frontend conectado. |
| `PARTIAL` | Código existe, funciona en tests, pero faltan componentes críticos para uso real. |
| `MOCK_ONLY` | Código existe pero todos los LLM calls están mockeados. Sin validación real. |
| `NOT_CONNECTED` | Backend existe pero frontend no lo consume. |
| `MISSING` | No existe código ni estructura. |
| `NEEDS_REFACTOR` | Existe pero la arquitectura es incorrecta para el objetivo real. |

---

## 1 — Candidate Knowledge Base

**Estado: `PARTIAL`**

Lo que existe:
- Modelo `Candidate` con: name, email, location, target_roles, preferences, work_authorization, availability, career_goals, salary_min_usd, languages
- Modelo `CandidateSource`: source_type, source_url, raw_content, extracted_content
- Modelo `CandidateProfile`: extracted skills, experience, achievements, education, projects
- Modelo `EvidenceRecord`: claim, source_text, strength, evidence_type
- PUT /candidates/me acepta todos los campos del KB

Lo que falta:
- **No existe entidad `CandidateAnswer`**: respuestas pre-guardadas a preguntas estándar de aplicaciones (salary expectation, work authorization response, STAR stories). Cada aplicación genera sus respuestas desde cero.
- **Profile editor incompleto en frontend**: el UI de `/profile` edita campos básicos pero no permite editar experience[], projects[], skills[] con evidencia.
- **Sin Master CV concept**: no hay un CV base del candidato. Sólo versiones personalizadas per-application.
- **Languages no usadas en matching**: el campo existe en DB pero el motor no lo considera.

**Brecha real**: El sistema puede almacenar el perfil pero no puede responder preguntas de aplicación usando ese conocimiento de forma autónoma. Cada campo que no mapea directamente requiere intervención humana.

---

## 2 — Profile Intelligence

**Estado: `PARTIAL` / `MOCK_ONLY` en producción**

Lo que existe:
- `ProfileAgent` (`profile_agent.py`, 237 líneas): extrae skills, experience, projects, achievements de texto libre usando LLM con structured output
- `CandidateProfile` y modelos relacionados: `SkillExtracted`, `ExperienceExtracted`, `AchievementExtracted`, `ProjectExtracted`
- POST /candidates/me/analyze-source ejecuta el agente

Lo que falta:
- **Todos los tests usan mocks del LLM** — no hay validación de que el agente extrae correctamente de un CV real
- **Sin conflict resolution UI**: `profile.conflicts` es un campo JSON detectado por el agente, pero el frontend no muestra ni permite resolver conflictos entre fuentes
- **Sin profile quality score**: existe health score (completeness), pero no quality score (evidence coverage, achievement specificity, source consistency)
- **Sin GitHub API real**: solo acepta texto pegado, no hace fetch de repositorios reales

---

## 3 — Source Ingestion

**Estado: `PARTIAL`**

Lo que existe:
- `CandidateSource` con types: cv, linkedin, github, portfolio, manual
- POST /candidates/me/sources acepta URL o texto
- SSRF protection en source_url (validate_url_not_private)
- PDF extraction con PyMuPDF

Lo que falta:
- **GitHub source**: acepta el URL pero no hace fetch de la API de GitHub. El usuario pega texto.
- **LinkedIn source**: igual — acepta texto, no scraping (correcto por ToS, pero el campo es decorativo hoy)
- **Sin pipeline de ingesta real**: no hay worker/background task para procesar fuentes asíncronamente. Todo es síncrono en el request handler.
- **Sin deduplication de sources**: el mismo CV puede ingresarse múltiples veces

---

## 4 — Conflict Resolution

**Estado: `MISSING` en frontend**

Lo que existe:
- `profile.conflicts` almacenado como JSON en DB
- El ProfileAgent detecta y reporta conflictos entre fuentes

Lo que falta:
- **Sin UI de resolución**: el frontend no muestra conflictos ni permite al usuario decidir qué valor es correcto
- **Sin registro de decisión del usuario**: cuando el usuario elige entre fuentes conflictivas, esa decisión no se persiste
- **Sin re-extracción selectiva**: si el usuario corrige un conflicto, el sistema no sabe que debe recalcular la confianza de claims relacionados

---

## 5 — Job Discovery

**Estado: `PARTIAL`**

Lo que existe:
- `JobSource` Protocol en `base.py`
- `RemotiveAdapter` en `remotive.py`: fetch de API pública de Remotive
- GET /recommendations llama al recommender que llama a Remotive

Lo que falta:
- **Un solo adapter**: Remotive únicamente. Sin Indeed, LinkedIn Jobs, Greenhouse boards, Lever boards, Ashby boards.
- **Sin scheduler**: job discovery no corre automáticamente. Solo cuando el usuario abre /recommendations.
- **Sin notificaciones**: el sistema no alerta cuando aparece un job nuevo con match > threshold.
- **Sin búsqueda semántica**: solo búsqueda por keywords en título/descripción.

---

## 6 — Job Normalization

**Estado: `PARTIAL`**

Lo que existe:
- `JobAgent` parsea JD con structured output: title, company, seniority, tech_stack, requirements[], salary, location
- `SENIORITY_RANK` dict normaliza niveles

Lo que falta:
- **Sin pipeline explícito de normalización**: el normalization ocurre dentro del agente, no es un paso separado reutilizable
- **Salary normalization incompleta**: detecta rangos en USD pero no normaliza otras monedas ni formatos ("100k-150k" vs "$100,000-$150,000")
- **Tech stack normalization superficial**: "Python 3" y "Python" son considerados diferentes por el matching si no están en SKILL_SYNONYMS

---

## 7 — Job Deduplication

**Estado: `MISSING`**

Lo que existe:
- Ninguna lógica de deduplicación

Lo que falta:
- Hash/fingerprint de JD normalizada
- Check antes de guardar: ¿existe job similar (company, title, location) en últimos N días?
- El mismo trabajo puede guardarse N veces por el mismo candidato

---

## 8 — Job Description Intelligence

**Estado: `PARTIAL` / `MOCK_ONLY` en producción**

Lo que existe:
- `JobAgent` con structured output: title, company, seniority, tech_stack, requirements[], must_have/nice_to_have, salary, visa_sponsorship, parsing_confidence
- `JobRequirement` con requirement_type, category, is_required, seniority_signal, classification (MANDATORY/PREFERRED/INFERRED)

Lo que falta:
- **Todos los tests mockeados**: no hay validación de que el agente extrae correctamente de JDs reales
- **Sin company intelligence separada**: company_description está en el Job, no en una entidad CompanyProfile propia
- **classification field (MANDATORY/PREFERRED/INFERRED)** existe en DB pero el agente no siempre lo llena — campo opcional sin validación de cobertura

---

## 9 — Company Intelligence

**Estado: `MISSING`**

Lo que existe:
- `company_description: Text` en el modelo Job (campo simple)

Lo que falta:
- Entidad `CompanyProfile` separada: industry, size, culture_signals, tech_signals, growth_stage
- Company reusable entre múltiples jobs del mismo candidato (o entre candidatos)
- Company research agent
- Integración con fuentes públicas (Crunchbase, LinkedIn Company, Glassdoor datos públicos)

---

## 10 — Semantic Skill Matching

**Estado: `PARTIAL`**

Lo que existe:
- `SKILL_SYNONYMS` en engine.py: 25+ grupos de aliases
- Función `expand_skills()` que normaliza antes de comparar
- Matching usa el conjunto expandido

Lo que falta:
- **Sin embeddings semánticos**: "data pipeline engineering" ≠ "ETL development" para el matcher actual, aunque son sinónimos en la industria
- **Sin pgvector**: la infraestructura de similaridad semántica está documentada pero no implementada
- **SKILL_SYNONYMS manual**: crecer este dict es O(n²) por persona. No escala.
- **Sin skill taxonomy**: no hay jerarquía (Python → Programming Language → Technology)

---

## 11 — Requirement-by-Requirement Matching

**Estado: `MISSING`**

Lo que existe:
- El matching suma skills como conjunto (intersection / union)
- `matched_skills` y `missing_skills` como listas en la respuesta

Lo que falta:
- **Coverage por requirement**: para cada `JobRequirement`, computar cobertura individual con evidencia
- Estructura esperada:
  ```
  {requirement: "5 years Python", importance: 0.9,
   candidate_match: 0.85, evidence: "Experience #3 (DataCo, 3 years)", confidence: 0.91}
  ```
- Breakdown visible en UI (ni backend ni frontend implementado)
- Sin considerar years-of-experience requeridos vs reales del candidato

---

## 12 — Hard Constraints

**Estado: `IMPLEMENTED` (BACKEND FOUNDATION)**

Lo que existe:
- `check_hard_constraints()` en engine.py: seniority gap > 2, salary gap > 30%, work_authorization vs visa_sponsorship
- `HardConstraintResult(blocked, blockers)` 
- Integrado en el flujo de match, `application_decision = "BLOCKED"` cuando dispara
- Tests unitarios confirman los 3 casos

Limitaciones:
- **Solo 3 constraints**: no verifica certifications requeridas, clearances de seguridad, requisitos geográficos estrictos
- **work_authorization binario**: sólo bloquea cuando `visa_required + job offers no sponsorship`. Otros casos (OPT, TN visa, etc.) no distinguidos.
- **Salary blocker unidireccional**: no bloquea si el candidato tiene un mínimo altísimo vs mercado general

---

## 13 — Job Fit

**Estado: `PARTIAL`**

Lo que existe:
- Scoring determinístico 4 componentes: skill_overlap (40%), experience (30%), location (20%), education (10%)
- LLM reasoning layer: score + reasoning + strengths + gaps
- Hybrid score: deterministic * 0.6 + LLM * 0.4
- Tiers: excellent/strong/moderate/weak/poor
- `MatchAnalysis` en DB con todos los campos

Limitaciones:
- **Skill matching por keywords**: no semántico (ver ítem 10)
- **Experience score sólo por years**: no considera relevancia del dominio, type de empresa, scope
- **Location score básico**: match de string, no geográfico real
- **Education score minimal**: cualquier educación vs "requiere degree" — no verifica campo de estudio
- **Sin per-requirement breakdown** (ver ítem 11)

---

## 14 — Career Fit

**Estado: `PARTIAL`**

Lo que existe:
- `compute_career_fit()` en engine.py: computa score [0,1] basado en seniority gap y salary alignment
- `career_fit_score` en `MatchAnalysis` DB model y respuesta de API
- Distinción: gap=0 → 0.90, gap=+1 → 1.00, gap=+2 → 0.55

Limitaciones:
- **Sólo 2 dimensiones**: seniority gap + salary. Sin domain growth, scope match, trajectory alignment
- **Sin LLM reasoning para career fit**: el LLM match agent sólo produce job fit reasoning
- **No visible en frontend**: el campo existe en DB y API response pero MatchScoreCard no lo muestra

---

## 15 — Application Decision

**Estado: `IMPLEMENTED` (BACKEND FOUNDATION)**

Lo que existe:
- `decide_application()` en engine.py: BLOCKED / DO_NOT_APPLY / LOW_FIT / STRETCH / APPLY_WITH_CUSTOMIZATION / APPLY
- Lógica clara y determinística
- `application_decision` en `MatchAnalysis` y schema de respuesta

Limitaciones:
- **Frontend muestra decisión como texto** pero no la usa para guiar el flujo (no bloquea si decisión = DO_NOT_APPLY)
- **Sin "what_would_change_this_decision"**: guía al candidato sobre qué habilidades adquirir para mejorar el fit
- **Decisión no considera historial de aplicaciones**: si el candidato ya aplicó y fue rechazado, no se refleja

---

## 16 — Job Recommendation

**Estado: `PARTIAL`**

Lo que existe:
- `job_recommender.py`: fetch de Remotive + keyword scoring
- GET /recommendations con paginación
- Frontend `/recommendations` page

Limitaciones:
- **Scoring simple**: count de keywords del target_role en título/descripción. No usa el motor de matching real.
- **Sin personalización profunda**: no considera work_authorization, salary_min, career_fit
- **Sin ranking**: lista de jobs sin ordenar por fit
- **Un solo source**: Remotive. Sin agregación multi-source.
- **Sin "estas son las 7 a las que aplicar"**: no produce shortlist priorizada

---

## 17 — Application Strategy

**Estado: `PARTIAL` / `MOCK_ONLY` en producción**

Lo que existe:
- `ApplicationAgent` (`application_agent.py`): genera approach, positioning, cv_changes, cover_letter_key_points, answer_strategies con LLM
- `ApplicationStrategy` guardado en `application.strategy_json`
- POST /applications/{id}/strategy route

Limitaciones:
- **Tests con mock LLM**: sin validación de calidad real
- **Strategy no se actualiza si cambia el perfil**: generada una vez, no recomputable incrementalmente
- **Sin A/B testing de estrategias**: no se rastrea qué estrategias llevan a más entrevistas

---

## 18 — Master CV

**Estado: `MISSING`**

Lo que existe:
- `CVVersion` per-application: versión personalizada del CV para cada trabajo

Lo que falta:
- **Entidad Master CV**: el CV base del candidato del que parten las personalizaciones
- **Sin versionado del Master CV**: si el candidato actualiza su experiencia, no hay diff vs versión anterior
- **Sin export del Master CV**: solo se generan versiones personalizadas

---

## 19 — Personalized CV

**Estado: `PARTIAL` / `MOCK_ONLY` en producción**

Lo que existe:
- `CVAgent` (`cv_agent.py`): genera summary_adapted, changes[], skills_ordered, headline_adapted con LLM
- `CVChange` con original, adapted, rationale, evidence_ref
- POST /applications/{id}/cv route
- Frontend muestra CV adaptado con comparación original vs adaptado
- PDF generation con ReportLab

Limitaciones:
- **Tests con mock LLM**: sin validación de que la adaptación es correcta o no alucina
- **claim_validator usado post-generación**: valida claims pero no impide generación de contenido sin evidencia
- **Sin per-section evidence map**: no hay un grafo que trace claim → evidence_record en el CV final
- **PDF generado localmente**: no hay upload del PDF a storage accesible para adjuntar a formularios

---

## 20 — CV Evidence Validation

**Estado: `PARTIAL` — NEEDS_REFACTOR**

Lo que existe:
- `ClaimValidator` con `SUPPORTED / PLAUSIBLE / UNSUPPORTED` classification
- Basado en keyword overlap: ≥3 keywords → SUPPORTED, 1-2 → PLAUSIBLE, 0 → UNSUPPORTED
- Integrado en POST /applications/{id}/cv

Limitaciones:
- **Keyword overlap ≠ semantic validation**: "led migration of 50TB Redshift warehouse" puede tener pocas palabras en común con el evidence record aunque sea la misma experiencia
- **Sin cómputo de years-of-experience**: "5 years SQL" requiere sumar las experiencias reales donde SQL aparece
- **Sin temporal consistency**: no verifica que las fechas de experiencias sumen correctamente
- **Threshold arbitrario**: 3 keywords es un número sin calibración

---

## 21 — Cover Letter

**Estado: `PARTIAL` / `MOCK_ONLY` en producción**

Lo que existe:
- `CommunicationAgent` (`communication_agent.py`): genera cover letter con key_points_addressed
- POST /applications/{id}/cover-letter
- Frontend muestra cover letter generada

Limitaciones:
- **Tests con mock LLM**
- **Sin template system**: una sola estructura de cover letter
- **Sin tono adaptado a cultura de empresa**: no usa company_intelligence
- **Sin versiones**: se regenera, no se versiona

---

## 22 — Application Answers

**Estado: `PARTIAL` / `MOCK_ONLY` en producción**

Lo que existe:
- Endpoint para generar respuestas a preguntas específicas de aplicaciones con LLM
- Frontend tiene textarea para pegar preguntas y generar respuestas
- `answer_strategies` en ApplicationStrategy

Limitaciones:
- **Sin `CandidateAnswer` entity**: respuestas generadas no se persisten como conocimiento reutilizable del candidato
- **Sin STAR story library**: el candidato no tiene stories pre-construidas para situaciones comunes
- **Tests con mock LLM**

---

## 23 — Application Knowledge Base

**Estado: `MISSING`**

Lo que falta:
- Entidad `CandidateAnswer`: respuestas estándar del candidato a preguntas frecuentes de aplicaciones
- Tipos semánticos: salary_expectation, work_authorization_text, why_interested, greatest_strength, career_goal
- Respuestas usadas como input por form intelligence para campos custom_essay
- Esto es diferente a generar desde cero con LLM cada vez

---

## 24 — Form Intelligence

**Estado: `PARTIAL` — NEEDS_REFACTOR**

⚠️ **DISTINCIÓN CRÍTICA**: POST /applications/{id}/form NO descubre formularios reales.

Lo que existe:
- `form_intelligence.py`: clasificación semántica por regex de 18 tipos. Función pura, sin I/O.
- `ApplicationForm` y `ApplicationFormField` en DB con auto_fill_value, human_required, human_answer
- `ApplicationFormService` (route forms.py): acepta lista de campos que el USUARIO especifica manualmente, clasifica y mapea
- GET/POST /applications/{id}/form, PATCH /applications/{id}/form/answer/{field_id}

Lo que falta:
- **El usuario tiene que ingresar los campos manualmente**: no hay descubrimiento automático del formulario
- **Regex ≠ semantic form understanding**: los patrones de regex cubren casos comunes pero falla en labels idiomáticos, multi-idioma, o preguntas creativas
- **Sin section detection**: formularios multi-sección (Personal → Experience → Questions → Review) no se modelan
- **Sin options detection**: selects, radios, checkboxes con opciones específicas requieren mapeo manual
- **Sin required field detection**: el sistema no sabe cuáles son realmente obligatorios en el sitio

---

## 25 — Real Browser Automation

**Estado: `MISSING`**

Lo que existe:
- Playwright pre-instalado en el container (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
- docker-compose.yml no incluye Playwright
- `requirements.txt` no incluye playwright

Lo que falta:
- **Cero código de browser automation**: no hay ningún archivo en el proyecto que use Playwright
- Sin `BrowserAutomationAdapter`
- Sin `PageInteractionService`
- Sin manejo de cookies, sessions, login flows de ATS
- Sin screenshot capture para evidencia de submission
- Sin manejo de CAPTCHAs (por diseño, requiere human-in-the-loop)

---

## 26 — Real Form Discovery

**Estado: `MISSING`**

Lo que falta:
- Abrir URL del application form con browser real
- Detectar estructura del formulario: fields, labels, types, required, options
- Detectar secciones y pasos (multi-step applications)
- Detectar JS-rendered forms (React, Angular) — no sólo HTML estático
- Detectar login-gated forms vs public forms
- Detectar ATS provider desde URL pattern o HTML fingerprint

---

## 27 — Generic Form Agent

**Estado: `MISSING`**

Lo que falta:
- Agente LLM que, dado un screenshot o HTML de un form desconocido, clasifica campos semánticamente
- Manejo de labels ambiguos o en otros idiomas
- Estrategia de retry cuando la clasificación es incierta
- Fallback a human-in-the-loop cuando confidence < threshold

---

## 28 — ATS Adapters

**Estado: `MISSING`**

Lo que existe:
- `job_sources/base.py` con `JobSource` Protocol (para discovery, no para submission)

Lo que falta:
- Adapters específicos para:
  - **Greenhouse**: `boards.greenhouse.io/[company]/jobs/[id]`
  - **Lever**: `jobs.lever.co/[company]/[id]`
  - **Ashby**: `jobs.ashbyhq.com/[company]`
  - **Workday**: `[company].wd1.myworkdayjobs.com`
  - **SmartRecruiters**: `careers.smartrecruiters.com/[company]`
  - **iCIMS**: `careers-[company].icims.com`
  - **Taleo**: `[company].taleo.net`
- Cada adapter necesita: login flow, form detection, field filling, file upload, submit, confirmation
- `ATSAdapter` Protocol base
- Registry para detección automática de ATS por URL pattern

---

## 29 — Field Semantic Mapping

**Estado: `PARTIAL` — NEEDS_REFACTOR**

Lo que existe:
- 18 tipos semánticos con regex-based classification
- `_ALWAYS_HUMAN` set para campos que nunca se auto-llenan
- `_CANDIDATE_FIELD_MAP` dict para mapeo determinístico

Lo que falta:
- **Sin mapeo de derived fields**: "years of Python experience" requiere calcular desde experiencias reales, no sólo un campo del candidato
- **Sin mapeo desde CandidateAnswer**: custom_essay y similar no pueden usar respuestas pre-guardadas
- **Sin confidence score**: todos los mapeos se tratan como binario (auto-fill o human-required)
- **Sin multi-field resolution**: fields como "Current Salary + Expected Salary" requieren lógica compuesta

---

## 30 — Candidate → Field Mapping

**Estado: `PARTIAL`**

Lo que existe:
- Mapeo directo de campos Candidate → form fields para: name, email, location, salary, work_authorization, availability
- first_name/last_name split desde candidate.name

Lo que falta:
- **Mapping desde experience**: "years of experience in X" requiere sumar de experience[]
- **Mapping desde education**: degree, major, graduation year, GPA
- **Mapping desde projects**: portfolio URL, top project description
- **Mapping desde certifications**: cert name, issuer, date
- **Generative mapping**: "describe your biggest achievement" → LLM con candidate context

---

## 31 — Automatic Field Filling

**Estado: `PARTIAL` — NOT_CONNECTED (a browser real)**

Lo que existe:
- `map_candidate_to_form()` devuelve `MappedField` con `auto_fill_value` para campos conocidos
- Los valores se guardan en DB en `ApplicationFormField.auto_fill_value`

Lo que falta:
- **Sin envío real al browser**: los valores están en DB pero ningún código los pone en un formulario real
- Sin typing simulation (algunos ATS detectan fills programáticos)
- Sin validation de formato (phone: "11 1234-5678" vs "+54 11 1234 5678")
- Sin retry cuando el campo rechaza el valor

---

## 32 — File Attachment

**Estado: `MISSING`**

Lo que falta:
- Upload del CV generado (PDF) a un file storage accesible
- Attach CV al formulario via browser automation (`<input type="file">`)
- Attach cover letter si el form tiene campo para ello
- Soporte de formatos: PDF, DOCX (algunos ATS requieren DOCX)
- MIME validation del archivo antes de adjuntar
- Sin file storage configurado (no hay S3/GCS/local storage para PDFs generados)

---

## 33 — Human-in-the-Loop

**Estado: `PARTIAL` — NOT_CONNECTED**

Lo que existe:
- `human_required: bool` en `ApplicationFormField`
- `human_answer: Text` en `ApplicationFormField`
- `human_fields_pending: int` en `ApplicationForm`
- PATCH /applications/{id}/form/answer/{field_id} para que el usuario responda
- Bloqueo del submit si human_fields_pending > 0

Lo que falta:
- **Frontend no implementado para form fields**: la aplicación workspace no muestra los campos del formulario al usuario. El código del backend existe pero el frontend no lo consume.
- Sin notificación push/email cuando se requiere input humano
- Sin contexto para el usuario: "¿por qué me preguntan esto?" no se explica
- Sin sugerencia de respuesta (el LLM podría sugerir basado en candidate context)

---

## 34 — Pre-Submit Validation

**Estado: `PARTIAL`**

Lo que existe:
- Check: `human_fields_pending > 0` → 422 antes de submit
- Check: no double-submit (409 si ya existe submission)

Lo que falta:
- **Sin validación de completeness de campos required**: el sistema no verifica que todos los campos `is_required=True` tienen valor
- Sin validación de formato de valores (email, phone, URL)
- Sin "preview mode": el usuario no puede revisar todos los campos antes de confirmar submit

---

## 35 — REAL Submit

**Estado: `MISSING` — ⚠️ DISTINCIÓN CRÍTICA**

⚠️ **POST /applications/{id}/submit NO envía la aplicación a ningún sitio externo.**

Lo que existe:
- POST /applications/{id}/submit: registra en DB que una aplicación fue enviada manualmente
- Crea `ApplicationSubmission` con confirmation_number, submission_url ingresados por el usuario
- Cambia application.status a "applied"

Lo que falta:
- **Browser automation que navegue al form y haga click en submit**
- **Detección de confirmation page**: el sistema no navega a la confirmación
- **Captura automática del confirmation number**: el usuario lo ingresa manualmente
- **Screenshot como evidencia de submission**
- Sin manejo de errores en submit (validation errors del ATS, session timeout, CAPTCHA)

---

## 36 — Submission Confirmation

**Estado: `PARTIAL` — MANUAL ONLY**

Lo que existe:
- `ApplicationSubmission` en DB: confirmation_number, submission_url, submitted_via, notes
- El usuario puede ingresar manualmente el número de confirmación

Lo que falta:
- **Captura automática de confirmation desde el browser**: detección de "Application submitted", "Your application has been received", pattern matching de confirmation IDs
- Sin screenshot almacenado como evidencia
- Sin hash/checksum de la confirmación para detectar falsificaciones

---

## 37 — Application Tracking

**Estado: `PARTIAL`**

Lo que existe:
- `Application` con status state machine: draft → ready → applied → reviewing → interview → offer → rejected
- `ApplicationEvent` log con event_type y metadata JSON
- GET /applications con listado y estadísticas
- Frontend `/applications` lista las aplicaciones con estado

Lo que falta:
- **Sin tracking automático de cambios de estado**: requiere actualización manual
- Sin email parsing para detectar respuestas del employer
- Sin integración con LinkedIn para detectar "Application viewed"
- Sin follow-up reminders (la fecha de follow_up_date existe en DB pero no hay scheduler)
- Funnel analytics existe pero sin drill-down por empresa/rol/stack

---

## 38 — Follow-up

**Estado: `MISSING`**

Lo que existe:
- `follow_up_date: Date` en `Application` model
- El usuario puede setear la fecha en el UI

Lo que falta:
- **Sin notificaciones**: no hay scheduler que avise cuando llega la fecha
- Sin templates de follow-up email
- Sin tracking de si se envió el follow-up
- Sin LLM-generated follow-up messages

---

## 39 — Interview Intelligence

**Estado: `PARTIAL` / `MOCK_ONLY` en producción**

Lo que existe:
- `InterviewAgent` (`interview_agent.py`): genera probable questions, STAR stories, company research points
- `Interview` model en DB
- POST /applications/{id}/interview-prep
- Frontend `/applications/[id]/interview-prep` page

Limitaciones:
- **Tests con mock LLM**
- **Sin personalización real**: las preguntas no están calibradas con evidencia de lo que el candidato realmente sabe
- **Sin mock interview**: no hay flujo de práctica
- **Sin post-interview capture**: no se registra qué preguntas se hicieron realmente

---

## 40 — Outcome Tracking

**Estado: `IMPLEMENTED` (BACKEND FOUNDATION)**

Lo que existe:
- `outcome: str | None` en `MatchAnalysis`
- POST /jobs/{id}/match/feedback con outcome value
- Frontend muestra modal de feedback con opciones de outcome
- Outcome alimenta el learning loop (compute_calibration)

Limitaciones:
- **Frontend envía al endpoint correcto**: IMPLEMENTED en flujo completo
- **Sin reminder para registrar outcome**: el usuario puede olvidarse de actualizar

---

## 41 — Outcome Analytics

**Estado: `PARTIAL`**

Lo que existe:
- GET /stats/summary: funnel básico (applied, interviewed, offers)
- Frontend `/analytics` con KPI tiles y funnel visual

Lo que falta:
- **Sin breakdown por empresa/rol/tecnología/seniority**
- **Sin cohort analysis**: outcomes de aplicaciones de hace 3 meses
- **Sin benchmark externo**: el candidato no sabe si su tasa de entrevistas es buena o mala

---

## 42 — Learning Loop

**Estado: `PARTIAL` — NEEDS_REFACTOR**

Lo que existe:
- `learning_loop.py`: `compute_calibration()` calcula calibration_score (actual/expected interview rate) por tier
- `TierInsight` con interview_rate, rejection_rate, expected_interview_rate
- GET /candidates/me/learning-insights expone el reporte
- 14 tests unitarios e integración

Lo que falta:
- **No ajusta los pesos del motor**: el learning loop produce un reporte, pero ningún código usa ese reporte para cambiar `WEIGHTS` en engine.py
- **Sin feedback loop real**: los insights son descriptivos, no prescriptivos para el sistema
- **Sin umbral de confianza**: con 5 outcomes (MIN_OUTCOMES_FOR_CALIBRATION) el cálculo tiene alta varianza
- **Sin A/B testing infrastructure**: para comparar versiones del motor con pesos ajustados

---

## 43 — AI Evaluation

**Estado: `IMPLEMENTED` (como framework)**

Lo que existe:
- `ai_evaluation.py`: `EvalCriterion`, `EvalReport`, `evaluate()`, 5 factory functions
- `test_ai_evaluation.py`: 20 tests unitarios del framework
- Framework es correcto y extensible

Limitaciones:
- El framework existe pero **no está integrado en ningún endpoint de producción**. No hay respuesta de API que devuelva un EvalReport.
- Los criterios son estructurales, no semánticos (no evalúa "¿esta CV adaptación es realmente mejor?")

---

## 44 — Real AI Tests

**Estado: `MOCK_ONLY` / `MISSING`**

Lo que existe:
- `test_smoke.py`: 5 smoke tests para los 4 agentes principales
- Auto-skipped cuando ANTHROPIC_API_KEY no está configurada

Lo que falta:
- **Tests nunca corrieron con API key real en CI**: todos los tests pasan pero ninguno valida LLM output real
- **Sin eval corpus**: sin candidatos sintéticos, sin JDs de ejemplo, sin ground truth
- **Sin regression tests**: si el prompt del JobAgent cambia, no hay test que lo detecte
- **Smoke tests validan estructura, no calidad**: `field_not_empty("title", min_length=3)` pasa con "A" en title

---

## 45 — Prompt Versioning

**Estado: `MISSING`**

Lo que falta:
- Prompts hardcodeados en cada agente como string constants
- Sin sistema de versionado (v1, v2, etc.)
- Sin A/B testing de prompts
- Sin rollback a versión anterior si un prompt empeora la calidad
- Sin registro de qué versión de prompt generó cada output

---

## 46 — Model Routing

**Estado: `MISSING`**

Lo que existe:
- `claude-haiku-4-5-20251001` hardcodeado en todos los agentes como `MODEL_*` constant

Lo que falta:
- Routing por tarea: tareas de alta precisión (CV generation) → modelo más capaz; tareas rápidas (field classification) → haiku
- Sin fallback si el modelo está indisponible
- Sin config centralizado de modelos por rol

---

## 47 — Evidence Graph

**Estado: `MISSING`**

Lo que existe:
- `EvidenceRecord` con source_text, claim, strength
- `evidence_ref` en CVChange referencia un evidence_record conceptualmente

Lo que falta:
- **Sin grafo real**: no hay estructura que trace `source → evidence_record → claim → application_content`
- No es posible responder "¿en qué me baso para decir 'lideré migración de 50TB'?"
- Sin visualización del grafo
- `evidence_ref` es un string libre, no una FK al evidence record

---

## 48 — RAG

**Estado: `MISSING`**

Lo que existe:
- `docs/11-RAG.md`: documentación de la arquitectura RAG planeada
- `redis` en requirements.txt (instalado, no usado para RAG)

Lo que falta:
- Embeddings de candidate data (experiencias, proyectos, skills con contexto)
- pgvector extension en PostgreSQL
- Indexado de EvidenceRecords en vector space
- Retrieval: "dado este campo de formulario, ¿qué experiencias del candidato son más relevantes?"
- El matching usa keyword expansion en Python puro (funciona para MVP, no escala)

---

## 49 — Semantic Search / pgvector

**Estado: `MISSING`**

Lo que falta:
- pgvector no está instalado en el PostgreSQL del docker-compose
- Sin modelos de embedding en requirements.txt (no hay sentence-transformers, no hay OpenAI embeddings)
- Sin vectorization pipeline
- Sin similarity search en ningún endpoint

---

## 50 — Cost Tracking

**Estado: `IMPLEMENTED`**

Lo que existe:
- `cost_tracker.py`: `track_call()` registra model, input_tokens, output_tokens en lista en memoria
- `COST_PER_MILLION_TOKENS` dict con rates por modelo
- Logs de cada LLM call con costo estimado
- GET /stats/summary incluye LLM cost en respuesta

Limitaciones:
- **In-memory sólo**: al reiniciar el servidor se pierde la historia. Sin persistencia en DB.
- **Rates desactualizados**: el dict de rates puede quedar desactualizado con cambios de pricing

---

## 51 — Caching

**Estado: `MISSING`**

Lo que existe:
- `REDIS_URL` en config, redis en requirements.txt

Lo que falta:
- **Redis no está en uso**: ningún endpoint cachea nada con Redis
- Sin cache de JD parsing (el mismo JD procesado dos veces hace 2 LLM calls)
- Sin cache de embeddings
- Sin cache de profile extraction
- Sin TTL management

---

## 52 — Security

**Estado: `PARTIAL`**

Lo que existe:
- JWT access + refresh tokens con HMAC-SHA256
- Password hashing con pbkdf2
- Security headers middleware (CSP, X-Frame-Options, HSTS)
- Rate limiting con SlowAPI (200/min dev, 5/min prod) en auth endpoints
- SSRF protection en source_url (validate_url_not_private)
- Ownership checks en todas las entidades

Lo que falta:
- **MIME validation por magic bytes** (sólo valida content_type header, no el contenido real del archivo)
- **Account deletion / GDPR**: DELETE /candidates/me no existe
- Refresh token en localStorage (debería ser httpOnly cookie)
- Sin token revocation (no hay blacklist de refresh tokens)

---

## 53 — Prompt Injection

**Estado: `MISSING`**

Lo que falta:
- Sin tests de adversarial input (JDs con "Ignore previous instructions...")
- El JobAgent procesa el raw_jd directamente. Un JD malicioso podría intentar manipular la extracción.
- Sin sanitización de contenido externo antes de pasarlo al LLM
- `docs/13-SECURITY.md` menciona el riesgo pero sin implementación

---

## 54 — Privacy

**Estado: `PARTIAL`**

Lo que existe:
- Ownership isolation: cada candidato sólo ve sus propios datos
- No se usan datos de candidatos en datasets de evaluación (fixtures sintéticos)

Lo que falta:
- **Sin account deletion**: sin forma de que el usuario elimine todos sus datos
- Sin data export (GDPR Art. 20: portabilidad)
- Sin data retention policy implementada
- Sin logs de acceso auditables

---

## 55 — Observability

**Estado: `PARTIAL`**

Lo que existe:
- Structured logging con structlog
- Request ID middleware (X-Request-ID header)
- LLM call logging con model, tokens, cost
- Error logging en exception handlers

Lo que falta:
- **Sin métricas**: no hay Prometheus, Grafana, ni dashboard de salud
- Sin distributed tracing (ningún Jaeger/Zipkin/OTel)
- Sin alertas: no hay configuración de alertas cuando el error rate sube
- Sin SLA monitoring

---

## 56 — Frontend Integration

**Estado: `PARTIAL` — NOT_CONNECTED en áreas nuevas**

Lo que existe (conectado):
- Auth (register, login, refresh), onboarding
- Profile (health score, sources, edit básico)
- Jobs (add, list, detail, match, outcome)
- Applications workspace (strategy, cv, cover letter, answers, interview prep)
- Analytics dashboard
- Recommendations

Lo que falta (NOT_CONNECTED):
- **ApplicationForm**: POST /applications/{id}/form, GET fields, PATCH field answer — sin página en frontend
- **Submission**: POST /applications/{id}/submit, GET /submit — sin flujo en frontend
- **Learning insights**: GET /candidates/me/learning-insights — sin página en frontend
- **Career fit**: campo en API response pero no mostrado en MatchScoreCard
- **Application Decision breakdown**: application_decision visible pero sin guidance para el usuario

---

## 57 — Golden E2E

**Estado: `PARTIAL` — BACKEND ONLY**

Lo que existe:
- `test_e2e.py`: 208 líneas, flujo completo via API:
  Register → Profile → Job → Match → Application → CV → Cover Letter → Form → Submit → Track

Lo que falta:
- **Sin browser automation**: el E2E no abre ningún navegador real
- **Sin ATS mock server local**: no existe un servidor web simulado que sirva formularios para test
- **Sin validación de UI**: el E2E testea API responses, no flujo de usuario real
- El "Submit" en el test registra una submission manual, no navega a ningún formulario externo

---

## 58 — Production Readiness

**Estado: `NOT_READY` — para el objetivo real del producto**

Está listo para demo de backend:
- ✅ 181 tests pasando
- ✅ 12 migraciones de Alembic
- ✅ Seguridad básica (auth, rate limiting, SSRF)
- ✅ LLM integration (Anthropic SDK, structured output)
- ✅ CI/CD con GitHub Actions

NO está listo para el objetivo del producto (AI Job Application Agent):
- ❌ No puede navegar formularios reales
- ❌ No puede enviar aplicaciones reales
- ❌ No tiene ATS adapters
- ❌ Frontend no consume el 30% de los nuevos endpoints
- ❌ Sin browser automation infrastructure
- ❌ Sin real AI validation (todos los tests de LLM mockeados)
- ❌ Sin file storage para CVs generados
- ❌ Sin queue/worker para tareas de larga duración (form navigation puede tardar 2-5 min)

---

## Resumen ejecutivo: BACKEND FOUNDATION vs REAL PRODUCT CAPABILITY

```
PIPELINE COMPLETO REQUERIDO:
─────────────────────────────────────────────────────────────────────
Candidate Profile          → PARTIAL  (KB existe, sin conflict resolution ni Master CV)
Job Discovery              → PARTIAL  (solo Remotive, sin scheduling)
Job Intelligence           → PARTIAL  (LLM parsing existe, sin company intelligence, sin dedup)
Job Fit                    → PARTIAL  (keyword-based, sin semantic, sin per-requirement)
Career Fit                 → PARTIAL  (2 dimensions, no conectado al frontend)
Application Decision       → IMPLEMENTED (determinístico, 6 categorías)
Application Strategy       → PARTIAL/MOCK_ONLY
Personalized CV            → PARTIAL/MOCK_ONLY (sin evidence graph, sin file storage)
Cover Letter               → PARTIAL/MOCK_ONLY
Application Answers        → PARTIAL/MOCK_ONLY (sin CandidateAnswer KB)
Form Discovery             → MISSING (el form intelligence es clasificación manual, no discovery)
Browser Automation         → MISSING (cero código)
ATS Adapters               → MISSING (ninguno)
Field Semantic Mapping     → PARTIAL/NEEDS_REFACTOR (regex, no semántico)
Automatic Field Filling    → PARTIAL/NOT_CONNECTED (a browser real)
File Attachment            → MISSING
Human-in-the-Loop          → PARTIAL/NOT_CONNECTED (frontend no conectado)
REAL Submit                → MISSING (POST /submit registra en DB, no navega el web)
Submission Confirmation    → PARTIAL/MANUAL (el usuario ingresa el número)
Application Tracking       → PARTIAL (sin tracking automático)
Learning Loop              → PARTIAL/NEEDS_REFACTOR (analiza pero no retroalimenta)
─────────────────────────────────────────────────────────────────────

CAPACIDADES DE INFRAESTRUCTURA:
Evidence Graph             → MISSING
RAG / pgvector             → MISSING
Semantic Search            → MISSING
Prompt Versioning          → MISSING
Model Routing              → MISSING
Caching                    → MISSING (Redis instalado, sin uso)
File Storage               → MISSING
Task Queue                 → MISSING (para tareas async de larga duración)
Real AI Tests              → MISSING (todos mockeados)
Prompt Injection Defense   → MISSING
ATS Mock for Testing       → MISSING
─────────────────────────────────────────────────────────────────────

CONTEO:
IMPLEMENTED     :  6 capacidades (Auth, Cost Tracking, Hard Constraints, 
                   Application Decision, Outcome Tracking, AI Eval Framework)
PARTIAL         : 24 capacidades (fundación existe, falta componente crítico)
MOCK_ONLY       :  8 capacidades (LLM agents sin validación real)
NOT_CONNECTED   :  5 capacidades (backend existe, frontend no consume)
MISSING         : 15 capacidades (cero implementación)
NEEDS_REFACTOR  :  3 capacidades (diseño incorrecto para objetivo real)
─────────────────────────────────────────────────────────────────────
```

---

## Próximo milestone: REAL APPLICATION AGENT

El gap más crítico no es el matching ni el CV — es que el sistema no puede:
1. Abrir un formulario de empresa real
2. Detectar sus campos
3. Llenarlos
4. Enviar la aplicación

Todo el backend construido hasta ahora es la **fundación correcta** para soportar ese flujo, pero el flujo real no existe. Los documentos `ARCHITECTURE_APPLICATION_AGENT.md` y `ROADMAP_REAL_AGENT.md` definen la arquitectura y el plan de implementación.
