# LinkedIn Intelligence 2.0 — Master Gap Analysis

> Actualizado: 2026-08-14
> Basado en: directiva `LINKEDIN_INTELLIGENCE_MASTER_IMPLEMENTATION_DIRECTIVE.md` + código real
> Branch: `claude/new-session-ce0sct`
> Tests: 90 pasando, 0 fallando

---

## Metodología

Análisis basado en lectura directa del código fuente. No en documentación. Cada ítem verifica
archivos reales en `backend/` y `frontend/`. Estado refleja la situación post-implementación
de las Fases 1–11.

---

## Resumen ejecutivo

Fases 1–11 implementaron la fundación completa: auth, perfil de candidato, ingesta de fuentes,
matching híbrido (determinístico + LLM), workspace de postulación, analytics, seguridad básica,
CI/CD, health score del perfil, expansión semántica de skills, y registro de outcome.

Las capacidades P0 más críticas aún ausentes son:
1. Rate limiting en endpoints de auth (seguridad)
2. Hard Constraints Layer en matching (trabajo autorizado, salario, seniority imposible)
3. Career Fit separado de Job Fit
4. Application Decision Engine (APPLY / STRETCH / DO_NOT_APPLY / BLOCKED)
5. Form Intelligence (enteramente ausente)
6. Submission + Confirmation workflow (ausente)
7. Account deletion / GDPR

---

## Tabla de capacidades

