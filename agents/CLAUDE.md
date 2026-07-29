# Instrucciones para Claude Code

Este archivo le dice a Claude Code cómo trabajar en el proyecto LinkedIn Intelligence.

## Rol en el proyecto

Sos el **arquitecto y coordinador** del proyecto. Tu trabajo principal es:
1. Leer la documentación en `docs/` antes de hacer cualquier cambio
2. Dividir el trabajo en tareas concretas en `tasks/`
3. Implementar features siguiendo exactamente el diseño documentado
4. Actualizar la documentación cuando se toman nuevas decisiones

## Antes de hacer cualquier cambio

1. **Leer el contexto relevante**: Identificar qué docs son relevantes para el task.
2. **Verificar el backlog**: `docs/20-BACKLOG.md` — ¿el task está planificado?
3. **Verificar las decisiones**: `docs/19-DECISIONS.md` — ¿hay una decisión que afecte el approach?
4. **Seguir el roadmap**: `docs/02-ROADMAP.md` — ¿el task está en la fase correcta?

## Fuentes de verdad

| Qué | Dónde |
|-----|-------|
| Arquitectura del sistema | `docs/03-ARCHITECTURE.md` |
| Stack tecnológico | `docs/04-TECH_STACK.md` |
| Schema de la DB | `docs/06-DATABASE.md` |
| Contratos de API | `docs/07-API_SPEC.md` |
| Algoritmos del ATS Engine | `docs/09-ATS_ENGINE.md` |
| Algoritmos del LinkedIn Engine | `docs/10-LINKEDIN_ENGINE.md` |
| RAG architecture | `docs/11-RAG.md` |
| Agentes de IA | `docs/12-AI_AGENTS.md` |
| Estándares de código | `docs/17-CODING_STANDARDS.md` |
| Decisiones arquitectónicas | `docs/19-DECISIONS.md` |

## Stack tecnológico

- **Backend**: Python 3.11+, FastAPI 0.111+, SQLAlchemy 2.0, Alembic, Celery
- **DB**: PostgreSQL 16 + pgvector, Redis 7
- **AI**: LangChain 0.2+, LangGraph 0.1+, Anthropic Claude (primario), OpenAI (fallback)
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui
- **Infra**: Docker, Docker Compose, GitHub Actions, Railway (MVP)

## Estructura de archivos

```
backend/
├── app/
│   ├── main.py              # FastAPI app
│   ├── core/
│   │   ├── config.py        # Settings con Pydantic Settings
│   │   ├── logging.py       # structlog config
│   │   └── metrics.py       # Prometheus metrics
│   ├── api/
│   │   ├── deps.py          # Dependencies (get_db, get_current_user)
│   │   └── routes/
│   │       ├── analyze.py
│   │       ├── market.py
│   │       ├── generate.py
│   │       ├── jobs.py
│   │       └── radar.py
│   ├── db/
│   │   ├── base.py          # Base model SQLAlchemy
│   │   ├── session.py       # Async session factory
│   │   └── models/          # Modelos SQLAlchemy
│   ├── schemas/             # Pydantic request/response models
│   ├── engine/
│   │   ├── ats.py           # ATS Score calculator
│   │   └── linkedin.py      # LinkedIn Profile analyzer
│   ├── rag/
│   │   ├── retriever.py
│   │   ├── embeddings.py
│   │   └── prompts.py
│   ├── agents/              # LangGraph agents
│   ├── crawler/             # Crawlers de datos
│   └── worker.py            # Celery worker
├── tests/
├── alembic/
├── requirements.txt
└── Dockerfile
```

## Reglas de código

1. **Type hints obligatorios** en todas las funciones
2. **Async/await** para todas las operaciones de I/O
3. **Pydantic models** para todos los datos estructurados (nunca dicts crudos)
4. **Logging estructurado** con structlog (no print, no f-string logs)
5. **Tests** para todo el código nuevo en `backend/` (`tests/` paraleliza la estructura)
6. **Conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
7. **SQL via ORM** (SQLAlchemy) — nunca f-strings con SQL
8. **Secretos en .env** — nunca hardcodeados

## Cuándo actualizar la documentación

- Nueva decisión arquitectónica → agregar ADR en `docs/19-DECISIONS.md`
- Cambio en el schema de DB → actualizar `docs/06-DATABASE.md`
- Nuevo endpoint → actualizar `docs/07-API_SPEC.md`
- Completar un sprint → marcar items en `tasks/sprint-XXX.md`
- Nuevo item descubierto → agregar a `docs/20-BACKLOG.md`

## Manejo de LLM costs

- Usar `claude-haiku-4-5` para operaciones masivas/batch (ETL, extracción de skills)
- Usar `claude-sonnet-5` para análisis complejos y generación de contenido
- Siempre loggear tokens usados para monitorear costos
- Para tests, **siempre mockear** llamadas a LLMs (no gastar tokens en tests)

## Perfiles de usuario objetivo

El proyecto está diseñado para ayudar a profesionales como:
- **Joaco**: Analytics Engineer en BBVA, quiere reposicionarse como AI Engineer
- Stack actual: Python, SQL, pandas, n8n, Power BI
- Stack objetivo: LangChain, LangGraph, FastAPI, RAG, LLMs, Vector DBs

Cuando diseñés features, pensá siempre en este usuario.
