# PRODUCTION READINESS AUDIT
**Fecha**: 2026-08-17  
**Branch**: `claude/new-session-ce0sct`  
**Tests**: 594 passing, 0 failing, 5 skipped  
**Auditor**: Code audit (no real-world execution yet)

---

## Escala de evaluación

| Estado | Significado |
|--------|-------------|
| `READY` | Implementado, testeado, sin gaps conocidos |
| `PARTIAL` | Implementado pero con gaps documentados |
| `NOT_READY` | No existe o es stub |
| `BLOCKED` | Requiere decisión externa o dependencia no resuelta |

---

## 1. Candidate Profile

**Estado**: `READY`

- **Evidencia**: `candidates.py` route, `CandidateProfile` ORM, extracción desde LinkedIn/PDF/GitHub
- **Archivos**: `app/api/routes/candidates.py`, `app/db/models/candidate.py`, `app/services/agents/profile_agent.py`
- **Tests existentes**: `test_candidates.py`, `test_profile_agent.py` — PASS
- **Tests faltantes**: Test E2E con CV real (PDF) → extracción → DB
- **Riesgos**: Calidad de extracción depende del LLM; sin eval real hecha
- **Fix requerido**: Ninguno estructural. Ejecutar real-model eval con API key.
- **Acceptance criteria**: Extracción produce `name`, `email`, `skills`, `experience` con confianza ≥ 0.8 en 3 CVs reales

---

## 2. CV Personalization

**Estado**: `PARTIAL`

- **Evidencia**: `cv_agent.py`, `PersonalizedCV`, `CVChange` con `reason`/`evidence_refs`; `CVVersion` en DB
- **Archivos**: `app/services/agents/cv_agent.py`, `app/db/models/application.py`
- **Tests existentes**: `test_cv_agent.py` — PASS (LLM mockeado)
- **Tests faltantes**: CV differentiation test (1 candidato × 3 JDs → 3 outputs distintos); real-model eval
- **Riesgos**: Personalización superficial sin eval real; `evidence_refs` puede quedar vacío si LLM no retorna refs
- **Fix requerido**: Implementar CV differentiation test (Sprint PR-2)
- **Acceptance criteria**: Summary differentiation detectable en los 3 outputs; sin claims inventados

---

## 3. Evidence Validation

**Estado**: `PARTIAL`

- **Evidencia**: `claim_validator.py` con `_semantic_similarity()` (TF-cosine) + `_temporal_consistency()`; `SemanticMatcher` con embeddings reales en `matching/semantic.py`
- **Archivos**: `app/services/claim_validator.py`, `app/services/matching/semantic.py`
- **Tests existentes**: `test_claim_validator.py` — PASS
- **Tests faltantes**: Eval real de precision/recall de SUPPORTED vs CONTRADICTED
- **Riesgos**: **Dos conceptos distintos llamados "semantic"** — TF-cosine en claim_validator y embeddings reales en SemanticMatcher. Confusión conceptual. Scores no están unificados en un output estructurado.
- **Fix requerido** (BLOCKER PR-2): Unificar bajo `lexical_score` / `semantic_score` / `temporal_consistent` / `contradicted` / `final_status`. Eliminar ambigüedad.
- **Acceptance criteria**: Output estructurado único; `unsupported_claim_rate ≤ 2%` en eval real

---

## 4. Requirement Matching

**Estado**: `PARTIAL`

- **Evidencia**: `engine.py` con `match_requirements()`, `RequirementMatch` con `evidence_refs: list[str]`, `_parse_requirements()` LLM
- **Archivos**: `app/services/matching/engine.py`, `app/schemas/match.py`
- **Tests existentes**: `test_sprints_b_through_l.py` — PASS
- **Tests faltantes**: Dataset de calibración con expected labels; medición de BLOCKER false-positive rate
- **Riesgos**: Un false BLOCKER bloquea una candidatura válida — crítico. Sin calibración sobre datos reales.
- **Fix requerido** (BLOCKER PR-2): Crear dataset de calibración; medir `BLOCKER FP rate`; target `< 2%`
- **Acceptance criteria**: Precision MATCHED ≥ 0.90; BLOCKER FP rate < 2% sobre dataset

