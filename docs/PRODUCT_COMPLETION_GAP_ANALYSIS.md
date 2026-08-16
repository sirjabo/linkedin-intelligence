# LinkedIn Intelligence — Product Completion Gap Analysis

> Versión: 4.3  
> Fecha: 2026-08-16  
> Branch: `claude/new-session-ce0sct`  
> Tests: 515 pasando (405 baseline + 19 Sprint A + 60 Sprints B–L + 31 Sprint Completion), 5 skipped  
> Metodología: lectura directa del código fuente, no documentación previa  

---

## Leyenda de estados

| Estado | Significado |
|--------|-------------|
| `PRODUCTION_READY` | Funciona end-to-end con datos reales, tiene tests robustos |
| `IMPLEMENTED` | Lógica completa pero falta validación real o gaps menores |
| `PARTIAL` | Existe pero incompleto — funciona para el happy path, falla edge cases |
| `MOCK_ONLY` | Implementación simulada, no produce resultados reales |
| `STUB` | Firma existe, sin implementación real |
| `NOT_CONNECTED` | Implementado pero no conectado al pipeline real |
| `NEEDS_REFACTOR` | Funciona pero con deuda técnica bloqueante para escalar |
| `MISSING` | No existe, debe crearse desde cero |

---

## 1. PERFIL DE CANDIDATO

### 1.1 Extracción de Perfil

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Extracción multi-fuente (CV PDF, LinkedIn text, GitHub, manual) | `IMPLEMENTED` | `profile_agent.py` | LLM extrae name, email, location, career_level, skills (con EvidenceRef), experience, education, projects, certifications | Source validation; conflict resolution entre fuentes usa LLM solo cuando >1 fuente |
| Consolidación de perfil de múltiples fuentes | `IMPLEMENTED` | `profile_agent.py` → `ConsolidatedProfile` | Merge de fuentes, flags de conflicto | Deduplicación de habilidades por sinónimo pre-LLM |
| Extracción de habilidades con evidencia | `IMPLEMENTED` | `profile_agent.py` → `SkillExtracted` | skill_name, proficiency_level, years_experience, evidence (list[EvidenceRef]) | `years_experience` es LLM-estimated, no computado desde fechas reales |
| Parsing de PDF de CV | `PRODUCTION_READY` | `pdf_extractor.py` | pdfminer.six extrae texto limpio | |
| Análisis de LinkedIn URL | `PARTIAL` | `linkedin_analyzer.py` | Genera análisis LLM del texto pasado | No scraping directo; depende de que el usuario pegue el texto del perfil |
| Health Score de perfil | `IMPLEMENTED` | `profile_optimizer.py` | 0-100 score con desglose por sección | Sin actualización automática al cambiar perfil |

### 1.2 CandidateKnowledgeResolver

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Resolución de campos básicos (nombre, email, teléfono) | `IMPLEMENTED` | `candidate_knowledge_resolver.py` | DIRECT desde candidate model | |
| Resolución de ubicación | `IMPLEMENTED` | idem | DIRECT | |
| Resolución de years_experience total | `IMPLEMENTED` | idem → `_compute_total_years()` | Suma duration_years de experiencias | Deduplicación de períodos solapados |
| **Resolución de years-per-skill** ("¿cuántos años de SQL?") | **`IMPLEMENTED`** ✅ Sprint B | `candidate_knowledge_resolver.py` → `DateRange`, `_deduplicate_periods()` | Deduplicación de períodos solapados; open-end (None) soportado | Integración con skill_years flow completo |
| Resolución de salary_expectation | `IMPLEMENTED` | idem | DIRECT o fallback LLM | |
| Resolución de work_authorization | `IMPLEMENTED` | idem | DIRECT desde perfil | |
| Resolución de custom_essay | `IMPLEMENTED` | idem | LLM genera respuesta contextualizada | Sin evaluación de calidad post-generación |
| Resolución de cover_letter | `NOT_CONNECTED` | idem → `communication_agent.py` | Llama a CommunicationAgent | No usa evidence_records reales en llamada |
| Resolución de cv_file | `IMPLEMENTED` | `cv_storage.py` | PDF generado y guardado; projects_personalized + experience_personalized aplicados | — |
| Cache de resolución por application | `MISSING` | — | — | Cada resolución recomputa desde cero |

