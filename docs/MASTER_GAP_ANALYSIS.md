# LinkedIn Intelligence — Master Gap Analysis

> Generado: 2026-08-13  
> Base: auditoría de código real (no documentación)  
> Branch: `claude/new-session-ce0sct`

---

## Metodología

Este documento analiza el código fuente real, no la documentación. Cada ítem fue verificado leyendo los archivos en `backend/` y `frontend/`. Las bugs reportadas son defectos confirmados, no hipotéticos.

---

## Tabla de capacidades

| Capacidad | Estado | Tests | Prod-ready | Notas |
|-----------|--------|-------|-----------|-------|
| Auth register/login/refresh | ✅ Implementado | ✅ 9 tests | ⚠️ Parcial | SECRET_KEY default inseguro |
| JWT manual (stdlib) | ✅ Implementado | ✅ 5 tests | ✅ | HMAC-SHA256, sin cffi |
| Password hash (pbkdf2) | ✅ Implementado | ✅ | ✅ | |
| Candidate model básico | ✅ Implementado | ✅ 9 tests | ✅ | |
| CandidateSource (text) | ✅ Implementado | ✅ | ✅ | |
| CandidateSource (PDF upload) | ✅ Implementado | ❌ Sin tests | ❌ | PDF upload no testeado |
| Profile extraction (LLM) | ✅ Implementado | ✅ mock | ⚠️ | Llamada real sin tests |
| Profile consolidation (multi-source) | ❌ Bug crítico | ❌ | ❌ | Usa modelo inválido `"claude-sonnet-5"` |
| EvidenceRecord rebuild | ⚠️ Parcial | ⚠️ | ❌ | Solo guarda `evidence_type="skill"`, resto se descarta |
| ProfileConflict detection | ✅ Modelo existe | ❌ | ❌ | Campo `conflicts` en JSON, nunca expuesto al usuario |
| Job create/parse | ✅ Implementado | ✅ 11 tests | ✅ | |
| Job list/get | ✅ Implementado | ✅ | ✅ | |
| Job analyze (sin guardar) | ✅ Implementado | ✅ | ✅ | |
| Matching engine (determinístico) | ✅ Implementado | ✅ 5 unit | ✅ | |
| Matching engine (LLM reasoning) | ✅ Implementado | ✅ mock | ⚠️ | |
| MatchScoreCard (frontend) | ❌ Bug crítico | ❌ | ❌ | Lee campos incorrectos, renderiza vacío |
| Application CRUD | ✅ Implementado | ✅ 17 tests | ✅ | |
| Application state machine | ⚠️ Parcial | ⚠️ | ⚠️ | 7 estados, falta `discovered`/`saving`/`analyzing`/`ready`/`screening` |
| CV generation (LLM) | ✅ Implementado | ✅ mock | ⚠️ | |
| Strategy caching | ✅ Implementado | ✅ | ✅ | |
| Claim validation (determinístico) | ✅ Implementado | ✅ 3 tests | ⚠️ | Solo regex + token overlap, no semántico |
| Cover letter generation | ✅ Implementado | ✅ mock | ⚠️ | |
| Application answers | ✅ Backend | ❌ Frontend | ❌ | Endpoint existe, UI ausente |
| Interview prep (backend) | ❌ Bug crítico | ✅ mock | ❌ | TypeError en runtime — provider.generate() args incorrectos |
| Interview prep (frontend) | ❌ Faltante | ❌ | ❌ | Ninguna UI |
| Job discovery (Remotive) | ✅ Implementado | ✅ 11 tests | ✅ | |
| Recommendations (backend) | ✅ Implementado | ✅ | ✅ | Keyword-overlap scoring |
| Recommendations (frontend) | ❌ Faltante | ❌ | ❌ | Ninguna UI, ningún link al dashboard |
| Candidate profile UI | ❌ Faltante | ❌ | ❌ | Todo el surface `/candidates/me/*` no tiene UI |
| Candidate onboarding flow | ❌ Faltante | ❌ | ❌ | |
| Application list con job title | ❌ Bug | ❌ | ❌ | Lista muestra UUID parcial, no título del trabajo |
| Follow-up date UI | ❌ Parcial | ❌ | ❌ | Campo en DB y PATCH, sin UI |
| Analytics / funnel | ❌ Faltante | ❌ | ❌ | |
| Outcome tracking | ⚠️ Parcial | ❌ | ❌ | ApplicationEvent existe, sin análisis |
| Learning loop | ❌ Faltante | ❌ | ❌ | |
| CI/CD | ❌ Faltante | ❌ | ❌ | Sin GitHub Actions |
| Docker Compose (v2) | ⚠️ Parcial | ❌ | ❌ | docker-compose.yml existe pero no refleja v2 |
| Refresh token (frontend) | ❌ Bug | ❌ | ❌ | api-v2.ts no maneja refresh, tokens expiran en 60min |
| v1 CVSession auth | ❌ Sin auth | ❌ | ❌ | Acceso sin autenticación |
| E2E golden journey | ❌ Faltante | ❌ | ❌ | |