---

## 5. Job Fit

**Estado**: `READY`

- **Evidencia**: `match_agent.py` con `LLMMatchResult` (score, reasoning, strengths, gaps, recommendation)
- **Archivos**: `app/services/agents/match_agent.py`, `app/api/routes/match.py`
- **Tests existentes**: `test_match_agent.py` — PASS
- **Tests faltantes**: Real-model eval en 5+ JDs
- **Riesgos**: Score calibración no validada en producción
- **Fix requerido**: Ejecutar real-model eval con API key
- **Acceptance criteria**: Score correlaciona con criterio humano en ≥ 4/5 casos de prueba

---

## 6. Career Fit

**Estado**: `PARTIAL`

- **Evidencia**: `profile_agent.py` contiene `career_level` y `extraction_confidence`; no hay un "Career Fit score" explícito separado del Job Fit
- **Archivos**: `app/services/agents/profile_agent.py`
- **Tests existentes**: Indirectamente testeado en `test_profile_agent.py`
- **Tests faltantes**: Test explícito Career Fit separado de Job Fit
- **Riesgos**: Career Fit y Job Fit pueden confundirse en el flujo
- **Fix requerido**: Clarificar si Career Fit es un score propio o está subsumido en Job Fit
- **Acceptance criteria**: Documentación clara del distinción en API spec

---

## 7. Application Strategy

**Estado**: `READY`

- **Evidencia**: `application_agent.py` con `ApplicationStrategy`, `CVChangeGuidance`
- **Archivos**: `app/services/agents/application_agent.py`
- **Tests existentes**: `test_application_agent.py` — PASS (mockeado)
- **Tests faltantes**: Real-model eval; validación de que strategy cambia entre JDs distintos
- **Riesgos**: Sin eval real
- **Fix requerido**: Ejecutar con API key en PR-2
- **Acceptance criteria**: Strategy difiere entre JD Senior vs Junior para mismo candidato

---

## 8. Cover Letter

**Estado**: `READY`

- **Evidencia**: `communication_agent.py` con `CoverLetterResult`; `CoverLetter` en DB
- **Archivos**: `app/services/agents/communication_agent.py`
- **Tests existentes**: `test_ai_evaluation_suite.py` — cliché avoidance, company hook (skipped sin API key)
- **Tests faltantes**: Real-model eval ejecutado
- **Riesgos**: Clichés y carta genérica si el LLM falla en personalización
- **Fix requerido**: Ejecutar AI eval suite con API key real
- **Acceptance criteria**: `cliche_avoidance ≥ 0.90`; `company_hook present = 100%`

---

## 9. Application Answers

**Estado**: `PARTIAL`

- **Evidencia**: `communication_agent.py` con `AnswerResult`; `answers.py` route; `application_answers` en DB
- **Archivos**: `app/services/agents/communication_agent.py`, `app/api/routes/answers.py`
- **Tests existentes**: `test_answers.py` — PASS
- **Tests faltantes**: Test específico para salary/sponsorship/demographic → HUMAN_REQUIRED
- **Riesgos**: **Campos sensibles** (salary, work auth, sponsorship, relocation, demographic) podrían recibir auto-respuesta inapropiada
- **Fix requerido** (BLOCKER PR-4): Auditar `_ALWAYS_HUMAN` en `form_intelligence.py` para cubrir todos los campos sensibles; agregar test explícito
- **Acceptance criteria**: 100% de campos sensibles → `HUMAN_REQUIRED`; 0 auto-inferences en salary/auth/demographic

---

## 10. Form Intelligence

**Estado**: `PARTIAL`

- **Evidencia**: `form_intelligence.py` con 25+ SemanticTypes; `_ALWAYS_HUMAN` definido; regla `cover_letter_file` agregada
- **Archivos**: `app/services/form_intelligence.py`
- **Tests existentes**: `test_form_intelligence.py` — PASS
- **Tests faltantes**: Validación contra forms reales de Greenhouse/Lever/Workday; test de campos sin label (aria-only, placeholder-only)
- **Riesgos**: Campos sin label tradicional (aria-label only, placeholder-only) pueden no clasificarse
- **Fix requerido**: Expandir clasificación a aria-label y placeholder como fallback primario; tests con fixtures de forms reales
- **Acceptance criteria**: Classification accuracy ≥ 95% sobre 50 campos reales diversos

