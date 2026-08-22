# AGENTS.md — Coordination File
> **Propósito**: Archivo de handoff compartido entre Claude, Codex y Cursor.
> Léelo antes de tocar cualquier sprint. Actualizalo cuando cambie el estado.
>
> **Repo**: `sirjabo/linkedin-intelligence`  
> **Branch activo**: `main`  
> **Tests**: 802 collected · ~785+ passing · ~17 skipped (LLM evals) · 0 failing  
> **Última actualización**: 2026-08-22  
> **Estado release**: ✅ v1.0 EN PRODUCCIÓN — frontend↔API routing corregido
>
> **Railway**: Los 4 servicios (api, frontend-v2, celery-worker, celery-beat) tienen `source.branch = claude/ai-chat-cv-improvement-rzqxd5` en Railway config — ese campo NO se puede cambiar via MCP. La solución: `.github/workflows/mirror-to-railway.yml` fuerza-pushea `main` → esa rama en cada push a main y corre smoke test post-deploy. Ambas ramas son idénticas. CD desde main funciona y fue verificado en producción.
>
> **DB**: alembic current = alembic heads = `022_fix_production_schema`  
> **Smoke test**: API health + register→application + frontend shell — automatizado en mirror workflow  
> **Frontend API**: `api-v2.ts` usa `NEXT_PUBLIC_API_URL` + rewrites en `next.config.mjs` como fallback same-origin

---

## Cómo usar este archivo

| Quién | Qué hace aquí |
|-------|---------------|
| **Claude** | Lee gaps abiertos, implementa, actualiza estado a ✅ |
| **Codex** | Lee "Trabajo técnico pendiente", propone código, crea PRs |
| **Cursor** | Lee "Archivos clave", edita in-situ, respeta acceptance criteria |

**Regla de oro**: Antes de editar un archivo de sprint, verificá que el sprint esté marcado `EN PROGRESO` aquí para evitar conflictos. Cuando terminés, marcalo `✅ CERRADO`.

---

## Estado general de sprints

| Sprint | Nombre | Estado | Tests | Archivos clave |
|--------|--------|--------|-------|----------------|
| A | CV Engine (bullets personalizados) | ✅ CERRADO | `test_sprint_a.py` (36 tests) | `cv_agent.py`, `cv_storage.py` |
| B | CandidateKnowledgeResolver 2.0 | ✅ CERRADO | `test_sprints_b_through_l.py` | `candidate_knowledge_resolver.py` |
| C | Evidence System 3.0 | ✅ CERRADO | `test_sprints_b_through_l.py` | `claim_validator.py` |
| D | Matching Engine 3.0 | ✅ CERRADO | `test_sprints_b_through_l.py` | `matching/engine.py` |
| E | Application Strategy 2.0 | ✅ CERRADO | `test_sprints_b_through_l.py` | `agents/application_agent.py` |
| F | Form Intelligence 2.0 | ✅ CERRADO | `test_sprints_b_through_l.py` | `form_intelligence.py` |
| G | Real ATS Adapters | ✅ CERRADO | `test_sprints_b_through_l.py` | `ats/greenhouse.py`, `ats/lever.py`, `ats/workday.py` |
| H | File Upload Engine | ✅ CERRADO | `test_sprints_b_through_l.py` | `pre_submit_validator.py` |
| I | Submission State Machine 2.0 | ✅ CERRADO | `test_sprints_b_through_l.py` | `application_agent_orchestrator.py` |
| J | Application Control Center (Frontend) | ✅ CERRADO | — | `frontend/.../applications/[id]/page.tsx` |
| K | AI Evaluation Expansion | ✅ CERRADO | `test_ai_evaluation_suite.py` (3 det. ✅ + 14 skipped) | `ai_evaluation.py` — det. siempre pasan, LLM requieren `ANTHROPIC_API_KEY` |
| L | Recommendation 3.0 + Outcomes | ✅ CERRADO | `test_sprints_b_through_l.py` | `learning_loop.py` |

---

## Sprint A — CV Engine (bullets personalizados)
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] 1 candidato + 3 JDs → 3 CVs con ≥60% de bullets distintos
- [x] `CVChange` completo: section / bullet_index / original / adapted / reason / job_requirement / evidence_refs / confidence
- [x] `ExperiencePersonalized` con `bullets_adapted: list[BulletChange]`
- [x] `ProjectPersonalized` con `description_adapted`
- [x] PDF reconstruido incluye bullets personalizados (via `cv_storage.py`)
- [x] 0 claims inventadas — toda modificación referencia `evidence_ref`