---

## 2. MOTOR DE CV PERSONALIZADO

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Análisis de JD y extracción de requisitos | `IMPLEMENTED` | `cv_agent.py` | LLM extrae keywords ATS, fit score, reasoning | Sin extracción estructurada req-by-req |
| Personalización de summary y headline | `IMPLEMENTED` | `cv_agent.py` → `PersonalizedCV` | summary_adapted, headline_adapted, ats_keywords_added | |
| Personalización de experience bullets | **`IMPLEMENTED`** ✅ Sprint A | `cv_agent.py` → `BulletChange`, `ExperiencePersonalized` | bullet_index, original, adapted, reason, job_requirement, evidence_ref, confidence por bullet | — |
| Personalización de projects section | **`IMPLEMENTED`** ✅ Sprint A | `cv_agent.py` → `ProjectPersonalized`, `cv_storage.py` | description_adapted, highlights_adapted en PDF rebuild | — |
| Ordenamiento de skills por relevancia al JD | `IMPLEMENTED` | `cv_agent.py` → `skills_ordered` | Lista reordenada | Sin separación por proficiency o relevance score |
| Traceabilidad de cambios (original/personalizado/reason) | `IMPLEMENTED` ✅ Sprint A | `CVChange`: section, bullet_index, original, adapted, reason, job_requirement, evidence_refs (list), confidence | Todos los campos completos; backward-compat via `.evidence_ref` y `.rationale` | — |
| Evaluación de diferenciación entre CVs | **`IMPLEMENTED`** ✅ Sprint A | `ai_evaluation.py` → `cv_differentiation_score()` | Pairwise set-based ≥ 60% diferenciación validada en tests | Motor LLM para factuality/clichés pendiente (Sprint K) |
| CVs materialmente distintos para 3 tipos de JD | **`IMPLEMENTED`** ✅ Sprint A | `cv_agent.py` schema + test_sprint_a.py | 19 acceptance tests; diferenciación ≥ 60% para AI/Data/ML JDs | — |
| Reconstrucción PDF desde PersonalizedCV | **`IMPLEMENTED`** ✅ Sprint A | `cv_storage.py` → `_build_cv_dict()` | projects_personalized aplicado; experience_personalized ya conectado | — |
| Evaluación de ATS score post-generación | **`MISSING`** | — | — | Pipeline de scoring contra JD |

---

## 3. SISTEMA DE EVIDENCIA

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Validación de claims por keyword overlap | `IMPLEMENTED` ✅ Sprint C | `claim_validator.py` | SUPPORTED ≥3, PLAUSIBLE 1-2, UNSUPPORTED 0, CONTRADICTED cuando claim inflada | — |
| **EvidenceBuilder** (construye evidence records desde perfil) | **`IMPLEMENTED`** ✅ Sprint C | `claim_validator.py` → `EvidenceBuilder.build_from_profile()` | Genera EvidenceRecord de experience, skills, projects, education; skills como dict también soportados | — |
| Evidencia real pasada a validate_claims() | **`IMPLEMENTED`** ✅ Sprint Completion | `applications.py` → `evidence_records = EvidenceBuilder.build_from_profile(profile)` | evidence_records ahora construidos desde perfil real para CV gen y cover letter | — |
| Detección de claims infladas (CONTRADICTED) | **`IMPLEMENTED`** ✅ Sprint C | `claim_validator.py` → `_check_contradiction()` | Detecta inflación de años ("10 years" vs evidencia de 3) | Sin semántica profunda |
| Validación semántica (embedding similarity) | **`MISSING`** | — | — | Pipeline pgvector para búsqueda semántica |
| Validación temporal (¿experiencia vigente en período?) | **`MISSING`** | — | — | Parser de fechas de experiencia + check temporal |
| EvidenceRef en skills de perfil | `IMPLEMENTED` | `profile_agent.py` → `SkillExtracted.evidence` | Lista de `EvidenceRef` por skill | EvidenceBuilder no conectado en pipeline downstream |

