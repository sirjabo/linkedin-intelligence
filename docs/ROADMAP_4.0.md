# LinkedIn Intelligence — Roadmap 4.0

> Versión: 4.0  
> Fecha: 2026-08-15  
> North Star: **ENTREVISTAS CALIFICADAS GENERADAS POR CANDIDATO ACTIVO**  
> Branch de desarrollo: `claude/new-session-ce0sct`  
> Fuente: `LINKEDIN_INTELLIGENCE_NEXT_MASTER_EXECUTION_DIRECTIVE.md` + auditoría de código real

---

## Principios del Roadmap

1. **El código real tiene prioridad sobre la documentación** — leer antes de implementar
2. **No inventar datos**: ningún campo de evaluación usa datos personales reales
3. **No auto-submit**: `human_confirmed=True` siempre requerido para submit final
4. **North Star primero**: cada sprint debe avanzar la métrica de entrevistas calificadas
5. **Tests primero**: acceptance criteria medibles antes de cerrar un sprint

---

## Sprint A — Real Personalized CV Engine

**Objetivo**: Producir CVs materialmente diferentes por tipo de JD — no solo resumen y orden de skills.

### Acceptance Criteria
- [ ] 1 candidato + 3 JDs distintos → 3 CVs con al menos 60% de bullets de experiencia distintos
- [ ] `CVChange` completo: section / bullet_index / original / adapted / reason / job_requirement / evidence_refs / confidence
- [ ] Pipeline de evaluación: factuality_score, personalization_score, differentiation_score
- [ ] PDF reconstruido incluye bullets personalizados de experience y projects
- [ ] 0 claims inventadas — toda modificación referencia `evidence_ref` de profile real

### Trabajo técnico
- `cv_agent.py`: añadir `_personalize_experience_bullets()` y `_personalize_projects()` — bullet-level edits con LLM
- `PersonalizedCV`: extender para incluir `experience_personalized: list[ExperiencePersonalized]`
- `cv_storage.py`: reconstruir PDF desde `PersonalizedCV.experience_personalized` en lugar de perfil crudo
- `ai_evaluation.py`: criterios `cv_factuality`, `cv_personalization_score`, `cv_differentiation`
- Tests: fixture con 1 candidato + 3 JDs; assert diferenciación mínima entre outputs

### Dependencias
- `profile_agent.py` ya produce `EvidenceRef` por skill — usar como fuente de evidence_refs
- `pdf_generator.py` ya está PRODUCTION_READY — adaptar para recibir bullets personalizados

---

## Sprint B — CandidateKnowledgeResolver 2.0

**Objetivo**: Responder con precisión "¿cuántos años de X?" extrayendo fechas reales de la experiencia.

### Acceptance Criteria
- [ ] `resolve("skill_years", skill="SQL")` → `ResolvedValue(answer="3 años", confidence=0.85, evidence_refs=[...])`
- [ ] Deduplicación de períodos solapados (job A 2020-2022 + job B 2021-2023 → 3 años, no 4)
- [ ] Confidence < 0.50 cuando el skill no aparece explícitamente en experience data
- [ ] Cache de resoluciones por `application_id` — no recomputar en mismo contexto

### Trabajo técnico
- `candidate_knowledge_resolver.py`:
  - `_resolve_skill_years(skill: str) → ResolvedValue`
  - `_extract_skill_periods(skill: str, experiences: list) → list[DateRange]`
  - `_deduplicate_periods(periods: list[DateRange]) → float`
  - Cache dict `_resolution_cache: dict[str, ResolvedValue]` por instancia
- `form_intelligence.py`: detectar SemanticType `skill_years` ("años de X", "years of X", "experience with X")
- Tests: fixture de profile con solapamiento de jobs; assert deduplicación correcta

### Dependencias
- Sprint A completo (evidence_refs disponibles)

---

## Sprint C — Evidence System 3.0

**Objetivo**: Validación real de claims — semantic + temporal + cross-source.

### Acceptance Criteria
- [ ] `validate_claims(cv_text, evidence_records)` recibe evidence_records reales (no `[]`)
- [ ] SUPPORTED: ≥3 matches semánticos o keyword  
- [ ] PLAUSIBLE: 1-2 matches  
- [ ] UNSUPPORTED: 0 matches  
- [ ] **CONTRADICTED**: claim contradice evidencia existente (ej: "5 años de Python" cuando profile dice 2)
- [ ] Validación temporal: claim sobre skill en período X verifica que experiencia cubra ese período
- [ ] Evidence_records conectados desde perfil real en `_run_intelligence_phase()`