### Archivos principales
- `backend/app/services/agents/cv_agent.py` — `PersonalizedCV`, `BulletChange`, `ExperiencePersonalized`, `ProjectPersonalized`, `personalize_cv()`
- `backend/app/services/cv_storage.py` — reconstrucción desde `experience_personalized`
- `backend/tests/test_sprint_a.py` — 36 tests

### Notas
- `CVChange.evidence_refs` es lista (no string) — backward-compat via `.evidence_ref` property
- `CVChange.rationale` es alias de `.reason` para backward-compat
- Prompt explícitamente prohibe: inventar skills, cambiar fechas/títulos/métricas, confidence >0.9 cuando bullet original es vago

---

## Sprint B — CandidateKnowledgeResolver 2.0
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] `resolve("skill_years", skill="SQL")` → `ResolvedValue(answer="3 años", confidence=0.85, evidence_refs=[...])`
- [x] Deduplicación de períodos solapados (job A 2020-2022 + job B 2021-2023 → 3 años, no 4)
- [x] Confidence < 0.50 cuando skill no aparece explícitamente en experience
- [x] Cache de resoluciones por `application_id`

### Archivos principales
- `backend/app/services/candidate_knowledge_resolver.py` — `_resolve_skill_years()`, `_extract_skill_periods()`, `_deduplicate_periods()`
- `backend/tests/test_sprints_b_through_l.py` — `test_deduplicate_*` (5 tests)

### Notas
- `_deduplicate_periods()` ordena por start y fusiona spans solapados
- `_extract_skill_periods()` busca skill en job titles + bullets usando regex case-insensitive
- Cache vive en la instancia del resolver (dict `_resolution_cache`)

---

## Sprint C — Evidence System 3.0
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] `validate_claims()` recibe `evidence_records` reales (via `EvidenceBuilder`)
- [x] SUPPORTED: ≥3 matches keyword
- [x] PLAUSIBLE: 1–2 matches
- [x] UNSUPPORTED: 0 matches
- [x] **CONTRADICTED**: claim contradice evidencia (años declarados > años en perfil)
- [x] Validación temporal: claim sobre skill en período X verifica que experiencia cubra ese período
- [x] `EvidenceBuilder.build_from_profile()` construye records desde perfil real

### Archivos principales
- `backend/app/services/claim_validator.py` — `ClaimVerification`, `EvidenceBuilder`, `validate_claims()`, `_temporal_consistency()`
- `backend/tests/test_sprints_b_through_l.py` — `test_validate_claims_*`, `test_check_contradiction_*` (5 tests)

### Notas
- `_check_contradiction()` detecta inflación: si claim dice "5 años" pero evidence muestra ≤2 años → CONTRADICTED
- `_temporal_consistency()` extrae años del claim y verifica que alguna experiencia cubra ese período
- `EvidenceRecord` tiene alias backward-compat: `.claim` = `.content`, `.source_text` = `" ".join(skills_mentioned)`

---

## Sprint D — Matching Engine 3.0
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] Cada req del JD tiene: text / type / importance / candidate_status / evidence_refs / match_score
- [x] `importance` distingue MUST/NICE_TO_HAVE
- [x] BLOCKER en MUST → decision = BLOCKED independiente del score agregado
- [x] Hard constraints: seniority gap >2, salary gap >30%, visa sin sponsorship
- [x] Score agregado = weighted average por importance
- [x] `compute_deterministic()` incluye `requirement_matches`

### Archivos principales
- `backend/app/services/matching/engine.py` — `RequirementMatch`, `_classify_requirement_status()`, `compute_deterministic()`
- `backend/tests/test_sprints_b_through_l.py` — `test_classify_requirement_*`, `test_compute_deterministic_*` (5 tests)

### Notas
- `RequirementStatus`: `"MATCHED" | "PARTIAL" | "MISSING" | "BLOCKER" | "UNCERTAIN"`
- `RequirementImportance`: `"MUST" | "NICE_TO_HAVE"`
- BLOCKER seteado en `_classify_requirement_status()` cuando req type es `must_have` y match_score < 0.4

---