---

## Bugs críticos (producción rota)

### BUG-001 — `interview_agent.generate_interview_prep()` TypeError

**Severidad:** P0 — runtime crash  
**Archivo:** `backend/app/services/agents/interview_agent.py`  
**Problema:**

```python
# Lo que llama:
result = await provider.generate(prompt=prompt, tools=[_TOOL_SCHEMA], tool_choice=...)

# Firma real de AnthropicProvider.generate():
async def generate(self, system: str, messages: list, model: str, max_tokens: int) -> str
```

Los kwargs `prompt=`, `tools=`, `tool_choice=` no existen. Cada request a `POST /applications/{id}/interview-prep` retorna HTTP 500.  
**Fix:** Migrar `interview_agent.py` a `provider.structured_output()` como los demás agentes.

---

### BUG-002 — `MatchScoreCard` renderiza vacío

**Severidad:** P0 — feature completamente rota  
**Archivo:** `frontend/src/components/MatchScoreCard.tsx`  
**Problema:**

```typescript
// Lo que lee el componente:
match.tier          // undefined
match.reasoning     // undefined
match.strengths     // undefined
match.gaps          // undefined

// Lo que devuelve el backend:
match.match_tier    // correcto
match.llm_reasoning // correcto
match.llm_strengths // correcto
match.llm_gaps      // correcto
```

El match score siempre aparece vacío aunque la API responda correctamente.  
**Fix:** Corregir los nombres de campo en `MatchScoreCard.tsx`.

---

### BUG-003 — `consolidate_profiles` usa modelo inválido

**Severidad:** P0 — crash en consolidación multi-fuente  
**Archivo:** `backend/app/services/agents/profile_agent.py`  
**Problema:**

```python
model="claude-sonnet-5"  # No existe
```

Modelo correcto: `claude-sonnet-4-5` o `claude-haiku-4-5-20251001`. Todo usuario con más de una fuente (CV + LinkedIn) ve un 500 al hacer rebuild del perfil.  
**Fix:** Usar un modelo válido del LLMProvider.

---

### BUG-004 — `ApplicationListResponse` no incluye job title

**Severidad:** P1 — UX rota  
**Archivos:** `backend/app/schemas/application.py`, `frontend/src/app/applications/page.tsx`  
**Problema:** La lista de postulaciones muestra `"Job ID: a3f4c9d1…"`. El usuario no puede identificar a qué trabajo corresponde cada postulación.  
**Fix:** Incluir `job_title` y `job_company` en `ApplicationListResponse` vía join.

---

### BUG-005 — `test_recommendations_with_profile` path incorrecto

**Severidad:** P1 — test roto  
**Archivo:** `backend/tests/test_recommendations.py`  
**Problema:** Llama `POST /api/v2/candidates/sources` (404). Path correcto: `/api/v2/candidates/me/sources/text`.  
**Fix:** Corregir path en el test.

---

## Deuda técnica

### DEUDA-001 — EvidenceRecord rebuild descarta datos

**Archivo:** `backend/app/api/routes/candidates.py` líneas 221-229  
**Problema:** Solo crea `EvidenceRecord` para `evidence_type="skill"`. Evidencias de experience, education, achievements y certifications se pierden en cada rebuild. El ClaimValidator pierde cobertura.

---

### DEUDA-002 — Migration 005 inconsistente con 001-004

**Archivo:** `backend/alembic/versions/005_interview.py`  
**Problemas:**
- Usa `sa.JSON()` en vez de `sa.JSONB()` (PostgreSQL pierde indexing)
- `created_at` y `updated_at` sin `server_default=sa.func.now()` (NULLs en prod si ORM no los setea)