### Trabajo técnico
- `claim_validator.py`:
  - `_semantic_similarity(claim: str, evidence: str) → float` usando pgvector o sentence-transformers
  - `_temporal_consistency(claim: str, experiences: list) → bool`
  - Estado `CONTRADICTED` con `contradiction_source: str`
- `orchestrator.py`: reemplazar `evidence_records=[]` con evidencia real construida desde `candidate_profile`
- Tests: fixture con claim verdadera, claim falsa, claim contradictoria

### Dependencias
- pgvector ya configurado en DB
- Sprint B (skill_years disponibles para comparar con claims)

---

## Sprint D — Matching Engine 3.0

**Objetivo**: Breakdown requirement-by-requirement con estado MATCHED/PARTIAL/MISSING/BLOCKER/UNCERTAIN.

### Acceptance Criteria
- [ ] Cada requisito del JD tiene: `text / type / importance / candidate_status / evidence_refs / match_score`
- [ ] `importance` distingue MUST/NICE_TO_HAVE (parseado del JD)
- [ ] Un BLOCKER en requisito MUST → decision = BLOCKED independiente del score agregado
- [ ] Hard constraints unchanged: seniority gap >2, salary gap >30%, visa requerida sin sponsorship
- [ ] Score agregado = weighted average por importance con evidence boost
- [ ] Semantic match por embedding para skills sin sinónimo exacto

### Trabajo técnico
- `matching/engine.py`:
  - `RequirementMatch` dataclass: text, type, importance, candidate_status, evidence_refs, match_score
  - `_parse_requirements(jd_text: str) → list[Requirement]` — LLM extrae req estructurados
  - `_match_requirement(req: Requirement, profile: dict) → RequirementMatch`
  - `MatchResult` extendido: añadir `requirements: list[RequirementMatch]`
- Frontend: vista req-by-req en applications/[id]
- Tests: JD con MUST y NICE_TO_HAVE; candidato sin MUST → BLOCKED; candidato con todo → APPLY

### Dependencias
- Sprint C (evidence_refs reales disponibles para match)

---

## Sprint E — Application Strategy 2.0

**Objetivo**: Estrategia completa, accionable, company-specific.

### Acceptance Criteria
- [ ] `ApplicationStrategy` incluye: positioning, target_narrative, keywords_for_form, answer_strategy (por tipo de pregunta), interview_preparation_strategy, claims_to_avoid, company_specific_angle
- [ ] `company_specific_angle` referencia datos reales del JD (producto, equipo, stack mencionado)
- [ ] `keywords_for_form`: lista de keywords ATS a incluir en respuestas de texto libre
- [ ] `answer_strategy`: mapa de question_type → estrategia de respuesta (STAR, motivational, technical)

### Trabajo técnico
- `application_agent.py`: extender prompt con todos los campos faltantes
- `ApplicationStrategy` schema: añadir 7 campos faltantes
- `communication_agent.py`: usar `answer_strategy` del strategy para generar `AnswerResult` más contextualizado
- Tests: assert que company_specific_angle menciona algo del JD real

### Dependencias
- Sprint D (match req-by-req informa strengths_to_emphasize y claims_to_avoid)

---

## Sprint F — Form Intelligence 2.0

**Objetivo**: Clasificación semántica robusta con tipos completos y confidence scoring.

### Acceptance Criteria
- [ ] SemanticType `skill_years` detectado en "How many years of Python/SQL/React?"
- [ ] SemanticType `experience_essay` detectado en "Describe a project where..."
- [ ] `MappedField` incluye: `confidence: float`, `classification_source: "regex"|"llm"`, `skill_target: str | None`
- [ ] Cache de clasificación por hash(label+placeholder+surrounding_text) por formulario
- [ ] LLM fallback solo para campos con confidence < 0.70

### Trabajo técnico
- `form_intelligence.py`:
  - Añadir regex patterns para `skill_years` y `experience_essay`
  - `MappedField`: añadir campos `confidence`, `classification_source`, `skill_target`
  - Cache en-memory por sesión de formulario