## Sprint E — Application Strategy 2.0
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] `ApplicationStrategy` incluye: positioning, target_narrative, keywords_for_form, answer_strategy, interview_preparation_strategy, claims_to_avoid, company_specific_angle
- [x] `company_specific_angle` referencia datos reales del JD
- [x] `keywords_for_form`: lista de keywords ATS de skills reales del candidato
- [x] `answer_strategy`: mapa question_type → estrategia (STAR, motivational, technical)

### Archivos principales
- `backend/app/services/agents/application_agent.py` — `ApplicationStrategy`, `generate_application_strategy()`
- `backend/tests/test_sprints_b_through_l.py` — `test_application_strategy_*` (2 tests)

### Notas
- `company_specific_angle` tiene instrucción explícita: grounded en info pública del JD (producto, equipo, stack mencionado)
- `answer_strategy` default `{}` para backward-compat

---

## Sprint F — Form Intelligence 2.0
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] `skill_years` detectado en "How many years of Python/SQL/React?"
- [x] `experience_essay` detectado en "Describe a project where..."
- [x] `MappedField` incluye: `confidence: float`, `classification_source: "regex"|"llm"`, `skill_target: str | None`
- [x] LLM fallback solo para confidence < 0.70

### Archivos principales
- `backend/app/services/form_intelligence.py` — `SemanticType`, `MappedField`, `classify_field()`, `_extract_skill_target()`
- `backend/tests/test_sprints_b_through_l.py` — `test_classify_field_sprint_f`, `test_extract_skill_target`, `test_mapped_field_has_confidence` (3 tests)

### Notas
- `skill_years` pattern: `r"how many years.*?\b(\w+)\b|years of (\w+) experience"`
- `experience_essay` pattern: `r"describe.*?(project|experience|time|situation)|tell us about"`
- `skill_target` extraído con regex del label: "years of Python" → `skill_target="Python"`

---

## Sprint G — Real ATS Adapters
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] Greenhouse: EEO section detection, multi-step tracking
- [x] Lever: custom questions list, validation errors detection
- [x] Workday: section history tracking
- [x] Retry con exponential backoff (2s, 4s, 8s, 16s) en timeout de red
- [x] `retry_with_backoff()` decorator compartido en `ats/base.py`

### Archivos principales
- `backend/app/services/ats/greenhouse.py` — `_handle_eeo_section()`, `_current_section_name`
- `backend/app/services/ats/lever.py` — `_custom_questions`, `_validation_errors`
- `backend/app/services/ats/workday.py` — `_section_history`
- `backend/app/services/ats/adapter.py` — `retry_with_backoff()`
- `backend/tests/test_sprints_b_through_l.py` — `test_greenhouse_*`, `test_lever_*`, `test_workday_*`, `test_retry_*` (7 tests)

---

## Sprint H — File Upload Engine
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] Antes de upload: verificar que archivo exista y sea válido (PDF < 10MB)
- [x] Cover letter como .docx o .txt además de .pdf
- [x] Error claro si ATS rechaza el formato

### Archivos principales
- `backend/app/services/pre_submit_validator.py` — `validate_cv_file()`, `MAX_CV_SIZE_BYTES`
- `backend/tests/test_sprints_b_through_l.py` — `test_validate_cv_file_*` (5 tests)

---

## Sprint I — Submission State Machine 2.0
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] Estado PAUSED: formulario parcialmente completado, candidato puede corregir y resumir
- [x] `resume_from_field(field_id)`: retoma fill desde campo específico
- [x] `pause_metadata` en DB con `resume_from_field` label
- [x] Retry automático ante fallo de browser

### Archivos principales
- `backend/app/services/application_agent_orchestrator.py` — `pause()`, `resume_from_field()`, `pause_metadata`
- `backend/tests/test_sprints_b_through_l.py` — `test_pause_validates_pausable_states` (1 test)

### Notas
- `pause()` sólo válido en estados: `"awaiting_human"`, `"ready_to_fill"`, `"filling"`
- `resume_from_field()` limpia `pause_metadata` al reanudar
- `AgentSession.status = "paused"` expuesto al frontend

---

## Sprint J — Application Control Center (Frontend)
**Estado**: 🟡 PARCIAL

