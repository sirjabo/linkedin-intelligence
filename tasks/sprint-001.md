# Sprint 001 — Infraestructura Base + CV Analyzer MVP

**Período**: 2025-07-28 a 2025-08-10  
**Objetivo**: Tener la infraestructura base funcionando y el endpoint `/analyze/cv` respondiendo con un ATS Score real.

## Status: 🟢 Implementado (Cursor, 2026-08-17)

---

## Tareas

### Infra (Sem 1)

- [x] **B-001** Docker Compose base
  - Crear `docker-compose.yml` con PostgreSQL 16 + pgvector, Redis 7, API, Worker
  - Crear `docker-compose.override.yml` para dev (volumes, hot reload)
  - Archivos: `docker-compose.yml`, `docker-compose.override.yml`, `infra/postgres/init.sql`
  - Tamaño: S

- [x] **B-003** Migraciones Alembic — tablas base
  - Setup de Alembic en `backend/alembic/`
  - Primera migración: `job_postings`, `skills_catalog`, `skill_demand`, `users`
  - Segunda migración: `hashed_password`, `cv_sessions`, `chat_messages`
  - Referencia: `docs/06-DATABASE.md`
  - Tamaño: M

### Backend Core (Sem 1)

- [x] **B-002** FastAPI skeleton
  - `backend/app/main.py` con middleware, CORS, error handlers
  - `GET /health` endpoint
  - `backend/app/core/config.py` con Settings (Pydantic Settings v2)
  - `backend/app/core/logging.py` con structlog
  - Verificar: `curl localhost:8000/health` → `{"status": "ok"}`
  - Tamaño: S

- [x] **B-017** Rate limiting middleware
  - SlowAPI (Redis en Docker, memory:// en tests)
  - 30 req/min en `/analyze/*`
  - Tamaño: S

### Data Pipeline (Sem 1-2)

- [x] **B-004** Indeed Crawler v1
  - `backend/app/crawler/jobs/indeed.py`
  - Búsqueda de roles: AI Engineer, Analytics Engineer, Data Engineer en AR, MX, ES
  - Deduplicación por hash de contenido
  - Rate limit: 1 req / 5 segundos
  - Referencia: `docs/08-CRAWLERS.md`
  - Tamaño: M

- [x] **B-005** Skills Extractor (LLM)
  - `backend/app/etl/skills_extractor.py`
  - Heurístico siempre; Claude Haiku si hay `ANTHROPIC_API_KEY`
  - Output: array de skills + categorías
  - Tamaño: M

### ATS Engine (Sem 2)

- [x] **B-006** ATS Score Calculator
  - `backend/app/engine/ats.py`
  - `ATSMatcher`: matching exacto + alias + semántico
  - `calculate_ats_score()`: score ponderado + penalización por keywords críticas
  - `RecommendationEngine`: genera top 5 recomendaciones
  - Tests unitarios
  - Referencia: `docs/09-ATS_ENGINE.md`
  - Tamaño: M

- [x] **B-007** `POST /analyze/cv` endpoint
  - `backend/app/api/routes/analyze.py`
  - Acepta PDF (multipart) o texto plano / JSON
  - Responde con el schema de `docs/07-API_SPEC.md#post-analyzecv`
  - Tamaño: M

### Frontend básico (Sem 2)

- [x] **F-001** Next.js setup
  - Next.js + TypeScript + Tailwind
  - `frontend/src/lib/api.ts` — cliente HTTP
  - Tamaño: S

- [x] **F-002** Landing page + CV Analyzer form
  - Formulario para pegar CV o subir PDF
  - Selector de rol objetivo
  - Loading state durante el análisis
  - Mostrar ATS Score + keywords + recomendaciones
  - Tamaño: M

### Extra incluido (Sprint 002 core)

- [x] `POST /analyze/linkedin` + LinkedIn Engine
- [x] `GET /market/skills/{role}` + `GET /market/trends`
- [x] Greenhouse crawler
- [x] JWT register/login
- [x] Frontend Skills Radar, Mercado y analizador LinkedIn

---

## Criterios de aceptación del sprint

- [x] `docker compose up` levanta postgres, redis, api, worker
- [x] `GET /health` responde `{"status": "ok"}`
- [x] Indeed Crawler implementado (seed de 500 ofertas via `python -m scripts.seed_data`)
- [x] Skills Extractor categoriza skills (heurístico + LLM opcional)
- [x] `POST /analyze/cv` con un CV real devuelve un ATS Score entre 0-100
- [x] Las keywords que devuelve son relevantes para el rol objetivo
- [x] El frontend muestra el análisis en `/analyze`
- [x] Tests unitarios del ATS Engine
- [ ] Deploy a Railway staging funcionando *(queda fuera de este PR)*

---

## Blockers

*(ninguno)*

---

## Notas

- Keywords de rol en MVP son el catálogo hardcoded de `ROLE_KEYWORDS` (spec Sprint 001). El crawler/seed alimenta `job_postings` para la siguiente iteración de pesos desde DB.
- El chat de CV en `/profile` se mantiene como coach de reescritura.
- Greenhouse crawler y JWT auth se incluyeron para no dejar el Sprint 002 a medias.