---

## 4. MATCHING ENGINE

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Match determinístico por dimensiones | `IMPLEMENTED` | `matching/engine.py` | skill_overlap(0.40), experience(0.30), location(0.20), education(0.10) | |
| Hard constraints (seniority, salary, visa) | `IMPLEMENTED` | idem | BLOCKED cuando gap >2 niveles, salary gap >30%, visa sin sponsorship | |
| Career fit score separado | `IMPLEMENTED` | idem | Tabla de career_fit por gap seniority; retornado junto al job score | |
| Decision engine (APPLY / STRETCH / DO_NOT_APPLY / BLOCKED) | `IMPLEMENTED` | idem | 6 estados con thresholds documentados | |
| Sinónimos de skills (26 grupos) | `IMPLEMENTED` | idem | python==py, js==javascript, etc. | Solo exact match dentro del grupo; sin embedding |
| LLM Match (reasoning + strengths + gaps) | `IMPLEMENTED` | `match_agent.py` | Pure function, DET_WEIGHT=0.60 | |
| **Match req-by-req (MATCHED/PARTIAL/MISSING/BLOCKER)** | **`IMPLEMENTED`** ✅ Sprint D | `matching/engine.py` → `RequirementMatch`, `_classify_requirement_status()`, `compute_deterministic()` | Per-requirement status (MATCHED/PARTIAL/MISSING/BLOCKER) + importance (MUST/NICE_TO_HAVE) + match_score; `FitAnalysisResponse.requirement_matches` en API schema | — |
| Scoring de dominio (fintech, healthtech, etc.) | **`IMPLEMENTED`** ✅ Sprint Completion | `matching/engine.py` → `_DOMAIN_KEYWORDS` (14 dominios) + `_score_domain()` + `DeterministicResult.domain_score` | Alineación candidato-job por sector; no pesa en overall_score (informativo) | Integrar como bonus ponderado en overall_score |
| Transferable skills (ML→Data Science) | **`IMPLEMENTED`** ✅ Sprint Completion | `matching/engine.py` → `TRANSFERABLE_SKILLS` (15 skills) + `_TRANSFERABLE_REVERSE` + `_classify_requirement_status()` | Candidato con ML → requirement "data science" → PARTIAL (score=0.35); devops→SRE; mobile→ios/android | — |
| Importance weighting por requisito (MUST/NICE_TO_HAVE) | **`IMPLEMENTED`** ✅ Sprint D | `matching/engine.py` → `RequirementMatch.importance` | MUST / NICE_TO_HAVE por tipo de requisito | JD parsing de must-vs-nice todavía usa heurística simple |
| Match semántico por embedding | **`MISSING`** | — | — | pgvector cosine |

---

## 5. ESTRATEGIA DE APLICACIÓN

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| ApplicationStrategy generada por LLM | `IMPLEMENTED` ✅ Sprint E | `application_agent.py` → `ApplicationStrategy` | overall_approach, recommendation, positioning, target_narrative, keywords_for_form, answer_strategy, interview_preparation_strategy, claims_to_avoid, company_specific_angle | — |
| Cover letter personalizada | `IMPLEMENTED` | `communication_agent.py` → `CoverLetterResult` | content, key_points_addressed, evidence_refs | Sin evaluación de calidad post-generación |
| Respuestas a preguntas de formulario | `IMPLEMENTED` | `communication_agent.py` → `AnswerResult` | question, answer, evidence_refs | |
| Company-specific hooks (noticias, producto, cultura) | **`MISSING`** | — | — | |
| Evaluación de calidad de cover letter | **`MISSING`** | — | — | Detección de clichés, personalización, evidencia |
| Estrategia de interview preparation | **`IMPLEMENTED`** ✅ Sprint E | `application_agent.py` → `ApplicationStrategy.interview_preparation_strategy` | Lista de STAR stories y prep items | Sin prueba E2E con LLM real |