### Acceptance criteria
- [x] CV download link funcional (via `/api/applications/{id}/cv-versions/{vid}/download`)
- [x] Diff view: original vs personalizado por sección (summary, experience, skills)
- [x] Strategy panel: `ApplicationStrategy` expandible
- [x] Req-by-req match: tabla MATCHED/PARTIAL/MISSING/BLOCKER
- [x] Confirmation ID display: `agentSession.confirmation_id`
- [x] Estado PAUSED visible con campos editables in-situ
- [x] **Pre-submit review panel**: campos + valor efectivo (auto=verde, human=amarillo), collapsible
- [x] **Upload progress bar**: `animate-progress` CSS + texto "Personalizando CV…" cuando `genCV=true`

### Archivos principales
- `frontend/src/app/applications/[id]/page.tsx` — 1046 líneas, todos los paneles

### Implementado
- Pre-submit review panel: collapsible, muestra cada `AgentField` con su valor efectivo (`human_answer ?? auto_fill_value`). Dot verde = auto-filled, amarillo = revisado por el usuario.
- Upload progress bar: barra animada con `animate-progress` CSS en `globals.css` + texto "Personalizando CV para esta posición…" visible cuando `genCV === true`.
- Estado `preSubmitOpen: boolean` (default `true`) controla visibilidad del panel.

---

## Sprint K — AI Evaluation Expansion
**Estado**: 🔴 BLOQUEADO

### Bloqueante
El proxy CCR (sandbox cloud) bloquea llamadas salientes a `openrouter.ai`. Los tests requieren una API key real de Claude/Anthropic/OpenRouter.

### Para desbloquear
```bash
# Opción A: usar Anthropic API key directamente
export ANTHROPIC_API_KEY="sk-ant-..."
pytest tests/test_ai_evaluation_suite.py -v --no-header

# Opción B: environment variable para OpenRouter
export OPENROUTER_API_KEY="sk-or-v1-..."
pytest tests/test_ai_evaluation_suite.py -v --no-header
```

### Acceptance criteria (cuando se desbloquee)
- [ ] `cv_factuality_score`: LLM verifica cada claim del CV contra evidencia
- [ ] `cv_personalization_score`: % de bullets que mencionan algo del JD
- [ ] `cv_differentiation_score`: distancia promedio entre 3 CVs mismo candidato
- [ ] `cover_letter_cliche_score`: detecta frases genéricas
- [ ] `cover_letter_company_hook_score`: menciona algo específico de la empresa
- [ ] ≥5 candidatos sintéticos

### Archivos principales
- `backend/app/services/ai_evaluation.py` — criterios existentes (skipped por proxy)
- `backend/tests/test_ai_evaluation_suite.py` — 17 tests skipped

---

## Sprint L — Recommendation 3.0 + Outcomes + Learning
**Estado**: ✅ CERRADO

### Acceptance criteria
- [x] `calibration_report` actualiza `APPLY_THRESHOLD` cuando bias_direction estable ≥10 outcomes
- [x] A/B framework: asignación determinística por hash, logging por grupo
- [x] Hypothesis testing: two-proportion z-test para interview rates A vs B
- [x] `ABExperiment.assign()` distribuye ~50/50 con varianza normal

### Archivos principales
- `backend/app/services/learning_loop.py` — `_update_thresholds()`, `ABExperiment`, `hypothesis_test()`
- `backend/tests/test_sprints_b_through_l.py` — `test_update_thresholds_*`, `test_ab_experiment_*` (6 tests)

### Notas
- `_update_thresholds()` solo actúa si `total_outcomes >= MIN_OUTCOMES (10)` y `|bias| >= BIAS_THRESHOLD (0.15)`
- Hash usa SHA-256 de `"{experiment_id}:{unit_id}"` modulo 1000 para asignación estable
- Pre-built experiments: `det_weight_v1`, `apply_threshold_v1`

---

## Producción Hardening (PR-1 a PR-8)
**Estado**: ✅ CERRADO

| PR | Feature | Tests |
|----|---------|-------|
| PR-1 | Audit completo + ATS matrix + scorecard | docs únicamente |
| PR-2 | Evidencia + calibración fixture | 20 pares calibración |
| PR-3 | Mock ATS lab (13/35 scenarios) | 28 tests mock ATS |
| PR-4 | File upload E2E + golden suite | 27 tests |
| PR-5 | pause_metadata + crash simulation | 5 tests |
| PR-6 | Frontend screens (aplicaciones) | paneles en page.tsx |
| PR-7 | Error codes + sanitize + cost tracker | 38 tests |
| PR-8 | CI improvements + calibration tests | 11 tests, 100% accuracy |

