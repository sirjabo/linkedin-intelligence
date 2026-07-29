# LinkedIn Intelligence — Claude Code Context

## Qué es este proyecto

LinkedIn Intelligence es una plataforma de inteligencia de mercado laboral que analiza ofertas de trabajo, perfiles y tendencias para ayudar a profesionales tech a optimizar su perfil de LinkedIn y CV.

**Repositorio**: `sirjabo/linkedin-intelligence`  
**Stack**: Python 3.11 + FastAPI + PostgreSQL + pgvector + LangChain + Next.js  
**Estado**: En desarrollo activo (Fase 1 — MVP)

## Instrucciones completas para Claude Code

Ver: `agents/CLAUDE.md`

## Documentación del proyecto

| Doc | Descripción |
|-----|-------------|
| `docs/00-VISION.md` | Problema y misión |
| `docs/01-PRD.md` | Requerimientos de producto |
| `docs/02-ROADMAP.md` | Roadmap de 12 meses |
| `docs/03-ARCHITECTURE.md` | Arquitectura del sistema |
| `docs/04-TECH_STACK.md` | Stack tecnológico |
| `docs/06-DATABASE.md` | Schema de la base de datos |
| `docs/07-API_SPEC.md` | Contratos de la API |
| `docs/09-ATS_ENGINE.md` | ATS Score algorithm |
| `docs/17-CODING_STANDARDS.md` | Estándares de código |
| `docs/19-DECISIONS.md` | Decisiones arquitectónicas |
| `docs/20-BACKLOG.md` | Backlog priorizado |

## Sprint activo

`tasks/sprint-001.md`

## Comandos de desarrollo

```bash
# Levantar infraestructura
docker compose up -d

# Backend
cd backend && pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Tests
pytest --cov=app tests/

# Linting
ruff check . && mypy .
```