| # | Capacidad | Estado | Tests | Notas |
|---|-----------|--------|-------|-------|
| **CANDIDATE** | | | | |
| 1 | Auth register/login/refresh | ✅ IMPLEMENTED | ✅ 9 tests | Refresh tokens, password strength |
| 2 | JWT stdlib (no cffi) | ✅ IMPLEMENTED | ✅ 5 tests | HMAC-SHA256 |
| 3 | Password hash (pbkdf2) | ✅ IMPLEMENTED | ✅ | |
| 4 | Rate limiting en auth | ❌ MISSING | ❌ | Brute force sin protección |
| 5 | Candidate model básico | ✅ IMPLEMENTED | ✅ | name, location, target_roles, preferences |
| 6 | Work authorization field | ❌ MISSING | ❌ | No existe campo en modelo |
| 7 | Availability field | ❌ MISSING | ❌ | No existe campo en modelo |
| 8 | Standard application answers | ❌ MISSING | ❌ | No existe entidad pre-guardada |
| 9 | STAR stories pre-guardadas | ❌ MISSING | ❌ | Solo se generan per-application |
| 10 | Career goals / motivations | ❌ MISSING | ❌ | No existe campo |
| 11 | CandidateSource (text/PDF) | ✅ IMPLEMENTED | ✅ | CV, LinkedIn, GitHub, Portfolio, Manual |
| 12 | GitHub source ingestion real | ❌ MISSING | ❌ | Solo acepta texto pegado, no API de GitHub |
| 13 | Profile extraction (LLM) | ✅ IMPLEMENTED | ✅ mock | EvidenceRef, SkillExtracted, ExperienceExtracted |
| 14 | Profile consolidation multi-fuente | ✅ IMPLEMENTED | ✅ mock | Bug de modelo inválido fixeado |
| 15 | EvidenceRecord storage | ✅ IMPLEMENTED | ✅ | claim, evidence_type, source_text, strength |
| 16 | ProfileConflict detection + UI | ⚠️ PARTIAL | ❌ | Campo `conflicts` en JSON, sin UI de resolución |
| 17 | Profile health score | ✅ IMPLEMENTED | ✅ | 10 checks, tips accionables |
| 18 | Profile Quality (vs Completeness) | ⚠️ PARTIAL | ❌ | Solo completeness, no quality ni evidence coverage |
| 19 | Profile editor con evidencia | ⚠️ PARTIAL | ❌ | UI edita campos básicos, no experience/projects |
| 20 | Account deletion (GDPR) | ❌ MISSING | ❌ | No existe endpoint |
| **JOB** | | | | |
| 21 | Job create + JD parsing (LLM) | ✅ IMPLEMENTED | ✅ 11 tests | title, company, seniority, tech_stack, requirements |
| 22 | Job list/get | ✅ IMPLEMENTED | ✅ | |
| 23 | Job deduplication | ❌ MISSING | ❌ | Mismo trabajo puede guardarse múltiples veces |
| 24 | JobSource extensible (Protocol) | ✅ IMPLEMENTED | ✅ | base.py con JobSource Protocol |
| 25 | Remotive adapter | ✅ IMPLEMENTED | ✅ | Único adapter implementado |
| 26 | Greenhouse / Lever / Ashby adapters | ❌ MISSING | ❌ | Solo Remotive |
| 27 | MANDATORY / PREFERRED / INFERRED classification | ⚠️ PARTIAL | ✅ | must_have / nice_to_have, falta INFERRED/UNKNOWN |
| 28 | Job normalization canónica | ⚠️ PARTIAL | ❌ | Parcial en JobAgent, sin pipeline explícito |
| 29 | Company Intelligence (separado de Job) | ❌ MISSING | ❌ | company_description en Job, sin entidad propia |
| 30 | Salary extraction + normalization | ⚠️ PARTIAL | ✅ | salary_min/max en modelo, no siempre extraído |
| **MATCHING** | | | | |
| 31 | Matching determinístico (4 componentes) | ✅ IMPLEMENTED | ✅ 5 unit | skill_overlap, experience, location, education |
| 32 | Matching con salary scoring | ✅ IMPLEMENTED | ✅ | Opcional, backward-compatible |
| 33 | Semantic skill expansion (sinónimos) | ✅ IMPLEMENTED | ✅ | 25+ grupos de aliases |
| 34 | LLM reasoning layer | ✅ IMPLEMENTED | ✅ mock | reasoning, strengths, gaps, recommendation |
| 35 | Layer 1 — Hard Constraints | ❌ MISSING | ❌ | Sin work_auth, seniority imposible, salary blocker |
| 36 | Layer 2 — Per-requirement coverage | ❌ MISSING | ❌ | No score por requirement individual |
| 37 | Layer 3 — Semantic experience matching | ❌ MISSING | ❌ | Solo keyword overlap |
| 38 | Layer 4 — Seniority deep evaluation | ⚠️ PARTIAL | ✅ | SENIORITY_RANK existe, falta scope/ownership |
| 39 | Layer 5 — Domain experience | ❌ MISSING | ❌ | |
| 40 | Layer 6 — Transferable skills | ❌ MISSING | ❌ | |
| 41 | Career Fit (separado de Job Fit) | ❌ MISSING | ❌ | Un solo score, no diferencia fit laboral de carrera |
| 42 | Application Decision Engine | ⚠️ PARTIAL | ✅ | LLM recommendation: apply/stretch/pass. Sin BLOCKED |
| 43 | Outcome tracking (registro) | ✅ IMPLEMENTED | ✅ | outcome column en match_analyses |
| 44 | Learning loop (ajuste de pesos) | ❌ MISSING | ❌ | Outcome registrado pero no usado para aprender |
| **APPLICATION** | | | | |
| 45 | Application CRUD completo | ✅ IMPLEMENTED | ✅ 17 tests | notes, follow_up_date, events |
| 46 | Application state machine | ⚠️ PARTIAL | ✅ | 7 estados (draft→rejected), falta discovering/ready |
| 47 | Application strategy (LLM) | ✅ IMPLEMENTED | ✅ mock | approach, cv_changes, cover_letter_key_points |
| 48 | CV personalization (LLM) | ✅ IMPLEMENTED | ✅ mock | changes con original/adapted/rationale/evidence_ref |
| 49 | CV change explainability | ✅ IMPLEMENTED | ✅ | CVChange model con original/adapted/rationale |
| 50 | Cover letter generation (LLM) | ✅ IMPLEMENTED | ✅ mock | |
| 51 | Application answers (backend) | ✅ IMPLEMENTED | ✅ mock | |
| 52 | Application answers (frontend) | ✅ IMPLEMENTED | ✅ | textarea + generate con IA |
| 53 | Readiness checklist | ✅ IMPLEMENTED | ✅ | CV ✓, carta ✓, estrategia ✓, enviado ✓ |
| 54 | Evidence validation (claim validator) | ✅ IMPLEMENTED | ✅ | Regex + keyword overlap. No semántico |
| 55 | Evidence classification (SUPPORTED/PLAUSIBLE/UNSUPPORTED) | ❌ MISSING | ❌ | Solo verified/unverified |
| 56 | Evidence graph (requirement → claim) | ❌ MISSING | ❌ | |
| 57 | Master CV concept | ❌ MISSING | ❌ | CVVersion per application, no Master CV base |
| 58 | CV version compare | ❌ MISSING | ❌ | |
| 59 | Application workspace unificado | ✅ IMPLEMENTED | ✅ | /applications/[id] con todas las secciones |
| 60 | Interview prep (backend) | ✅ IMPLEMENTED | ✅ mock | questions, STAR stories, company research |
| 61 | Interview prep (frontend) | ✅ IMPLEMENTED | ✅ | /applications/[id]/interview-prep |
| **FORM INTELLIGENCE** | | | | |
| 62 | Application Form entity | ❌ MISSING | ❌ | No existe en ningún archivo |
| 63 | Form discovery (browser) | ❌ MISSING | ❌ | |
| 64 | Field semantic classification | ❌ MISSING | ❌ | |
| 65 | Candidate data → Field mapping | ❌ MISSING | ❌ | |
| 66 | Browser automation adapter | ❌ MISSING | ❌ | Playwright no configurado para uso |
| 67 | Human-in-the-loop form fields | ❌ MISSING | ❌ | |
| 68 | Form fill + validation | ❌ MISSING | ❌ | |
| **SUBMISSION** | | | | |
| 69 | Submission entity | ❌ MISSING | ❌ | |
| 70 | Submit action | ❌ MISSING | ❌ | |
| 71 | Confirmation capture | ❌ MISSING | ❌ | |
| 72 | SUBMITTED / UNCONFIRMED states | ❌ MISSING | ❌ | |
| **DISCOVERY / RECOMMENDATIONS** | | | | |
| 73 | Job recommendations (backend) | ✅ IMPLEMENTED | ✅ | keyword scoring + Remotive |
| 74 | Job recommendations (frontend) | ✅ IMPLEMENTED | ✅ | /recommendations |
| 75 | Recommendation 2.0 (Job Fit + Career Fit + Freshness) | ❌ MISSING | ❌ | Solo keyword score simple |
| 76 | Analytics funnel dashboard | ✅ IMPLEMENTED | ✅ | /analytics con KPIs y funnel |
| 77 | Outcome analytics breakdown | ⚠️ PARTIAL | ✅ | Funnel básico, sin breakdown por role/company |
| **SECURITY** | | | | |
| 78 | Auth JWT + refresh tokens | ✅ IMPLEMENTED | ✅ | |
| 79 | Password strength validation | ✅ IMPLEMENTED | ✅ | 8+ chars, upper, lower, digit |
| 80 | Security headers middleware | ✅ IMPLEMENTED | ✅ | CSP, X-Frame, HSTS |
| 81 | Rate limiting en /auth/* | ❌ MISSING | ❌ | Sin SlowAPI ni similar |
| 82 | Ownership checks (entidades) | ✅ IMPLEMENTED | ✅ | candidate_id en todas las queries |
| 83 | MIME validation (uploads) | ⚠️ PARTIAL | ❌ | Acepta content_type "application/pdf", sin magic bytes |
| 84 | SSRF protection (URL fetching) | ❌ MISSING | ❌ | source_url sin validación de private IPs |
| 85 | Prompt injection tests | ❌ MISSING | ❌ | No se testea contenido adversarial en JDs |
| 86 | Account deletion (GDPR) | ❌ MISSING | ❌ | |
| **INFRASTRUCTURE** | | | | |
| 87 | LLMProvider centralizado | ✅ IMPLEMENTED | ✅ | provider.py con generate/structured_output/stream |
| 88 | Cost tracking | ✅ IMPLEMENTED | ✅ | cost_tracker.py |
| 89 | Model routing (economy vs capable) | ❌ MISSING | ❌ | Un único modelo para todo |
| 90 | Prompt versioning | ❌ MISSING | ❌ | Prompts hardcodeados en agentes |
| 91 | Request ID / correlation ID | ✅ IMPLEMENTED | ✅ | middleware en main.py |
| 92 | Structured logging (structlog) | ✅ IMPLEMENTED | ✅ | get_logger con campos estructurados |
| 93 | CI/CD pipeline | ✅ IMPLEMENTED | ✅ | GitHub Actions: lint, typecheck, pytest, tsc |
| 94 | Alembic migrations (001–006) | ✅ IMPLEMENTED | ✅ | 006 pendiente en prod |
| 95 | RAG / pgvector | ❌ MISSING | ❌ | Synonym expansion en Python puro (MVP OK) |
| 96 | Caching (JD parsing, embeddings) | ❌ MISSING | ❌ | Sin Redis ni cache |
| **FRONTEND** | | | | |
| 97 | Landing page | ✅ IMPLEMENTED | ✅ | |
| 98 | Auth (login/register/onboarding) | ✅ IMPLEMENTED | ✅ | Wizard 5 pasos |
| 99 | Dashboard | ✅ IMPLEMENTED | ✅ | Lista trabajos + nav |
| 100 | Profile page (health + sources) | ✅ IMPLEMENTED | ✅ | health score, tips, fuentes |
| 101 | Job detail + match + outcome | ✅ IMPLEMENTED | ✅ | job/[id] con outcome feedback |
| 102 | Application workspace | ✅ IMPLEMENTED | ✅ | /applications/[id] completo |
| 103 | Interview prep page | ✅ IMPLEMENTED | ✅ | |
| 104 | Analytics dashboard | ✅ IMPLEMENTED | ✅ | |
| 105 | Recommendations page | ✅ IMPLEMENTED | ✅ | |
| 106 | Loading / empty / error states | ⚠️ PARTIAL | ❌ | Cubierto en mayoría, no consistente en todas |
| 107 | Responsive (mobile) | ⚠️ PARTIAL | ❌ | Diseño usa max-w-5xl, mobile no optimizado |
| 108 | Accessibility (a11y) | ❌ MISSING | ❌ | Sin aria-labels, focus states, screen reader |
| **TESTING** | | | | |
| 109 | Unit tests (90 pasando) | ✅ IMPLEMENTED | ✅ | |
| 110 | Integration tests | ⚠️ PARTIAL | ✅ | httpx async client, SQLite in-memory |
| 111 | E2E tests (Playwright) | ❌ MISSING | ❌ | |
| 112 | AI evaluation tests | ❌ MISSING | ❌ | Todos los LLM calls mockeados |
| 113 | Real AI smoke tests | ❌ MISSING | ❌ | |
| 114 | Prompt injection tests | ❌ MISSING | ❌ | |

---

## Deuda técnica identificada

| Ítem | Severidad | Archivo |
|------|-----------|---------|
| Sin rate limiting en /auth/* | 🔴 CRÍTICO | main.py + auth.py |
| SSRF: source_url sin validación | 🔴 CRÍTICO | candidates.py |
| Sin account deletion | 🔴 ALTO | candidates.py / users |
| MIME validation incompleta (no magic bytes) | 🟡 MEDIO | candidates.py |
| Prompts hardcodeados sin versión | 🟡 MEDIO | todos los agentes |
| Refresh token en localStorage (no httpOnly) | 🟡 MEDIO | auth.tsx |
| Un solo modelo para todo (no routing) | 🟡 MEDIO | todos los agentes |
| Conflicts en JSON sin UI | 🟡 MEDIO | profile_agent.py |
| Career Fit inexistente | 🟡 MEDIO | engine.py + match.py |
| Outcome no retroalimenta matching | 🟡 MEDIO | engine.py |

---

## Capacidades clave faltantes por prioridad P0

### P0.1 — Rate Limiting (Seguridad crítica)
Sin este fix, los endpoints `/auth/register` y `/auth/login` son vulnerables a brute force.

**Archivos a modificar:**
- `backend/requirements.txt` — agregar slowapi
- `backend/app/main.py` — configurar Limiter
- `backend/app/api/routes/auth.py` — decorar register y login
- `backend/tests/test_auth.py` — tests de rate limiting

### P0.2 — Matching 2.0: Hard Constraints + Career Fit
El matching actual puede recomendar trabajos que el candidato no puede aceptar legalmente o por seniority.

**Archivos a modificar:**
- `backend/app/services/matching/engine.py` — Layer 1 constraints + career_fit_score
- `backend/app/db/models/candidate.py` — campos work_authorization, availability
- `backend/app/schemas/candidate.py`
- `backend/alembic/versions/007_candidate_fields.py`
- `backend/app/schemas/match.py` — career_fit_score en respuesta
- `backend/app/db/models/match.py` — campo career_fit_score
- `backend/tests/test_match.py` — tests hard constraints

### P0.3 — Application Decision Engine
Reemplazar el `recommendation` del LLM por una decisión estructurada con explicación verificable.

**Archivos a modificar:**
- `backend/app/services/agents/application_agent.py`
- `backend/app/api/routes/match.py`
- `frontend/src/app/jobs/[id]/page.tsx`

---

## Riesgos críticos

| Riesgo | Impacto | Mitigación |
|--------|---------|-----------|
| Sin rate limiting — brute force en auth | Alto | Implementar SlowAPI |
| SSRF en source_url | Alto | Validar URLs privadas |
| Sin account deletion — violación GDPR | Alto | Implementar DELETE /candidates/me |
| Form Intelligence requiere browser infra | Muy alto | Playwright aislado, separar lógica de negocio |
| LLM hallucination en CV | Medio | Claim validator + validación de evidencia |