- `candidate_knowledge_resolver.py`: conectar resolver de `skill_years` con Sprint B
- Tests: 25+ fixture fields; assert classification_source correcto

### Dependencias
- Sprint B (skill_years resolver)

---

## Sprint G — Real ATS Adapters

**Objetivo**: Greenhouse, Lever y Workday funcionando en el 80% de casos reales.

### Acceptance Criteria
- [ ] Greenhouse: maneja EEO section, preguntas voluntarias, multi-step tracking con nombre de sección actual
- [ ] Lever: extrae y llena custom questions, detecta errores de validación del servidor
- [ ] Workday: maneja wizard con secciones dinámicas, detecta required fields faltantes
- [ ] Capability matrix documentada: qué soporta cada adapter
- [ ] Retry con exponential backoff en timeout de red (2s, 4s, 8s, 16s)
- [ ] Screenshot en cada transición de página

### Trabajo técnico
- `ats/greenhouse.py`: `_handle_eeo_section()`, `_get_current_section_name()`, voluntary questions
- `ats/lever.py`: `_extract_custom_questions()`, `_check_validation_errors()`
- `ats/workday.py`: `_handle_dynamic_sections()`, auth detection
- `ats/base.py`: `retry_with_backoff()` decorator compartido
- `ats/capability_matrix.py`: dict de capabilities por ATS
- Tests con Playwright headless contra HTML fixtures de cada ATS

### Dependencias
- Sprint F (Form Intelligence 2.0 para clasificar campos ATS complejos)

---

## Sprint H — File Upload Engine

**Objetivo**: Upload confiable de CV y cover letter en cualquier ATS.

### Acceptance Criteria
- [ ] Antes de upload: verificar que el archivo exista y sea válido (PDF < 10MB)
- [ ] Cover letter puede subirse como archivo .docx o .txt además de .pdf
- [ ] Detección de campo file_upload antes de intentar upload
- [ ] Error claro si ATS rechaza el formato

### Trabajo técnico
- `orchestrator.py` → `_get_file_path()`: validación de existencia + tamaño
- `candidate_knowledge_resolver.py`: resolver `cover_letter_file` además de `cover_letter_text`
- `form_intelligence.py`: SemanticType `file_upload` con sub-tipo `cv_file` / `cover_letter_file`
- Tests: mock de file input en Playwright

### Dependencias
- Sprint G (ATS adapters estables)

---

## Sprint I — Submission State Machine 2.0

**Objetivo**: State machine robusta con pausa, resume, y evidencia completa.

### Acceptance Criteria
- [ ] Estado PAUSED: formulario parcialmente completado, candidato puede corregir y resumir
- [ ] `resume_from_field(field_id)`: retoma fill desde campo específico sin reiniciar
- [ ] `ApplicationSubmission` incluye: confirmation_id, screenshots, form_data_submitted, timestamp
- [ ] Frontend muestra confirmation_id y screenshot de confirmación
- [ ] Retry automático (1 vez) ante fallo de browser con logging claro

### Trabajo técnico
- `orchestrator.py`: estado PAUSED + `_resume_from_field()`
- DB migration: `ApplicationSubmission` con campos de evidencia completos
- Frontend: mostrar evidence de submission en applications/[id]
- Tests: simular fallo mid-fill; assert estado persiste correctamente

### Dependencias
- Sprint H (file upload confiable antes de state machine robusta)

---

## Sprint J — Application Control Center (Frontend)

**Objetivo**: UI completa que muestra todo el trabajo del backend a los candidatos.

### Acceptance Criteria
- [ ] CV download link funcional desde la vista de aplicación
- [ ] Diff view: original vs personalizado por sección (summary, experience, skills)
- [ ] Strategy panel: ApplicationStrategy completa expandible
- [ ] Req-by-req match: tabla MATCHED/PARTIAL/MISSING/BLOCKER
- [ ] Submission evidence: confirmation_id + screenshot thumbnail
- [ ] Estado PAUSED con campos editables in-situ

### Trabajo técnico
- `applications/[id]/page.tsx`: añadir CV download, diff view, strategy panel, req panel, evidence panel
- API endpoint: `GET /applications/{id}/cv` → PDF download
- API endpoint: `GET /applications/{id}/strategy` → ApplicationStrategy JSON
- API endpoint: `GET /applications/{id}/requirements` → MatchResult con requirements[]
- Tests: Playwright E2E para cada panel