---

## 6. FORM INTELLIGENCE

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Clasificación de campos por nombre/placeholder/label | `IMPLEMENTED` | `form_intelligence.py` | 18 SemanticType literals + "unknown"; regex + LLM fallback | |
| Tipo `skill_years` ("¿Cuántos años de X?") | **`IMPLEMENTED`** ✅ Sprint F | `form_intelligence.py` → `classify_field()`, `extract_skill_target()` | Detecta "Years of Python experience" → skill_years + skill_target="python"; `MappedField.skill_target` | — |
| Tipo `experience_essay` ("Describe un proyecto donde...") | **`IMPLEMENTED`** ✅ Sprint F | `form_intelligence.py` | "Tell us about your backend experience" → experience_essay; distingue de custom_essay | — |
| Confidence score por clasificación de campo | **`IMPLEMENTED`** ✅ Sprint F | `form_intelligence.py` → `MappedField.confidence`, `MappedField.classification_source` | confidence=1.0 para regex, <1.0 para LLM; classification_source="regex"\|"llm" | — |
| Detección de campos requeridos vs opcionales | `IMPLEMENTED` | `form_intelligence.py` | `required` flag desde Playwright attrs | |
| Detección de opciones de dropdown | `IMPLEMENTED` | idem | `options` list desde `<select>` | |
| Clasificación LLM de campos ambiguos | `IMPLEMENTED` | idem | LLM fallback cuando regex no matchea | Sin cache por URL/formulario |
| Manejo de iframes | `PARTIAL` | `lever.py` | Salta a iframe para Lever | No genérico — hardcoded por ATS |

---

## 7. ATS ADAPTERS

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Greenhouse (EEO + section tracking) | `IMPLEMENTED` ✅ Sprint G | `ats/greenhouse.py` → `eeo_section_present`, `sections_visited` | Detecta EEO section; tracks qué secciones se visitaron | Auth walls, preguntas dinámicas complejas |
| Lever (custom questions + validation errors) | `IMPLEMENTED` ✅ Sprint G | `ats/lever.py` → `custom_question_labels`, `validation_errors` | Extrae labels de preguntas custom; captura errores de validación del servidor | Iframe genérico sin state persistido |
| Workday (section history) | `IMPLEMENTED` ✅ Sprint G | `ats/workday.py` → `section_history` | Registra historial de secciones visitadas | Auth walls, wizard forms complejos |
| Retry con backoff en fallo de red | **`IMPLEMENTED`** ✅ Sprint G | `ats/adapter.py` → `retry_with_backoff()` | Retry configurable con exponential backoff; success/retry/all-fail | — |
| SmartRecruiters | `IMPLEMENTED` ✅ (auditoría corrige gap) | `ats/smart_recruiters.py` | `before_discover()`, `normalize_field()`, `submit()` (wizard hasta 8 páginas), `extract_confirmation_id_pattern()` | Sin tests de integración E2E |
| Genérico (fallback) | `IMPLEMENTED` | `ats/generic.py` | Fill + submit básico | Para formularios simples |
| Detección automática de ATS por URL | `IMPLEMENTED` | `ats/registry.py` | Pattern matching por URL | |
| Capability matrix (qué soporta cada ATS) | **`MISSING`** | — | — | |

---