---

## 11. Candidate Knowledge Resolution

**Estado**: `READY`

- **Evidencia**: `candidate_knowledge_resolver.py` completo; resuelve campos por SemanticType desde CandidateProfile
- **Archivos**: `app/services/candidate_knowledge_resolver.py`
- **Tests existentes**: `test_candidate_knowledge_resolver.py` — PASS
- **Tests faltantes**: Test de campo desconocido → `HUMAN_REQUIRED`; test campo sensible → `HUMAN_REQUIRED`
- **Riesgos**: Gap: campo no mapeado puede devolver valor vacío en lugar de HUMAN_REQUIRED
- **Fix requerido**: Verificar que campos sin mapping retornan `resolution_type=HUMAN_REQUIRED` explícito
- **Acceptance criteria**: Unknown fields → HUMAN_REQUIRED en 100% de casos

---

## 12. File Uploads

**Estado**: `PARTIAL`

- **Evidencia**: `playwright_adapter.py` tiene `upload_file(css_selector, file_path)`; `cv_storage.py` genera PDF; `cover_letter_file` SemanticType existe
- **Archivos**: `app/services/browser/playwright_adapter.py`, `app/services/cv_storage.py`
- **Tests existentes**: `test_server.py` mock ATS incluye `input[type=file]` — básico
- **Tests faltantes**: Test de upload real de PDF a mock ATS; test de file upload fallido; test de tipo de archivo rechazado
- **Riesgos**: Upload depende de `input[type=file]` bien detectado por el form extractor; no testeado con archivo real
- **Fix requerido** (BLOCKER PR-4): Test E2E de upload de CV PDF contra mock ATS; validación de que el archivo llega
- **Acceptance criteria**: CV upload success ≥ 98% en mock ATS; cover letter upload funciona

---

## 13. ATS Adapters

**Estado**: `PARTIAL`

- **Evidencia**: Adapters para Greenhouse, Lever, Workday, Ashby, SmartRecruiters, Generic — código completo con `url_patterns`, `before_discover()`, `normalize_field()`, `submit()`
- **Archivos**: `app/services/ats/`
- **Tests existentes**: `test_p3_ats_adapters.py`, `test_ats_capabilities.py` — PASS (todos con mocks)
- **Tests faltantes**: Validación contra URLs reales; fixture de forms reales por ATS
- **Riesgos**: **Cero validación contra ATS reales**. Todo testeado con mocks. Workday en particular es HIGH RISK (multi-step, dynamic DOM, session state).
- **Fix requerido** (BLOCKER PR-3): Ejecutar validation program contra 50+ job flows reales
- **Acceptance criteria**: Ver ATS Capability Matrix; Workday marcado PARTIAL hasta tener evidencia real

---

## 14. Browser Reliability

**Estado**: `PARTIAL`

- **Evidencia**: `PlaywrightAdapter` con timeout de 30s en navigate, 5s en fill/click; single retry via `contextlib.suppress`
- **Archivos**: `app/services/browser/playwright_adapter.py`
- **Tests existentes**: `test_semantic_matching.py` (indirecto) — no hay tests de browser hardening
- **Tests faltantes**: Test de timeout recovery; test de stale element; test de selector fallback; test de retry
- **Riesgos**: **Sin retry strategy**; sin fallback de selector (si el selector falla, el campo queda vacío); sin stale element recovery
- **Fix requerido** (BLOCKER PR-5): Implementar retry con backoff; fallback aria/placeholder; stale element detection
- **Acceptance criteria**: Fill retry ≤ 3 intentos antes de marcar campo HUMAN_REQUIRED; sin crashes silenciosos

---

## 15. Multi-step Forms

**Estado**: `PARTIAL`

