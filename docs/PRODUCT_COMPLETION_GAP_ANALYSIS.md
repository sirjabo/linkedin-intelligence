# LinkedIn Intelligence — Product Completion Gap Analysis

> Versión: 4.0  
> Fecha: 2026-08-15  
> Branch: `claude/new-session-ce0sct`  
> Tests: 405 pasando, 5 skipped  
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
| **Resolución de years-per-skill** ("¿cuántos años de SQL?") | **`MISSING`** | — | — | Motor de skill_years con extracción temporal de experiencias |
| Resolución de salary_expectation | `IMPLEMENTED` | idem | DIRECT o fallback LLM | |
| Resolución de work_authorization | `IMPLEMENTED` | idem | DIRECT desde perfil | |
| Resolución de custom_essay | `IMPLEMENTED` | idem | LLM genera respuesta contextualizada | Sin evaluación de calidad post-generación |
| Resolución de cover_letter | `NOT_CONNECTED` | idem → `communication_agent.py` | Llama a CommunicationAgent | No usa evidence_records reales en llamada |
| Resolución de cv_file | `IMPLEMENTED` | `cv_storage.py` | PDF generado y guardado | Usa solo summary_adapted y skills_ordered; no reconstruye experiencias personalizadas |
| Cache de resolución por application | `MISSING` | — | — | Cada resolución recomputa desde cero |

---

## 2. MOTOR DE CV PERSONALIZADO

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Análisis de JD y extracción de requisitos | `IMPLEMENTED` | `cv_agent.py` | LLM extrae keywords ATS, fit score, reasoning | Sin extracción estructurada req-by-req |
| Personalización de summary y headline | `IMPLEMENTED` | `cv_agent.py` → `PersonalizedCV` | summary_adapted, headline_adapted, ats_keywords_added | |
| Personalización de experience bullets | **`MISSING`** | — | cv_agent produce `CVChange` por sección pero sin bullet-level edits | Rework bullet-by-bullet con evidence_ref |
| Personalización de projects section | **`MISSING`** | — | idem | |
| Ordenamiento de skills por relevancia al JD | `IMPLEMENTED` | `cv_agent.py` → `skills_ordered` | Lista reordenada | Sin separación por proficiency o relevance score |
| Traceabilidad de cambios (original/personalizado/reason) | `IMPLEMENTED` | `CVChange`: section, original, adapted, rationale, evidence_ref | | evidence_ref no siempre completado |
| Evaluación de personalización (factuality / differentiation) | **`MISSING`** | — | `ai_evaluation.py` hace checks estructurales únicamente | Motor LLM para evaluar factuality, clichés, fortaleza de evidencia |
| CVs materialmente distintos para 3 tipos de JD | **`MISSING`** | — | cv_agent genera un único CV adaptado | Lógica de differentiation per JD type |
| Reconstrucción PDF desde PersonalizedCV | `PARTIAL` | `cv_storage.py` + `pdf_generator.py` | Usa summary_adapted + skills_ordered; sections restantes vienen del perfil crudo | Integración bullet-level para experience/projects |
| Evaluación de ATS score post-generación | **`MISSING`** | — | — | Pipeline de scoring contra JD |

---

## 3. SISTEMA DE EVIDENCIA

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Validación de claims por keyword overlap | `PARTIAL` | `claim_validator.py` | SUPPORTED ≥3, PLAUSIBLE 1-2, UNSUPPORTED 0 | Solo keyword, sin semántica |
| Evidencia real pasada a validate_claims() | **`MISSING`** | `orchestrator.py` → `validate_claims(cv_text, evidence_records=[])` | **evidence_records siempre vacío** — anotado como "Phase 2 gap" en el código | Conectar con EvidenceRef de profile/experience |
| Validación semántica (embedding similarity) | **`MISSING`** | — | — | Pipeline pgvector para búsqueda semántica |
| Validación temporal (¿experiencia vigente en período?) | **`MISSING`** | — | — | Parser de fechas de experiencia + check temporal |
| Detección de contradicciones entre fuentes | **`MISSING`** | — | — | Cross-source comparison |
| Estado CONTRADICTED | **`MISSING`** | — | Solo SUPPORTED/PLAUSIBLE/UNSUPPORTED | |
| EvidenceRef en skills de perfil | `IMPLEMENTED` | `profile_agent.py` → `SkillExtracted.evidence` | Lista de `EvidenceRef` por skill | Sin conexión a validation pipeline downstream |

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
| **Match req-by-req (MATCHED/PARTIAL/MISSING/BLOCKER)** | **`MISSING`** | — | Engine produce score agregado, no breakdown por requisito | Motor de requisitos estructurados |
| Scoring de dominio (fintech, healthtech, etc.) | **`MISSING`** | — | — | |
| Transferable skills (ML→Data Science) | **`MISSING`** | — | — | Grafo de transferabilidad |
| Importance weighting por requisito (MUST/NICE_TO_HAVE) | **`MISSING`** | — | JD no parsea must-vs-nice explícitamente | |
| Match semántico por embedding | **`MISSING`** | — | — | pgvector cosine |