## 8. SUBMISSION STATE MACHINE

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Fase start(): inteligencia + discovery | `IMPLEMENTED` | `orchestrator.py` | Det match, LLM match, strategy, CV, cover letter en paralelo; form discovery + clasificación | evidence_records siempre vacío |
| Fase resume(): validación de campos humanos | `IMPLEMENTED` | idem | Valida que campos HUMAN_REQUIRED estén respondidos | |
| Fase submit(): fill + ATS submit + confirmación | `IMPLEMENTED` | idem | Re-abre browser, re-descubre form, llena campos, pre-submit invalid check, submit, detección de confirmación | |
| Screenshots en cada fase | `IMPLEMENTED` | idem | Saved a `application_id_phase.png` | |
| Confirmación de submission por humano | `IMPLEMENTED` | idem | `human_confirmed=True` requerido en submit() | Siempre respetado — no auto-submit |
| **Estado PAUSED + resume_from_field()** | **`IMPLEMENTED`** ✅ Sprint I + (auditoría corrige gap) | `application_agent_orchestrator.py` → `pause()`, `resume_from_field()`, `resume()` | Estados pausables definidos; `pause()` setea status + resume_from en pause_meta; `resume_from_field()` reanuda desde campo específico | — |
| Evidencia de submission (screenshots + confirmation_id) | `PARTIAL` | idem | Screenshots guardados, `extract_confirmation_id()` implementado | `ApplicationSubmission` persiste datos pero frontend no lo muestra |
| Reintentos ante fallo de browser | **`MISSING`** | — | — | |

---

## 9. FILE UPLOAD ENGINE

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Upload de CV por file input en formularios | `PARTIAL` | `orchestrator.py` → `_get_file_path()` | Busca CV en `application_id.pdf` o último PDF en directorio | |
| **Validación de formato de archivo** | **`IMPLEMENTED`** ✅ Sprint H | `orchestrator.py` → `_validate_cv_file()` | Valida PDF real (magic bytes), no-PDF, empty, missing, too-large (>10MB) | — |
| Upload de carta de presentación como archivo | `MISSING` | — | Solo texto plano | |
| Detección de tipo de campo (file_upload) | `IMPLEMENTED` | `form_intelligence.py` | SemanticType "file_upload" reconocido | |

---

## 10. EVALUACIÓN CON IA

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Evaluación estructural de campos | `IMPLEMENTED` | `ai_evaluation.py` | field_not_empty, field_in_range, field_contains_keyword, field_one_of, list_items_have_field | |
| **Evaluación semántica LLM (criterio)** | **`IMPLEMENTED`** ✅ Sprint K | `ai_evaluation.py` → `LLMEvaluationCriterion`, `evaluate_async()` | Criterio con LLM judge; graceful error cuando API falla | Tests mockean LLM; sin E2E con API real |
| **Criterios pre-built** | **`IMPLEMENTED`** ✅ Sprint K | `ai_evaluation.py` → cover_letter_cliche_criterion, cover_letter_company_hook_criterion | Detección de clichés ("I am passionate") y company hooks | — |
| Evaluación de factualidad de CV | `PARTIAL` | `ai_evaluation.py` → `cv_changes_have_evidence()` ✅ Sprint A | Verifica que cada CVChange tenga evidence_refs | Cross-check claim vs evidencia del perfil pendiente |
| Evaluación de diferenciación entre CVs | **`IMPLEMENTED`** ✅ Sprint A | `ai_evaluation.py` → `cv_differentiation_score()` | Pairwise set-based; ≥ 60% para 3 JDs distintos | — |
| Test suite con modelo real | **`MISSING`** | — | Tests actuales mockean LLM | Evaluación E2E con Anthropic API real |
| Métricas de calidad agregadas por candidato | **`MISSING`** | — | — | |

---