- **Evidencia**: `WorkdayAdapter.submit()` y `GreenhouseAdapter.submit()` navegan multi-step con Next/Continue; `max_form_pages` configurable
- **Archivos**: `app/services/ats/workday.py`, `app/services/ats/greenhouse.py`
- **Tests existentes**: Unit tests con mock browser — PASS
- **Tests faltantes**: Test E2E de form de 5 pasos contra mock ATS; test de session loss mid-step
- **Riesgos**: Sin test de multi-step real; state entre pasos puede perderse en crash
- **Fix requerido**: Agregar form de 5 steps al mock ATS lab; test E2E de navegación completa
- **Acceptance criteria**: 5-step form navegado correctamente en mock ATS

---

## 16. iframes

**Estado**: `PARTIAL`

- **Evidencia**: `switch_to_frame()` en `PlaywrightAdapter`; `LeverAdapter.before_discover()` intenta switch a iframe
- **Archivos**: `app/services/browser/playwright_adapter.py`, `app/services/ats/lever.py`
- **Tests existentes**: Unit test de `switch_to_frame` con mock — PASS
- **Tests faltantes**: Test E2E de form dentro de iframe en mock ATS; test de iframe con cross-origin restrictions
- **Riesgos**: Lever usa iframe; sin test real; `switch_to_main_frame()` no testeado en flujo completo
- **Fix requerido**: Agregar fixture de iframe al mock ATS lab; test E2E
- **Acceptance criteria**: Form discovery funciona dentro de iframe en mock ATS

---

## 17. Human-in-the-loop

**Estado**: `READY`

- **Evidencia**: `submit()` requiere `human_confirmed=True` — hardcoded; `AgentError` si no; `_ALWAYS_HUMAN` en form_intelligence; frontend tiene botón de confirmación explícito
- **Archivos**: `app/services/application_agent_orchestrator.py:383`, `app/services/form_intelligence.py`
- **Tests existentes**: `test_orchestrator.py` — PASS
- **Tests faltantes**: Test de intento de submit sin `human_confirmed` → debe fallar
- **Riesgos**: Bajo
- **Fix requerido**: Agregar test negativo explícito para submit sin confirmación
- **Acceptance criteria**: 0 submits posibles sin `human_confirmed=True`

---

## 18. Pre-submit Validation

**Estado**: `PARTIAL`

- **Evidencia**: "Phase 6" en orchestrator revisa validación HTML5 del browser post-fill. No hay validador estructurado de pre-submit que chequee: required fields, files attached, no contradictions, sensitive fields confirmed.
- **Archivos**: `app/services/application_agent_orchestrator.py:458`
- **Tests existentes**: Ninguno específico para pre-submit
- **Tests faltantes**: Test de cada condición de bloqueo (campo required vacío, file faltante, claim contradicted)
- **Riesgos**: **Sin pre-submit validator estructurado** — el check actual es solo HTML5 validation del browser, que puede ser evadido o incompleto
- **Fix requerido** (BLOCKER PR-4): Implementar `PreSubmitValidator` con checklist completo; bloquear si falla
- **Acceptance criteria**: BLOCKED si: required field vacío, file faltante, claim contradicted, campo sensible sin confirmar

---

## 19. Submission

**Estado**: `PARTIAL`

- **Evidencia**: `submit()` en orchestrator llama `adapter.submit()` → `browser.click_submit()` → `is_confirmation_page()`
- **Archivos**: `app/services/application_agent_orchestrator.py:466`
- **Tests existentes**: `test_orchestrator.py` con mock — PASS
- **Tests faltantes**: Test contra mock ATS real (no mock browser); test de submit fallido → retry
- **Riesgos**: Sin retry en caso de submit fallido; sin timeout explícito en submit
- **Fix requerido**: Test E2E de submit contra mock ATS; retry en caso de network error
- **Acceptance criteria**: Submit success detectado correctamente; failure → status=failed (no silencioso)

---

## 20. Confirmation Detection

**Estado**: `PARTIAL`

