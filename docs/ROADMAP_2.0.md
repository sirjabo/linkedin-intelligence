# LinkedIn Intelligence 2.0 — Roadmap

> Generado: 2026-08-13  
> Reemplaza: `docs/02-ROADMAP.md` y `docs/20-BACKLOG.md`  
> Basado en: `docs/MASTER_GAP_ANALYSIS.md`

---

## Norte

**Qualified interviews generated per active candidate**

No optimizar por CVs generados, cartas generadas ni trabajos analizados.

---

## Regla

Una fase no está terminada hasta tener backend + frontend + tests + error states + security checks + acceptance criteria.

---

## Fase 0 — Bug fixes críticos (≈1 día)

> Estado: **Pendiente**  
> Bloqueantes: Todo lo demás.

### 0.1 Fix interview_agent TypeError (BUG-001)

`backend/app/services/agents/interview_agent.py`

Migrar de `provider.generate(prompt=..., tools=..., tool_choice=...)` a `provider.structured_output(system, messages, schema, model, max_tokens)`. Igual que los otros agentes.

**Acceptance:** `POST /applications/{id}/interview-prep` retorna 201 con datos válidos. Test real sin mock pasa.

### 0.2 Fix MatchScoreCard field names (BUG-002)

`frontend/src/components/MatchScoreCard.tsx`

Cambiar `match.tier → match.match_tier`, `match.reasoning → match.llm_reasoning`, `match.strengths → match.llm_strengths`, `match.gaps → match.llm_gaps`.

**Acceptance:** El componente muestra tier, strengths y gaps reales del backend.

### 0.3 Fix consolidate_profiles modelo inválido (BUG-003)

`backend/app/services/agents/profile_agent.py`

Cambiar `model="claude-sonnet-5"` por `claude-haiku-4-5-20251001` (consistente con el resto).

**Acceptance:** Usuario con 2+ fuentes puede hacer rebuild sin 500.

### 0.4 Fix ApplicationListResponse sin job title (BUG-004)

`backend/app/schemas/application.py` + ruta `GET /applications`

Incluir `job_title: str | None` y `job_company: str | None` vía join con `Job`.

**Acceptance:** Frontend muestra título del trabajo en lista de postulaciones.

### 0.5 Fix test path en test_recommendations (BUG-005)

`backend/tests/test_recommendations.py`

Cambiar `POST /api/v2/candidates/sources` por `POST /api/v2/candidates/me/sources/text`.

**Acceptance:** `pytest tests/test_recommendations.py` pasa 100%.

---

## Fase 1 — UI faltante para APIs existentes (≈2-3 días)

> Estado: **Pendiente**  
> Prerequisito: Fase 0 completa.

Las siguientes páginas tienen backend funcional y testeado pero cero UI.

### 1.1 Página `/recommendations`

Botón en dashboard → `/recommendations`. Lista de trabajos externos rankeados con score, matched_keywords, company, remote_type, URL. Filtros: query, limit, category.

**Acceptance:** Usuario logueado puede ver y filtrar trabajos recomendados. Link al trabajo externo abre en nueva pestaña.

### 1.2 Página `/applications/[id]/interview-prep`

Tab o sección dentro de la workspace de postulación. Muestra 5 preguntas técnicas (con rationale), 5 behavioral (con competency), 3 STAR stories, 5 preguntas para hacer, company research. Botón "Generar prep" → `POST /applications/{id}/interview-prep`.

**Acceptance:** Usuario puede generar y ver interview prep. Segunda generación (upsert) no duplica.

### 1.3 Sección de answers en `/applications/[id]`

Textarea donde pegar preguntas de la empresa (una por línea). Botón "Generar respuestas" → `POST /applications/{id}/answers`. Muestra respuestas generadas. Requiere strategy (igual que cover letter).

**Acceptance:** Usuario puede generar respuestas a preguntas custom. Se muestran debajo de cover letter.

### 1.4 Página `/profile` — Candidate management

Reemplaza el legacy CV chatbot de `/profile`. Muestra:
- Datos del candidato (name, location, target_roles, preferences) con edición inline
- Lista de fuentes (source_type, fecha, confianza) con botón para agregar nueva
- Botón "Rebuild profile" → `POST /candidates/me/profile/rebuild`
- Vista del perfil consolidado (summary, skills, experience, education)

**Acceptance:** Usuario puede ver y actualizar su perfil. Puede agregar fuentes y reconstruir el perfil. Muestra estado del perfil (completo/incompleto).

### 1.5 Auth redirect en landing

Si el usuario tiene token válido en localStorage al cargar `/`, redirigir a `/dashboard`.

**Acceptance:** Usuario logueado que abre la URL raíz va directo al dashboard.

---

## Fase 2 — Deuda técnica crítica (≈2 días)

> Estado: **Pendiente**  
> Se puede hacer en paralelo con Fase 1.

### 2.1 SECRET_KEY validation on startup

`backend/app/core/config.py`