---

## 5. ESTRATEGIA DE APLICACIÓN

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| ApplicationStrategy generada por LLM | `PARTIAL` | `application_agent.py` → `ApplicationStrategy` | overall_approach, cv_changes, cover_letter_key_points, strengths_to_emphasize, risks_to_address, recommendation | Falta: positioning, target_narrative, keywords_for_form, answer_strategy, interview_prep, claims_to_avoid, company_specific_angle |
| Cover letter personalizada | `IMPLEMENTED` | `communication_agent.py` → `CoverLetterResult` | content, key_points_addressed, evidence_refs | Sin evaluación de calidad post-generación |
| Respuestas a preguntas de formulario | `IMPLEMENTED` | `communication_agent.py` → `AnswerResult` | question, answer, evidence_refs | |
| Company-specific hooks (noticias, producto, cultura) | **`MISSING`** | — | — | |
| Evaluación de calidad de cover letter | **`MISSING`** | — | — | Detección de clichés, personalización, evidencia |
| Estrategia de interview preparation | **`MISSING`** | — | — | |

---

## 6. FORM INTELLIGENCE

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Clasificación de campos por nombre/placeholder/label | `IMPLEMENTED` | `form_intelligence.py` | 18 SemanticType literals + "unknown"; regex + LLM fallback | |
| Tipo `skill_years` ("¿Cuántos años de X?") | **`MISSING`** | — | — | Detection de skill-experience questions |
| Tipo `experience_essay` ("Describe un proyecto donde...") | **`MISSING`** | — | — | |
| Confidence score por clasificación de campo | **`MISSING`** | — | MappedField sin metadata de confianza | |
| Detección de campos requeridos vs opcionales | `IMPLEMENTED` | `form_intelligence.py` | `required` flag desde Playwright attrs | |
| Detección de opciones de dropdown | `IMPLEMENTED` | idem | `options` list desde `<select>` | |
| Clasificación LLM de campos ambiguos | `IMPLEMENTED` | idem | LLM fallback cuando regex no matchea | Sin cache por URL/formulario |
| Manejo de iframes | `PARTIAL` | `lever.py` | Salta a iframe para Lever | No genérico — hardcoded por ATS |

---

## 7. ATS ADAPTERS

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Greenhouse básico (single-step) | `PARTIAL` | `ats/greenhouse.py` | GDPR banner click, submit loop Next→Submit (max 10 páginas) | EEO fields, preguntas dinámicas, tracking de página actual |
| Greenhouse multi-step tracking | `PARTIAL` | idem | Loop sencillo sin state | Sin detección de qué sección está |
| Lever (iframe) | `PARTIAL` | `ats/lever.py` | Navega a /apply, salta a iframe | Sin extracción de preguntas custom, sin feedback de validación |
| Workday | `PARTIAL` | `ats/workday.py` | Click "Apply Now", navegación multi-step | Auth walls, wizard forms complejos, dynamic section loading |
| SmartRecruiters | `STUB` | `ats/smart_recruiters.py` | Clase existe | Sin implementación real |
| Genérico (fallback) | `IMPLEMENTED` | `ats/generic.py` | Fill + submit básico | Para formularios simples |
| Capability matrix (qué soporta cada ATS) | **`MISSING`** | — | — | |
| Detección automática de ATS por URL | `IMPLEMENTED` | `ats/registry.py` | Pattern matching por URL | |
| Manejo de errores de validación del servidor | **`MISSING`** | — | — | |
| Retry con backoff en timeout de red | **`MISSING`** | — | — | |

---

## 8. SUBMISSION STATE MACHINE

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Fase start(): inteligencia + discovery | `IMPLEMENTED` | `orchestrator.py` | Det match, LLM match, strategy, CV, cover letter en paralelo; form discovery + clasificación | evidence_records siempre vacío |
| Fase resume(): validación de campos humanos | `IMPLEMENTED` | idem | Valida que campos HUMAN_REQUIRED estén respondidos | |
| Fase submit(): fill + ATS submit + confirmación | `IMPLEMENTED` | idem | Re-abre browser, re-descubre form, llena campos, pre-submit invalid check, submit, detección de confirmación | |
| Screenshots en cada fase | `IMPLEMENTED` | idem | Saved a `application_id_phase.png` | |
| Confirmación de submission por humano | `IMPLEMENTED` | idem | `human_confirmed=True` requerido en submit() | Siempre respetado — no auto-submit |
| **Estado PAUSED + resume desde campo arbitrario** | **`MISSING`** | — | — | State machine no soporta pausa mid-fill |
| Evidencia de submission (screenshots + confirmation_id) | `PARTIAL` | idem | Screenshots guardados, `extract_confirmation_id()` implementado | `ApplicationSubmission` persiste datos pero frontend no lo muestra |
| Reintentos ante fallo de browser | **`MISSING`** | — | — | |

---