- **Evidencia**: `is_confirmation_page()` via JS en `form_extractor.py` con 6 keywords + regex para confirmation ID; ATS-specific patterns en adapters
- **Archivos**: `app/services/browser/form_extractor.py:120`, `app/services/browser/playwright_adapter.py:249`
- **Tests existentes**: Test de mock ATS con página de confirmación — PASS
- **Tests faltantes**: Test de URL-transition-only confirmation; test de DOM marker; test de delayed confirmation
- **Riesgos**: Keywords pueden no coincidir con el idioma de la página (español/francés); sin fallback URL-based
- **Fix requerido**: Agregar fallback de URL transition a confirmation detection; test multilingual
- **Acceptance criteria**: Confirmation detectada en ≥ 95% de los casos del mock ATS lab; output `SUBMITTED_CONFIRMED` vs `SUBMISSION_UNCONFIRMED`

---

## 21. Resume after Interruption

**Estado**: `PARTIAL`

- **Evidencia**: `pause()` y `resume()` implementados; `resume_from_field()` con metadata en `error_message` (JSON)
- **Archivos**: `app/services/application_agent_orchestrator.py:241`
- **Tests existentes**: `test_orchestrator.py` cubre pause/resume — PASS
- **Tests faltantes**: Test de crash (proceso muere mid-fill) y restart; test de form expired en resume
- **Riesgos**: Metadata de pause almacenada en `error_message` (campo de texto) — frágil; no hay test de crash real
- **Fix requerido** (PR-5): Migrar metadata pause/resume a columna JSON estructurada; test de crash simulation
- **Acceptance criteria**: Resume después de crash restaura estado correcto; form expired → error claro

---

## 22. Tracking

**Estado**: `READY`

- **Evidencia**: `Application` ORM con status, events; `ApplicationSubmission` con confirmation_id; campos `fields_total`, `fields_auto_filled`, `fields_confirmed` en `ApplicationAgentSession`
- **Archivos**: `app/db/models/application.py`, `app/db/models/agent_session.py`
- **Tests existentes**: `test_applications.py` — PASS
- **Tests faltantes**: Test de event timeline completo post-submit
- **Riesgos**: Bajo
- **Fix requerido**: Ninguno crítico
- **Acceptance criteria**: Application trackeable desde Discovery hasta Submitted

---

## 23. Outcome Logging

**Estado**: `PARTIAL`

- **Evidencia**: `learning_loop.py` con `log_outcome()`, `hypothesis_test()`, `update_apply_threshold()`; `rank_jobs_with_outcomes()`
- **Archivos**: `app/services/learning_loop.py`, `app/services/job_recommender.py`
- **Tests existentes**: `test_sprints_b_through_l.py` — PASS
- **Tests faltantes**: Test de outcome loop cerrado (submit → outcome logged → threshold updated → ranker boost)
- **Riesgos**: Outcome loop no integrado end-to-end con el orchestrator
- **Fix requerido**: Test E2E del loop completo
- **Acceptance criteria**: Outcome registrado post-submit; threshold actualizable desde outcomes reales

---

## 24. AI Evals

**Estado**: `PARTIAL`

- **Evidencia**: `test_ai_evaluation_suite.py` con 11 tests (8 LLM-gated, 3 deterministic)
- **Archivos**: `backend/tests/test_ai_evaluation_suite.py`
- **Tests existentes**: 3 deterministic — PASS; 8 LLM → **SKIPPED** (sin API key)
- **Tests faltantes**: Ejecución real con API key; registro de latency/cost/tokens
- **Riesgos**: **8 de 11 AI evals nunca ejecutadas** — no se sabe si pasan en producción
- **Fix requerido** (BLOCKER PR-2): Configurar API key en CI; ejecutar evals; registrar resultados
- **Acceptance criteria**: Los 8 LLM tests pasan; resultados documentados con modelo/tokens/latency/cost

---

## 25. Real-model Tests

**Estado**: `NOT_READY`

- **Evidencia**: Ninguna prueba ejecutada con modelo real
- **Archivos**: N/A
- **Tests existentes**: Todos los LLM tests usan mocks
- **Tests faltantes**: Real-model run completo contra 3+ JDs y 1 candidato real
- **Riesgos**: **Crítico** — el producto puede fallar en producción de formas no capturadas por mocks
- **Fix requerido** (BLOCKER PR-2): Ejecutar con ANTHROPIC_API_KEY configurada; documentar resultados
- **Acceptance criteria**: CV factuality ≥ 0.95; personalization ≥ 0.80; evidence support ≥ 0.90