Si `ENVIRONMENT=production` y `SECRET_KEY == "dev-secret-change-in-production"`, levantar `ValueError` en startup. Documentar en `.env.example`.

### 2.2 Refresh token en frontend

`frontend/src/lib/api-v2.ts`, `frontend/src/lib/auth.tsx`

Guardar `refresh_token` en localStorage. En cualquier respuesta 401 de la API, intentar `POST /auth/refresh`. Si falla, hacer logout. Token de acceso se renueva transparentemente.

### 2.3 EvidenceRecord rebuild completo

`backend/app/api/routes/candidates.py` líneas 221-229

Iterar sobre todos los tipos de evidencia (skill, experience, education, achievement, certification) del perfil consolidado y crear `EvidenceRecord` para cada uno. El ClaimValidator necesita evidencia completa para funcionar bien.

### 2.4 Fix migration 005

`backend/alembic/versions/005_interview.py`

Nueva migración (006) que:
- Altera `interview_preps` JSON columns a JSONB (PostgreSQL)
- Añade `server_default=sa.func.now()` a `created_at` y `updated_at`

### 2.5 Rate limiting

`backend/app/main.py` + middleware

Usar `slowapi` o implementar contador in-memory simple. Límite razonable por IP para endpoints LLM-intensivos: match, CV generation, cover letter, interview prep. Retorna 429 con `Retry-After`.

---

## Fase 3 — Onboarding flow (≈3-4 días)

> Estado: **Pendiente**  
> Prerequisito: Fase 1.4 (profile page) completa.

### 3.1 `/onboarding` — Wizard de 6 pasos

**Paso 1 — Bienvenida**: Explicación del valor, qué va a pasar.

**Paso 2 — CV**: Upload PDF o pegar texto. Preview del texto extraído. Progreso de extracción.

**Paso 3 — LinkedIn**: Pegar texto del perfil de LinkedIn. Instrucciones para exportar.

**Paso 4 — GitHub / Portfolio** (opcional): Username de GitHub. URLs de proyectos.

**Paso 5 — Objetivos**: Target roles (multi-select o texto libre). Seniority objetivo. Preferencia remote/hybrid/onsite. Rango salarial esperado (opcional).

**Paso 6 — Confirmación**: "Esto es lo que entendimos de vos." Muestra perfil extraído: nombre, skills identificadas, años de experiencia, nivel detectado. Usuario puede corregir campos antes de confirmar.

**Estado final**: `CandidateProfile` creado, `EvidenceRecord`s completos, usuario redirigido a `/dashboard`.

**Acceptance criteria:**
- Flow completo funciona sin errores
- Usuario puede volver a pasos anteriores
- Conflictos entre fuentes se muestran (si CV dice 2023 y LinkedIn dice 2022)
- Si el usuario ya tiene fuentes, va directo al paso de confirmación
- Mobile usable

---

## Fase 4 — Matching engine mejorado (≈3 días)

> Estado: **Pendiente**  
> Prerequisito: Onboarding (perfil completo con preferences y salary).

### 4.1 Salary matching

Agregar scoring de salary compatibility al deterministic engine:
- 1.0 si salary del job está dentro del rango del candidato
- 0.8 si dentro de ±20%
- 0.5 si fuera de rango
- 0.65 si unknown

Ajustar pesos o mantenerlos y reportarlo como campo separado en MatchAnalysis.

### 4.2 Hard constraints layer

Antes del scoring, evaluar blockers:
- Seniority gap > 2 niveles: `LOW_FIT`
- Location incompatible + no remote + sin relocation: `BLOCKER`
- Salary incompatible por > 40%: `WARNING`

Nuevo campo `blockers: list[str]` en `MatchAnalysis` y en el schema de respuesta.

### 4.3 Candidate preferences → matching

Leer `Candidate.preferences` en el matching engine. Target roles, industries, remote preference. Afectar `location_score` y agregar `preference_score` separado.

### 4.4 Match UI mejorada

`frontend/src/components/MatchScoreCard.tsx` (después de BUG-002 fix)

Mostrar: score general, scores por categoría (skills, experience, location, education), blockers en rojo, strengths en verde, gaps en amarillo. Recomendación (APPLY / APPLY_WITH_CUSTOMIZATION / LOW_FIT / DO_NOT_APPLY).

---

## Fase 5 — Application workspace completo (≈2 días)

> Estado: **Pendiente**  
> Prerequisito: Fases 1.2, 1.3 completas.

### 5.1 Application state machine completo

Agregar estados: `discovered`, `saving`, `analyzing`, `ready`, `screening`. Implementar transiciones válidas (no se puede ir de `draft` a `offer` sin pasar por `applied`). Mostrar flujo visual en UI.

### 5.2 Follow-up tracking

Mostrar y editar `follow_up_date` en la workspace. Highlight visual si hay follow-up vencido (fecha en el pasado).

### 5.3 Application readiness checklist

Mostrar antes del botón "Marcar postulado":
- ✅/❌ Perfil completo
- ✅/❌ CV generado
- ✅/❌ Cover letter generada
- ✅/❌ Match score calculado