---

### DEUDA-003 — JWT en localStorage (XSS)

**Archivo:** `frontend/src/lib/auth.tsx`  
**Problema:** `localStorage.setItem("li_token", token)`. Cualquier script inyectado puede exfiltrar el token. El estándar es `httpOnly cookie`.  
**Mitigación corto plazo:** Agregar Content-Security-Policy headers.

---

### DEUDA-004 — SECRET_KEY default inseguro

**Archivo:** `backend/app/core/config.py`  
**Problema:** `SECRET_KEY = "dev-secret-change-in-production"`. Si no se sobreescribe en producción, todos los JWTs son forgeables con clave conocida.  
**Fix:** Arrancar con error explícito si `ENVIRONMENT=production` y `SECRET_KEY` es el default.

---

### DEUDA-005 — v1 CVSession sin autenticación

**Archivos:** `backend/app/api/routes/cv.py`, `backend/app/api/routes/chat.py`  
**Problema:** Cualquier persona con el UUID de sesión puede leer o modificar cualquier CVSession. Sin `user_id`, imposible retrofittear auth sin migración.  
**Decisión requerida:** Deprecar v1 o migrar a auth.

---

### DEUDA-006 — No hay refresh token en frontend

**Archivo:** `frontend/src/lib/api-v2.ts`  
**Problema:** El `login()` guarda solo `access_token`. Expira en 60 minutos. Las llamadas subsiguientes fallan silenciosamente sin intentar refresh.

---

### DEUDA-007 — Config muerta

**Archivo:** `backend/app/core/config.py`  
**Problema:** `OPENAI_API_KEY` y `REDIS_URL` configurados pero nunca usados. Genera confusión sobre el stack real.

---

### DEUDA-008 — Campos de Job sin usar en matching

- `salary_min` / `salary_max`: extraídos, guardados, ignorados por matching engine
- `seniority_signal` en `JobRequirement`: extraído, guardado, ignorado
- `Candidate.preferences`: guardado como JSON, nunca leído por agentes ni engine

---

### DEUDA-009 — Candidate onboarding sin UI

Todo el surface `/api/v2/candidates/me/*` está implementado en backend (sources upload, text ingest, profile rebuild, evidence) pero no existe ninguna página en frontend que lo use.

---

## Estado de tests

| Suite | Tests | Mocks | Coverage real | Roto |
|-------|-------|-------|--------------|------|
| test_auth.py | 9 | Ninguno (no LLM) | Alta | No |
| test_candidates.py | 9 | profile_agent | Media | No |
| test_jobs.py | 11 | job_agent | Alta | No |
| test_match.py | 12 | match_agent | Alta | No |
| test_applications.py | 17 | application_agents | Alta | No |
| test_interview.py | 8 | interview_agent | Media | No (mock evade BUG-001) |
| test_recommendations.py | 11 | remotive | Alta | Sí (BUG-005) |
| test_security.py | 5 | Ninguno | Alta | No |
| **Total** | **82** | | | **1 roto** |

### Tests críticos faltantes

| Área | Por qué falta | Prioridad |
|------|--------------|-----------|
| PDF upload | Sin test de integración | P1 |
| interview_agent real (sin mock) | BUG-001 oculto por mock | P0 |
| MatchScoreCard frontend | BUG-002 no detectado | P1 |
| consolidate_profiles multi-source real | BUG-003 oculto por mock | P0 |
| Token refresh flow | Sin test E2E de expiración | P1 |
| Ownership checks exhaustivos | Parcial | P1 |
| ApplicationListResponse con job title | Campo ausente sin test | P1 |

---

## Funcionalidad faltante por área

### Backend — faltante

| Capacidad | Complejidad | Dependencias | Prioridad |
|-----------|------------|--------------|-----------|
| Candidate preferences aplicados a matching | Baja | Matching engine | P1 |
| Salary matching en engine | Media | Candidate model | P1 |
| Application state machine completo | Media | Application model | P2 |
| Follow-up reminders | Media | Infraestructura email | P3 |
| Funnel analytics por usuario | Media | Outcome tracking | P2 |
| Learning loop | Alta | Analytics + outcomes | P3 |
| pgvector / RAG para evidencias | Alta | Postgres + embeddings | P2 |
| Prompt versioning | Media | Agents | P2 |
| Cost tracking por llamada LLM | Baja | Provider | P2 |
| Account deletion + data export | Media | Privacy | P1 |
| Rate limiting | Media | Middleware | P1 |
| Prompt injection protection | Media | Agents + input validation | P1 |