---

## 26. Security

**Estado**: `PARTIAL`

- **Evidencia**: SSRF protection en `app/core/ssrf.py`; rate limiting en `app/core/limiter.py`; auth en `app/core/auth.py`; ownership checks en routes
- **Archivos**: `app/core/ssrf.py`, `app/core/security.py`, `app/core/limiter.py`
- **Tests existentes**: `test_security.py` — PASS
- **Tests faltantes**: Test de prompt injection en form fields; test de malicious HTML en job description; test de SSRF con IP interna; test de auth bypass
- **Riesgos**: Prompt injection desde job descriptions o form fields hacia el LLM; malicious file upload; browser isolation
- **Fix requerido** (PR-7): Security review completo; `docs/SECURITY_PRODUCTION_REVIEW.md`
- **Acceptance criteria**: 0 critical security issues; prompt injection sanitizado

---

## 27. Privacy

**Estado**: `PARTIAL`

- **Evidencia**: No hay PII logging explícito; screenshots guardados en filesystem
- **Archivos**: `app/services/application_agent_orchestrator.py:55` (`_save_screenshot`)
- **Tests existentes**: Ninguno de privacidad
- **Tests faltantes**: Test de que screenshots no se retienen más de X días; test de deletion de datos de candidato
- **Riesgos**: Screenshots contienen PII (CV, campos de formulario); no hay retention policy implementada
- **Fix requerido** (PR-7): `docs/PRIVACY_PRODUCTION_REVIEW.md`; retention policy en screenshots
- **Acceptance criteria**: Screenshots purgados en ≤ 30 días; sin PII en logs

---

## 28. Observability

**Estado**: `PARTIAL`

- **Evidencia**: `structlog` en todo el backend; `cost_tracker.py` para costos LLM; `fields_total`/`fields_auto_filled` en session; screenshot paths trackeados
- **Archivos**: `app/core/logging.py`, `app/services/ai/cost_tracker.py`, `app/db/models/agent_session.py`
- **Tests existentes**: Implícito en tests de servicio
- **Tests faltantes**: Test de trace completo de un application flow; test de cost por flow
- **Riesgos**: No hay `application_id` en todos los log events; `retry_count` no trackeado; `duration` no trackeado
- **Fix requerido** (PR-7): Añadir `application_id`, `duration`, `retry_count` a todos los log events críticos
- **Acceptance criteria**: Cada flow rastreable por `application_id` de punta a punta

---

## 29. Cost Monitoring

**Estado**: `PARTIAL`

- **Evidencia**: `cost_tracker.py` acumula costos por modelo; estimaciones hardcodeadas por token
- **Archivos**: `app/services/ai/cost_tracker.py`
- **Tests existentes**: Unit test de cost estimation — PASS
- **Tests faltantes**: Test de alerta si cost > budget; test de cost por application end-to-end
- **Riesgos**: Sin alerta de budget; costos pueden acumularse silenciosamente
- **Fix requerido** (PR-7): Budget alert; costo por application en observability output
- **Acceptance criteria**: Log de costo total por application; alerta si > $X

---

## 30. Frontend

**Estado**: `PARTIAL`

- **Evidencia**: Pages: dashboard, profile, jobs, applications, CV, recommendations, interview prep, analyze. Application detail page con flujo de agente (start → awaiting_human → confirm → submit)
- **Archivos**: `frontend/src/app/`
- **Tests existentes**: Ninguno de frontend
- **Tests faltantes**: Test E2E de frontend (Playwright/Cypress); test de Application Control Center completo
- **Riesgos**: Application Control Center no tiene todas las pantallas del flujo completo (Answer Pending, Pre-submit check, Track Outcome)
- **Fix requerido** (PR-6): Completar Application Control Center; agregar pantallas faltantes
- **Acceptance criteria**: Flow completo navegable desde UI: Start → Review → Confirm → Submit → Track