## 11. RECOMENDACIONES Y LEARNING

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Scoring TF-IDF de empleos | `IMPLEMENTED` | `job_recommender.py` | cosine similarity, IDF boost para skills raras | 405 tests pasando |
| Ranking de empleos por score | `IMPLEMENTED` | idem → `rank_jobs()` | Orden descendente por score | |
| Learning loop estadístico | `IMPLEMENTED` | `learning_loop.py` | calibration_score = actual / weighted_expected; bias_direction | MIN_OUTCOMES=5 |
| Registro de outcomes | `IMPLEMENTED` | `applications.py` | Endpoint PATCH /applications/{id}/outcome | |
| **Feedback loop → actualización de thresholds** | **`IMPLEMENTED`** ✅ Sprint L + Completion | `learning_loop.py` + `applications.py` → `record_outcome` | Auto-trigger: cada `POST /outcome` recalcula calibration y persiste thresholds actualizados en `candidate.preferences["match_thresholds"]` | — |
| **A/B testing de estrategias** | **`IMPLEMENTED`** ✅ Sprint L | `learning_loop.py` → `ABExperiment`, `ABVariant`, `DET_WEIGHT_EXPERIMENT`, `APPLY_THRESHOLD_EXPERIMENT` | Asignación determinista de variantes; config de det_weight y apply_threshold | — |
| **Hypothesis testing estadístico** | **`IMPLEMENTED`** ✅ Sprint Completion | `learning_loop.py` → `_norm_sf()` + z-test en `compute_calibration()` | `CalibrationReport.p_value` (two-tailed) + `CalibrationReport.significant` (True cuando p<0.05) | — |
| Recomendaciones de perfil basadas en outcomes | **`MISSING`** | — | — | |

---

## 12. FRONTEND — APPLICATION CONTROL CENTER

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| UI de workflow de aplicación (8 estados) | `IMPLEMENTED` | `applications/[id]/page.tsx` | initializing → submitted/failed; polling 3s | |
| Campos HUMAN_REQUIRED con dropdown/texto | `IMPLEMENTED` | idem | Select cuando hay options; text input con auto_fill | |
| Readiness checklist | `IMPLEMENTED` | idem | CV / cover letter / strategy / applied | |
| **Descarga de CV generado** | **`IMPLEMENTED`** ✅ Sprint J | `applications.py` → `GET /{app_id}/cv/download` + frontend download button | FileResponse PDF; regenera si no existe en disco | — |
| **Vista diff de cambios de CV** | **`IMPLEMENTED`** ✅ Sprint J | `applications/[id]/page.tsx` → cvDiffOpen panel | Muestra original vs adapted por bullet con reason | — |
| **Vista de estrategia completa** | **`IMPLEMENTED`** ✅ Sprint J | idem → strategyOpen panel | positioning, target_narrative, keywords, interview_prep, claims_to_avoid, company_specific_angle, strengths, risks | — |
| **Evidencia de submission** | **`IMPLEMENTED`** ✅ Sprint J | idem → submission evidence panel | confirmation_id, final_url, fields_confirmed, ats_name | Screenshots no persistidos en DB |
| **Vista req-by-req del match** | **`IMPLEMENTED`** ✅ Sprint J | idem → requirement_matches panel + `GET /{app_id}/fit-analysis` | MATCHED/PARTIAL/MISSING/BLOCKER con importancia y score | — |

---

## 13. INFRAESTRUCTURA Y SEGURIDAD

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Auth JWT (registro, login, refresh) | `PRODUCTION_READY` | `auth.py` | HMAC-SHA256, PBKDF2 | |
| Rate limiting en auth | **`IMPLEMENTED`** ✅ (auditoría corrige gap) | `auth.py` → `@limiter.limit(_LOGIN_LIMIT="5/min")`, `@limiter.limit(_REGISTER_LIMIT="3/min")` | slowapi con límites por ambiente (200/min dev, 5/min prod) | — |
| SSRF protection | `IMPLEMENTED` | `ssrf.py` | Bloquea IPs privadas | |
| Celery + Redis para tareas async | `IMPLEMENTED` | `worker/` | Email, market data tasks | |
| Health check endpoint | `IMPLEMENTED` | `main.py` | `/health` | |
| GDPR / account deletion | **`IMPLEMENTED`** ✅ (auditoría corrige gap) | `candidates.py` → `DELETE /candidates/me` | Elimina candidate con cascade (profile, sources, jobs, applications) | — |
| Logs estructurados (structlog) | `IMPLEMENTED` | `logging.py` | JSON con structlog | |

---

## Resumen ejecutivo — Prioridades por impacto

### Sprint A ✅ CERRADO (2026-08-16)