### Frontend — faltante

| Página / Feature | Complejidad | Prioridad |
|-----------------|------------|-----------|
| `/recommendations` | Baja | P0 (API existe) |
| `/applications/[id]/interview-prep` | Baja | P0 (API existe) |
| Answers en `/applications/[id]` | Baja | P0 (API existe) |
| `/profile` (candidate management) | Media | P0 (API existe) |
| Auth redirect en landing page | Muy baja | P1 |
| Refresh token flow | Baja | P1 |
| Follow-up date UI | Baja | P2 |
| Onboarding flow `/onboarding` | Alta | P1 |
| Dashboard mejorado (stats) | Media | P2 |
| Job inbox con filtros | Media | P2 |
| Profile editor | Alta | P2 |
| Document review (compare versions) | Alta | P2 |
| Analytics dashboard | Alta | P3 |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| SECRET_KEY default en prod | Media | Crítico | Validar en startup |
| JWT localStorage exfiltrado | Media | Alto | CSP headers + migrar a cookies |
| v1 session data leak | Alta | Medio | Deprecar v1 |
| consolidate_profiles crash (BUG-003) | Alta | Alto | Fix urgente |
| Interview prep crash (BUG-001) | Alta | Alto | Fix urgente |
| LLM hallucination en CV generation | Media | Alto | Claim validator (parcial) |
| Token expiry sin refresh | Alta | Medio | Fix frontend |

---

## Prioridades de implementación

### P0 — Bugs que bloquean features existentes (antes de cualquier nueva feature)

1. BUG-001: Fix `interview_agent` TypeError
2. BUG-002: Fix `MatchScoreCard` field names
3. BUG-003: Fix `consolidate_profiles` model name
4. BUG-004: Add job title a `ApplicationListResponse`
5. BUG-005: Fix test path en `test_recommendations`

### P0 — UI faltante para APIs que ya existen

6. Página `/recommendations`
7. Página `/applications/[id]/interview-prep`
8. Sección de answers en `/applications/[id]`
9. Página `/profile` (candidate profile + sources)

### P1 — Deuda técnica crítica

10. DEUDA-004: SECRET_KEY validation on startup
11. DEUDA-006: Refresh token en frontend
12. DEUDA-001: EvidenceRecord rebuild completo
13. DEUDA-002: Migration 005 fixes

### P1 — Funcionalidad core faltante

14. Onboarding flow `/onboarding`
15. Candidate preferences → matching
16. Application state machine completo
17. Rate limiting
18. Account deletion / data export

### P2 — Mejoras de matching y personalización

19. Salary matching
20. Semantic matching (embeddings)
21. Funnel analytics
22. Cost tracking por LLM call
23. Profile health score

### P3 — Features diferenciadores

24. Learning loop
25. Interview simulator
26. pgvector / RAG
27. CI/CD (GitHub Actions)
28. Market intelligence

---

## Dependencias entre fases

```
BUG-001,2,3,4,5 (fixes)
    ↓
UI faltante P0 (recommendations, interview-prep, answers, profile)
    ↓
Onboarding flow (depende de profile UI)
    ↓
Candidate preferences → Matching (depende de onboarding completo)
    ↓
Funnel analytics (depende de outcome tracking mejorado)
    ↓
Learning loop (depende de analytics)
    ↓
Semantic matching / pgvector (infraestructura independiente)
```

---

## Complejidad estimada por área

| Área | Días estimados | Riesgo técnico |
|------|---------------|---------------|
| Bug fixes P0 (5 bugs) | 1 | Bajo |
| UI P0 faltante (4 páginas) | 2-3 | Bajo |
| Refresh token + SECRET_KEY | 0.5 | Bajo |
| EvidenceRecord rebuild completo | 1 | Bajo |
| Onboarding flow | 3-4 | Medio |
| Application state machine | 1 | Bajo |
| Salary matching | 1 | Bajo |
| Rate limiting | 1 | Bajo |
| Funnel analytics | 2 | Medio |
| Semantic matching | 3-5 | Alto |
| Learning loop | 5+ | Alto |
| CI/CD | 1-2 | Bajo |