---

## 31. CI/CD

**Estado**: `NOT_READY`

- **Evidencia**: No hay `.github/workflows/` ni pipeline de CI
- **Archivos**: N/A
- **Tests existentes**: N/A
- **Tests faltantes**: GitHub Actions workflow con pytest + ruff + mypy
- **Riesgos**: Sin CI, los tests no se ejecutan en PRs automáticamente
- **Fix requerido** (PR-8): Crear `.github/workflows/ci.yml` con test suite + lint
- **Acceptance criteria**: PR bloqueado si tests fallan; AI evals corren con API key en CI

---

## 32. Deployment Readiness

**Estado**: `NOT_READY`

- **Evidencia**: `docker-compose.yml` existe; no hay pipeline de deploy; no hay health checks; no hay migration strategy para producción
- **Archivos**: `docker-compose.yml`
- **Tests existentes**: N/A
- **Tests faltantes**: Deploy a staging; smoke tests post-deploy
- **Riesgos**: Sin health check endpoint documentado; sin estrategia de migración DB en producción
- **Fix requerido** (PR-8): Health check `/api/health`; migration strategy; deploy staging
- **Acceptance criteria**: Deploy reproducible; health check responde 200; migrations corren sin downtime

---

## Resumen ejecutivo

| # | Dimensión | Estado |
|---|-----------|--------|
| 1 | Candidate profile | `READY` |
| 2 | CV personalization | `PARTIAL` |
| 3 | Evidence validation | `PARTIAL` ⚠️ |
| 4 | Requirement matching | `PARTIAL` ⚠️ |
| 5 | Job Fit | `READY` |
| 6 | Career Fit | `PARTIAL` |
| 7 | Application strategy | `READY` |
| 8 | Cover letter | `READY` |
| 9 | Application answers | `PARTIAL` ⚠️ |
| 10 | Form intelligence | `PARTIAL` |
| 11 | Candidate knowledge resolution | `READY` |
| 12 | File uploads | `PARTIAL` ⚠️ |
| 13 | ATS adapters | `PARTIAL` ⚠️ |
| 14 | Browser reliability | `PARTIAL` ⚠️ |
| 15 | Multi-step forms | `PARTIAL` |
| 16 | iframes | `PARTIAL` |
| 17 | Human-in-the-loop | `READY` |
| 18 | Pre-submit validation | `PARTIAL` ⚠️ |
| 19 | Submission | `PARTIAL` |
| 20 | Confirmation detection | `PARTIAL` |
| 21 | Resume after interruption | `PARTIAL` |
| 22 | Tracking | `READY` |
| 23 | Outcome logging | `PARTIAL` |
| 24 | AI evals | `PARTIAL` ⚠️ |
| 25 | Real-model tests | `NOT_READY` 🔴 |
| 26 | Security | `PARTIAL` |
| 27 | Privacy | `PARTIAL` |
| 28 | Observability | `PARTIAL` |
| 29 | Cost monitoring | `PARTIAL` |
| 30 | Frontend | `PARTIAL` |
| 31 | CI/CD | `NOT_READY` 🔴 |
| 32 | Deployment readiness | `NOT_READY` 🔴 |

**READY**: 7 / 32  
**PARTIAL**: 22 / 32  
**NOT_READY**: 3 / 32  
**BLOCKED**: 0 / 32

---

## Release Blockers (P0)

1. **Real-model tests nunca ejecutados** — no hay evidencia de que el LLM funcione en producción
2. **ATS adapters sin validación real** — todo testeado con mocks; cero flujos reales ejecutados
3. **Pre-submit validator no existe como componente estructurado** — riesgo de submit con datos incompletos
4. **Evidence system con dos definiciones de "semantic"** — ambigüedad conceptual y de score
5. **CI/CD inexistente** — sin automatización de tests en PRs
6. **Campos sensibles (salary/sponsorship/demographic) sin test explícito** — riesgo de auto-fill indebido
7. **File upload sin test E2E real** — upload puede fallar silenciosamente

---

*Próximos pasos: ver `docs/PRODUCTION_HARDENING_ROADMAP.md`*