- CVChange schema completo: bullet_index, reason, job_requirement, evidence_refs, confidence
- PersonalizedCV con experience_personalized + projects_personalized
- PDF rebuild usa projects_personalized descriptions
- cv_differentiation_score() ≥ 60% para 3 JDs distintos
- cv_changes_have_evidence criterion
- 19/19 acceptance tests pasando

### Sprints B–L ✅ CERRADOS (2026-08-16) — 60/60 tests pasando

| Sprint | Qué se implementó |
|--------|------------------|
| B | `DateRange` + `_deduplicate_periods()` para skill_years sin doble-conteo |
| C | `EvidenceBuilder.build_from_profile()` + `_check_contradiction()` + estado CONTRADICTED |
| D | `RequirementMatch`, `_classify_requirement_status()`, `requirement_matches` en `compute_deterministic()` y API schema |
| E | `ApplicationStrategy` +7 campos: positioning, target_narrative, keywords_for_form, answer_strategy, interview_preparation_strategy, claims_to_avoid, company_specific_angle |
| F | `classify_field()` → skill_years + experience_essay; `extract_skill_target()`; `MappedField.confidence` + `classification_source` |
| G | `GreenhouseAdapter.eeo_section_present/sections_visited`, `LeverAdapter.custom_question_labels/validation_errors`, `WorkdayAdapter.section_history`, `retry_with_backoff()` |
| H | `_validate_cv_file()`: valida PDF real (magic bytes), tamaño, existencia |
| I | `AgentError`, constantes de estados pausables documentadas en module docstring |
| K | `LLMEvaluationCriterion`, `evaluate_async()`, cover_letter_cliche/company_hook criteria |
| L | `_update_thresholds()`, `ABExperiment`/`ABVariant`, `DET_WEIGHT_EXPERIMENT`, `APPLY_THRESHOLD_EXPERIMENT` |

**Sprint J (Frontend Control Center)** — implementado en frontend (`applications/[id]/page.tsx`) + backend endpoint `GET /{app_id}/cv/download`; todas las 6 UIs del AC presentes.

### Sprint Completion ✅ CERRADO (2026-08-16) — 31 tests nuevos, 515 total

| Qué se implementó | Archivo |
|-------------------|---------|
| `EvidenceBuilder.build_from_profile()` conectado en CV gen y cover letter routes | `applications.py` |
| Auto-trigger de `_update_thresholds()` en cada `POST /outcome` | `applications.py` + `learning_loop.py` |
| `TRANSFERABLE_SKILLS` (15 skills) + `_TRANSFERABLE_REVERSE` → PARTIAL en `_classify_requirement_status()` | `matching/engine.py` |
| `_DOMAIN_KEYWORDS` (14 dominios) + `_score_domain()` → `DeterministicResult.domain_score` | `matching/engine.py` |
| `_norm_sf()` + z-test → `CalibrationReport.p_value` + `CalibrationReport.significant` | `learning_loop.py` |
| Correcciones en gap analysis: auth rate limiting, GDPR deletion, SmartRecruiters, resume_from_field() todos ya estaban IMPLEMENTED | gap analysis |

### P0 — Gaps restantes bloqueantes

(ninguno — todos los P0 anteriores están cerrados)

### P1 — Gaps que degradan calidad

1. **Evaluación E2E con LLM real**: tests actuales mockean Anthropic API

### P2 — Mejoras de calidad y escalabilidad

2. **Matching semántico** (pgvector cosine)
3. **Cache de resolución por application** — cada resolución recomputa desde cero
4. **Cover letter quality evaluation** — criterios LLM implementados pero no auto-llamados post-generación
5. **Scoring de dominio** incorporado en `overall_score` (actualmente informativo solamente)
6. **Reintentos ante fallo de browser** en orchestrator

---

*Generado por auditoría directa del código fuente — 2026-08-15*  
*Actualizado Sprint A — 2026-08-16*  
*Actualizado Sprints B–L — 2026-08-16 (453 tests pasando)*  
*Actualizado Sprint Completion — 2026-08-16 (515 tests pasando)*  
*Ver `docs/ROADMAP_4.0.md` para el plan de sprints A–L*
