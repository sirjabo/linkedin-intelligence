# Sprint 001 — Infraestructura Base + CV Analyzer MVP

**Período**: 2025-07-28 a 2025-08-10  
**Objetivo**: Tener la infraestructura base funcionando y el endpoint `/analyze/cv` respondiendo con un ATS Score real.

## Status: 🟡 Listo para iniciar

---

## Tareas

### Infra (Sem 1)

- [ ] **B-001** Docker Compose base
  - Crear `docker-compose.yml` con PostgreSQL 16 + pgvector, Redis 7, API, Worker
  - Crear `docker-compose.override.yml` para dev (volumes, hot reload)
  - Verificar: `docker compose up -d && docker compose ps` → todos healthy
  - Archivos: `docker-compose.yml`, `docker-compose.override.yml`, `infra/postgres/init.sql`
  - Tamaño: S

- [ ] **B-003** Migraciones Alembic — tablas base
  - Setup de Alembic en `backend/alembic/`
  - Primera migración: `job_postings`, `skills_catalog`, `skill_demand`, `users`
  - Verificar: `alembic upgrade head` sin errores
  - Referencia: `docs/06-DATABASE.md`
  - Tamaño: M

### Backend Core (Sem 1)

- [ ] **B-002** FastAPI skeleton
  - `backend/app/main.py` con middleware, CORS, error handlers
  - `GET /health` endpoint (DB + Redis + data freshness)
  - `backend/app/core/config.py` con Settings (Pydantic Settings v2)
  - `backend/app/core/logging.py` con structlog
  - Verificar: `curl localhost:8000/health` → `{"status": "ok"}`
  - Referencia: `docs/03-ARCHITECTURE.md#backend`
  - Tamaño: S

- [ ] **B-017** Rate limiting middleware
  - SlowAPI o middleware custom con Redis
  - 30 req/min anónimo, 60 req/min autenticado
  - Tamaño: S

### Data Pipeline (Sem 1-2)

- [ ] **B-004** Indeed Crawler v1
  - `backend/app/crawler/jobs/indeed.py`
  - Búsqueda de roles: AI Engineer, Analytics Engineer, Data Engineer en AR, MX, ES
  - Deduplicación por hash de contenido
  - Rate limit: 1 req / 5 segundos
  - Logging de run: items encontrados, nuevos, duplicados, errores
  - Verificar: correr manualmente y ver registros en `job_postings`
  - Referencia: `docs/08-CRAWLERS.md`
  - Tamaño: M

- [ ] **B-005** Skills Extractor (LLM)
  - `backend/app/etl/skills_extractor.py`
  - Usa `claude-haiku-4-5` para extraer skills de `job_postings.description_clean`
  - Output: array de skills + categorías → `job_postings.skills` y `job_postings.skills_jsonb`
  - Procesar en batches de 50 ofertas
  - Verificar: 100 ofertas procesadas correctamente
  - Referencia: `docs/05-DATA_SOURCES.md#pipeline-de-datos`
  - Tamaño: M

### ATS Engine (Sem 2)

- [ ] **B-006** ATS Score Calculator
  - `backend/app/engine/ats.py`
  - `ATSMatcher`: matching exacto + alias + semántico
  - `calculate_ats_score()`: score ponderado + penalización por keywords críticas
  - `RecommendationEngine`: genera top 5 recomendaciones
  - Tests unitarios completos
  - Referencia: `docs/09-ATS_ENGINE.md`
  - Tamaño: M

- [ ] **B-007** `POST /analyze/cv` endpoint
  - `backend/app/api/routes/analyze.py`
  - Acepta PDF (multipart) o texto plano
  - Llama a `CVParser` → `ATSEngine` → `RecommendationEngine`
  - Responde con el schema de `docs/07-API_SPEC.md#post-analyzecv`
  - Tests de integración: score válido, keywords correctas, rate limit funciona
  - Tamaño: M

### Frontend básico (Sem 2)

- [ ] **F-001** Next.js setup
  - `npx create-next-app@latest frontend --typescript --tailwind --app`
  - Instalar shadcn/ui, zustand, react-query, recharts
  - `frontend/src/lib/api.ts` — cliente HTTP tipado
  - Tamaño: S

- [ ] **F-002** Landing page + CV Analyzer form
  - Formulario para pegar CV o subir PDF
  - Selector de rol objetivo
  - Loading state durante el análisis
  - Mostrar ATS Score + keywords + top 3 recomendaciones
  - Tamaño: M

---

## Criterios de aceptación del sprint

- [ ] `docker compose up` levanta todos los servicios sin errores
- [ ] `GET /health` responde `{"status": "ok"}`
- [ ] Indeed Crawler procesó al menos 500 ofertas correctamente
- [ ] Skills Extractor categorizó las skills de esas 500 ofertas
- [ ] `POST /analyze/cv` con un CV real devuelve un ATS Score entre 0-100
- [ ] Las keywords que devuelve son relevantes para el rol objetivo
- [ ] El frontend muestra el análisis correctamente
- [ ] Tests unitarios del ATS Engine al 90% de cobertura
- [ ] Deploy a Railway staging funcionando

---

## Blockers

*(ninguno al iniciar)*

---

## Notas

- Para el CV Analyzer en MVP, usar el texto del CV de Joaco como caso de prueba real
- El ATS Score todavía es una v1 — no necesita ser perfecto, necesita ser explicable
- Si el frontend queda por tiempo, OK deployar solo la API en staging
- El Greenhouse Crawler (B-008) se mueve al Sprint 002 para no extender