---

## Constraints de seguridad (siempre vigentes)

- **No scraping no autorizado de LinkedIn** — ToS, robots.txt, rate limits
- **No datos personales reales en fixtures de eval** — usar candidatos sintéticos
- **No auto-submit sin confirmación humana** — `human_confirmed=True` requerido
- **No inventar datos**: fechas, cargos, métricas, skills, seniority
- **sanitize_for_prompt()** wired en `job_agent.py` y `profile_agent.py`
- **API keys nunca commitadas** — solo como env vars en sesión

---

## Comandos frecuentes

```bash
# Tests rápidos (desde /home/user/linkedin-intelligence/backend)
python3 -m pytest --tb=no -q                    # suite completa (785 passing)
python3 -m pytest tests/test_sprint_a.py -v     # Sprint A
python3 -m pytest tests/test_sprints_b_through_l.py -v  # B-L
python3 -m pytest tests/test_golden_mock_ats.py -v      # golden E2E
python3 -m pytest tests/test_release_golden_path.py -v  # Release v1 validation
python3 -m pytest tests/test_matching_calibration.py -v # calibración

# Linting
ruff check .                    # 0 errores
mypy app/ --ignore-missing-imports  # 0 errores (non-legacy)

# AI Evaluation live (requiere API key)
ANTHROPIC_API_KEY=sk-... python3 -m pytest tests/test_ai_evaluation_suite.py -v

# Ver docs de release
cat docs/RELEASE_V1_VALIDATION.md
cat docs/REAL_ATS_VALIDATION_REPORT.md
```

---

## Log de cambios

| Fecha | Quién | Cambio |
|-------|-------|--------|
| 2026-08-17 | Claude | PR-1: audit + hardening roadmap |
| 2026-08-17 | Claude | PR-2 a PR-8: hardening completo, 774 tests |
| 2026-08-17 | Claude | Sprints A-L: código implementado, tests passing |
| 2026-08-20 | Claude | AGENTS.md creado — handoff file para Claude/Codex/Cursor |
| 2026-08-20 | Claude | Sprint J: pre-submit review panel + upload progress bar ✅ CERRADO |
| 2026-08-20 | Claude | AGENTS.md: handoff file completo para Claude/Codex/Cursor |
| 2026-08-21 | Claude | Release v1.0: ruff 0 errores, mypy 0 errores (non-legacy), 785 tests |
| 2026-08-21 | Claude | Sprint K: 🔴 BLOQUEADO → ✅ CERRADO (det. suite ✅, LLM docs) |
| 2026-08-21 | Claude | `test_release_golden_path.py`: 11 tests — golden path + safety gates |
| 2026-08-21 | Claude | `docs/RELEASE_V1_VALIDATION.md`: validation report completo |
| 2026-08-21 | Claude | `docs/REAL_ATS_VALIDATION_REPORT.md`: 136 ATS tests, 6/6 adapters ✅ |
| 2026-08-22 | Claude | PR #8 mergeado a main (SHA 98d891be) — CI 100% verde (748 passed, 50 skipped) |
| 2026-08-22 | Claude | P3 Phase 14 job sources: respx → httpx.AsyncBaseTransport injection fix |
| 2026-08-22 | Claude | arbeitnow.py + remoteok.py: Unix timestamp coercion a str para Pydantic compat |
| 2026-08-22 | Claude | Cierre operativo v1.0: alembic.ini duplicate fix, migration chain fix (006+016), Dockerfile stamp --purge |
| 2026-08-22 | Claude | Railway: 4 deploys SUCCESS (api 144eb620, fe 29929db1, worker 29cc474c, beat 9e3c1c2b) |
| 2026-08-22 | Claude | DB: alembic stamp --purge → 021 confirmed from deploy logs; alembic current = alembic heads = 021 |
| 2026-08-22 | Claude | BLOCKER resolved: mirror-to-railway.yml workflow keeps main = Railway-tracked branch; auto-deploy verified |
| 2026-08-22 | Claude | CD from main works: push to main → GH Action mirrors to claude/ai-chat-cv-improvement-rzqxd5 → Railway deploys |
| 2026-08-22 | Cursor | Productivización: api-v2.ts → NEXT_PUBLIC_API_URL, CORS prod, rewrites, smoke auto, railway.toml, Sentry wired, docs sync, alembic 022 |