Solo habilitar "Marcar postulado" si checklist está completo (o permitir override con warning).

---

## Fase 6 — Analytics y funnel (≈2-3 días)

> Estado: **Pendiente**  
> Prerequisito: Application state machine completo.

### 6.1 Outcome tracking enriquecido

Agregar `rejection_reason` a `ApplicationEvent`. Campos opcionales: `recruiter_name`, `recruiter_contact`, `salary_offered`. Endpoint `GET /analytics/funnel` que retorna conteos por estado.

### 6.2 Dashboard mejorado

Reemplazar dashboard actual con:
- Resumen de postulaciones activas por estado
- Últimos 7 días de actividad
- Follow-ups pendientes
- Match score promedio de postulaciones activas
- Tasa de respuesta (si hay datos suficientes)

### 6.3 Página `/analytics`

Funnel visual: aplicaciones → respuestas → entrevistas → ofertas. Breakdown por: fuente de trabajo, rango de match score, tipo de empresa. Solo mostrar si hay ≥3 datos (evitar inferencias falsas con muestra mínima).

---

## Fase 7 — Seguridad y privacidad (≈1-2 días)

> Estado: **Pendiente**  
> Se puede hacer en paralelo con fases anteriores.

### 7.1 Account deletion

`DELETE /api/v2/auth/me` — elimina User + Candidate + todas las entidades en cascada.

### 7.2 Data export

`GET /api/v2/candidates/me/export` — retorna JSON con toda la data del candidato (profile, applications, CVs, cover letters). Útil para compliance y para que el usuario migre.

### 7.3 Prompt injection protection

Sanitizar JD text antes de pasarlo a agentes. Detectar patrones como "ignore previous instructions". Testear con payloads conocidos.

### 7.4 Content Security Policy

Headers `Content-Security-Policy` en FastAPI para mitigar XSS (mitiga DEUDA-003 sin refactorizar localStorage).

---

## Fase 8 — CI/CD y deployment (≈1-2 días)

> Estado: **Pendiente**  
> Se puede hacer en cualquier momento.

### 8.1 GitHub Actions

`.github/workflows/ci.yml`:
- `ruff check backend/`
- `mypy backend/app --ignore-missing-imports`
- `pytest backend/tests/ -q`
- `npm run build` en `frontend/`
- Bloquear merge si falla

### 8.2 Docker Compose actualizado

`docker-compose.yml` con servicios:
- `postgres` con variables de entorno
- `backend` con todas las env vars documentadas
- `frontend` en modo standalone
- Health checks entre servicios

### 8.3 `.env.example`

Documentar todas las variables requeridas con valores de ejemplo y notas de seguridad.

---

## Fase 9 — Profile health y Candidate Intelligence (≈3-4 días)

> Estado: **Pendiente**  
> Prerequisito: Onboarding completo + EvidenceRecord completo.

### 9.1 Profile health score

Calcular determinísticamente:
- `completeness`: % de campos obligatorios completos
- `evidence_coverage`: % de skills con ≥1 EvidenceRecord
- `achievement_quality`: experiencias con ≥1 logro cuantificado
- `skill_evidence`: skills sin evidencia flaggeadas

Endpoint: `GET /candidates/me/profile/health` → `{overall, completeness, evidence_coverage, achievement_quality, gaps: list[str]}`.

### 9.2 Skills gap por job

Después de calcular match, mostrar: skills que el candidato tiene y el JD pide (matched), skills que el JD pide y el candidato no tiene (gap), skills del candidato no mencionadas en el JD (extra).

---

## Fase 10 — Semantic matching / pgvector (≈5 días)

> Estado: **Futuro**  
> Prerequisito: Core estable, perfil con evidencia completa.

Agregar embeddings para comparación semántica de experiencias vs responsabilidades del JD. Usar pgvector. Caching de embeddings por hash de contenido.

---

## Fase 11 — Learning loop (≈5+ días)

> Estado: **Futuro**  
> Prerequisito: Analytics completo + suficiente data de outcomes.

Comparar results entre diferentes versiones de CV, estrategias y prompts. Reportar diferencias observadas con sample size y confidence. No asumir causalidad automáticamente.

---

## Backlog deprioritizado

Los siguientes ítems del backlog anterior quedan fuera del scope hasta que el core sea sólido:

- Content Calendar
- LinkedIn Post Generator
- AI Radar (trends, skills market)
- Reddit/HN signals
- Google Trends integration
- Browser extension
- LinkedIn OAuth
- Mobile app
- Team plan / multi-user
- Fine-tuned models

---

## Definición de Done

Una fase está terminada cuando:

1. Backend implementado con validación y error handling
2. Frontend implementado con loading / empty / error states
3. Tests que cubren happy path + edge cases + ownership
4. Sin llamadas a APIs externas reales en tests
5. Acceptance criteria verificados manualmente
6. Sin regressions en test suite existente