### Dependencias
- Sprints D, E, I (datos disponibles)

---

## Sprint K — AI Evaluation Expansion

**Objetivo**: Evaluación semántica con LLM judge para CV, cover letter y factualidad.

### Acceptance Criteria
- [ ] `cv_factuality_score`: LLM verifica que cada claim del CV esté respaldada por evidencia
- [ ] `cv_personalization_score`: % de bullets que mencionan algo específico del JD
- [ ] `cv_differentiation_score`: distancia promedio entre 3 CVs para mismo candidato
- [ ] `cover_letter_cliche_score`: detección de frases genéricas ("I am passionate about...")
- [ ] `cover_letter_company_hook_score`: menciona algo específico de la empresa
- [ ] Test suite E2E con modelo real (`claude-haiku-4-5-20251001`) en ≥5 candidatos sintéticos

### Trabajo técnico
- `ai_evaluation.py`: `LLMEvaluationCriterion` base class con LLM judge
- Criterios: `CVFactualityCriterion`, `CVPersonalizationCriterion`, `CoverLetterClicheCriterion`, `CoverLetterHookCriterion`
- Test suite con datos sintéticos (no datos reales): 5 perfiles ficticios + JDs reales públicas
- Tests: assert scores dentro de rangos esperados por tipo de CV bueno vs malo

### Dependencias
- Sprint A (CV personalizado real para evaluar)
- Sprint C (evidence system real para factualidad)

---

## Sprint L — Recommendation 3.0 + Outcomes + Learning

**Objetivo**: Learning loop activo que retroalimenta el sistema con resultados reales.

### Acceptance Criteria
- [ ] `calibration_report` actualiza `APPLY_THRESHOLD` cuando bias_direction es estable por ≥10 outcomes
- [ ] A/B framework: candidatos aleatoriamente asignados a estrategia A vs B; outcome logging por grupo
- [ ] Hypothesis testing: p-value para diferencia entre grupos A y B
- [ ] `rank_jobs()` incorpora signal de outcomes: skill que generó entrevistas recibe boost en IDF
- [ ] Recomendaciones de perfil: "Agregar X skill mejoraría tu match en N empleos de tu target"

### Trabajo técnico
- `learning_loop.py`: `_update_thresholds()` cuando MIN_OUTCOMES ≥ 10
- `job_recommender.py`: `_outcome_boosted_idf()` usando historial de outcomes por skill
- `applications.py`: endpoint `POST /experiments` para A/B assignment
- Hypothesis testing: scipy.stats.chi2_contingency para interview rate A vs B
- Tests: fixture de 15+ outcomes; assert threshold update correcto

### Dependencias
- Sprint K (evaluación de calidad disponible como señal adicional)

---

## Timeline estimado

| Sprint | Duración estimada | Bloqueante de |
|--------|------------------|---------------|
| A — CV Engine | 3–4 días | K, J |
| B — Knowledge Resolver | 2–3 días | C, F |
| C — Evidence System | 3–4 días | D, K |
| D — Matching 3.0 | 3–4 días | E, J |
| E — Strategy 2.0 | 2 días | J |
| F — Form Intelligence | 2 días | G |
| G — ATS Adapters | 4–5 días | H |
| H — File Upload | 1–2 días | I |
| I — State Machine | 2–3 días | J |
| J — Frontend | 3–4 días | — |
| K — AI Evaluation | 3–4 días | L |
| L — Learning 3.0 | 3–4 días | — |

**Total estimado**: 31–43 días de desarrollo

---

## Definición de "Listo" por sprint

Un sprint está cerrado cuando:
1. Todos los acceptance criteria tienen tests pasando
2. `ruff check .` → clean
3. `mypy app/` → 0 errors (excluyendo legacy cv.py/chat.py)
4. Commit pushed a `claude/new-session-ce0sct`
5. El documento `PRODUCT_COMPLETION_GAP_ANALYSIS.md` actualizado con nuevo estado

---

*Ver `docs/ARCHITECTURE_4.0.md` para diseño técnico de los componentes nuevos*  
*Ver `docs/PRODUCT_COMPLETION_GAP_ANALYSIS.md` para estado actual de cada capacidad*