## 9. FILE UPLOAD ENGINE

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Upload de CV por file input en formularios | `PARTIAL` | `orchestrator.py` → `_get_file_path()` | Busca CV en `application_id.pdf` o último PDF en directorio | Validación de que el archivo exista antes de intentar upload |
| Validación de formato de archivo | `MISSING` | — | — | |
| Upload de carta de presentación como archivo | `MISSING` | — | Solo texto plano | |
| Detección de tipo de campo (file_upload) | `IMPLEMENTED` | `form_intelligence.py` | SemanticType "file_upload" reconocido | |

---

## 10. EVALUACIÓN CON IA

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Evaluación estructural de campos | `IMPLEMENTED` | `ai_evaluation.py` | field_not_empty, field_in_range, field_contains_keyword, field_one_of, list_items_have_field | |
| Evaluación semántica LLM | **`MISSING`** | — | — | LLM judge por criterio |
| Evaluación de factualidad de CV | **`MISSING`** | — | — | Cross-check claim vs evidencia |
| Evaluación de diferenciación entre CVs | **`MISSING`** | — | — | Distancia entre narrativas |
| Evaluación de personalización de cover letter | **`MISSING`** | — | — | Detección de clichés, hooks específicos |
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
| Feedback loop → actualización de thresholds | **`MISSING`** | — | Calibration report generado pero no actúa sobre nada | Sin actualización de pesos o thresholds |
| A/B testing de estrategias | **`MISSING`** | — | — | Framework de experimentos |
| Hypothesis testing estadístico | **`MISSING`** | — | Solo descriptive stats | p-values, confidence intervals |
| Recomendaciones de perfil basadas en outcomes | **`MISSING`** | — | — | |

---

## 12. FRONTEND — APPLICATION CONTROL CENTER

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| UI de workflow de aplicación (8 estados) | `IMPLEMENTED` | `applications/[id]/page.tsx` | initializing → submitted/failed; polling 3s | |
| Campos HUMAN_REQUIRED con dropdown/texto | `IMPLEMENTED` | idem | Select cuando hay options; text input con auto_fill | |
| Readiness checklist | `IMPLEMENTED` | idem | CV / cover letter / strategy / applied | |
| **Descarga de CV generado** | **`MISSING`** | — | — | Link a PDF endpoint |
| **Vista diff de cambios de CV** | **`MISSING`** | — | — | Original vs personalizado por sección |
| **Vista de estrategia completa** | **`MISSING`** | — | — | Expandir ApplicationStrategy |
| **Evidencia de submission** | **`MISSING`** | — | Frontend no muestra confirmation_id ni screenshots | |
| **Vista req-by-req del match** | **`MISSING`** | — | — | Depende de Matching 3.0 |

---

## 13. INFRAESTRUCTURA Y SEGURIDAD

| Capacidad | Estado | Archivos | Funciona | Falta |
|-----------|--------|----------|----------|-------|
| Auth JWT (registro, login, refresh) | `PRODUCTION_READY` | `auth.py` | HMAC-SHA256, PBKDF2 | |
| Rate limiting en auth | **`MISSING`** | — | Brute force sin protección | slowapi en otros endpoints; no en auth |
| SSRF protection | `IMPLEMENTED` | `ssrf.py` | Bloquea IPs privadas | |
| Celery + Redis para tareas async | `IMPLEMENTED` | `worker/` | Email, market data tasks | |
| Health check endpoint | `IMPLEMENTED` | `main.py` | `/health` | |
| GDPR / account deletion | **`MISSING`** | — | — | |
| Logs estructurados (structlog) | `IMPLEMENTED` | `logging.py` | JSON con structlog | |

---

## Resumen ejecutivo — Prioridades por impacto

### P0 — Bloqueantes para el North Star (entrevistas calificadas)

1. **Evidence System 3.0**: `validate_claims()` siempre recibe `evidence_records=[]` — todas las claims son UNSUPPORTED
2. **CV Engine**: experience/project bullets no se personalizan — el CV "personalizado" tiene solo summary + skill order distintos
3. **Matching req-by-req**: sin breakdown por requisito no hay diferenciación real de qué candidate encaja qué job
4. **Skill years resolver**: formularios que preguntan "¿años de X?" no se pueden responder con precisión

### P1 — Gaps que degradan calidad significativamente

5. **Form Intelligence**: tipos `skill_years` y `experience_essay` ausentes
6. **ApplicationStrategy incompleta**: positioning, target_narrative, keywords, interview_prep no generados
7. **ATS adapters**: Greenhouse/Lever/Workday funcionan solo en happy path
8. **CV differentiation**: mismo CV para todos los tipos de JD

### P2 — Mejoras de calidad y escalabilidad

9. **Evaluación semántica LLM** para CV, cover letter, factualidad
10. **Frontend**: CV download, diff view, submission evidence
11. **Learning loop activo**: calibration report no retroalimenta el sistema
12. **Rate limiting en auth**

---

*Generado por auditoría directa del código fuente — 2026-08-15*  
*Ver `docs/ROADMAP_4.0.md` para el plan de sprints A–L*
