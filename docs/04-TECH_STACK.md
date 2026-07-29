# 04 · Tech Stack

## Principios de selección

1. **Dominio sobre novedad** — Priorizar tecnologías que el equipo conoce bien.
2. **Ecosistema Python** — El core es Python para maximizar librerías de IA/datos disponibles.
3. **Open source** — Preferir opciones open source para evitar lock-in y costos en fase inicial.
4. **Producción probada** — Nada experimental en el crítico path del dato.

---

## Stack completo

### Backend

| Tecnología | Versión | Rol | Por qué |
|-----------|---------|-----|---------|
| **Python** | 3.11+ | Lenguaje principal | Ecosistema IA, performance con 3.11 |
| **FastAPI** | 0.111+ | Framework API REST | Async nativo, tipado, OpenAPI automático |
| **Pydantic v2** | 2.x | Validación y serialización | Performance 5-50x vs v1, integración FastAPI |
| **SQLAlchemy** | 2.0+ | ORM | Async support, type hints, maduro |
| **Alembic** | 1.13+ | Migraciones de DB | Integración SQLAlchemy |
| **Celery** | 5.x | Task queue | Workers async, integración Redis |
| **Celery Beat** | — | Scheduler | Jobs nocturnos (AI Radar) |
| **Uvicorn** | — | ASGI server | Performance, soporte async |

### Base de datos

| Tecnología | Versión | Rol | Por qué |
|-----------|---------|-----|---------|
| **PostgreSQL** | 16 | Base de datos principal | ACID, JSON, full-text search |
| **pgvector** | 0.7+ | Búsqueda vectorial | Elimina necesidad de Pinecone/Qdrant en MVP |
| **Redis** | 7.x | Cache + message broker | Celery broker, cache de análisis, rate limiting |

**Decisión pgvector**: Para el volumen esperado en MVP (<1M vectores), pgvector en PostgreSQL elimina la necesidad de un servicio externo de vector DB, reduciendo costos y complejidad. Se revisará en Fase 5 si el volumen supera los límites de performance.

### IA / ML

| Tecnología | Versión | Rol | Por qué |
|-----------|---------|-----|---------|
| **LangChain** | 0.2+ | Framework LLM | Abstracción de LLMs, chains, RAG |
| **LangGraph** | 0.1+ | Agentes con estado | Multi-step agents, flujo de trabajo complejo |
| **Claude (Anthropic)** | claude-sonnet-5 | LLM primario | Mejor para análisis, escritura técnica |
| **GPT-4o** | — | LLM fallback | Redundancia en producción |
| **sentence-transformers** | 3.x | Embeddings locales | Sin costo por token, privacidad |
| **OpenAI Ada** | text-embedding-3-small | Embeddings cloud | Para comparaciones que requieren calidad máxima |
| **spaCy** | 3.7+ | NLP clásico | Extracción de entidades, NER de skills |
| **pdfplumber** | — | Parser PDF | Extracción de texto de CVs |

### Crawlers / ETL

| Tecnología | Versión | Rol | Por qué |
|-----------|---------|-----|---------|
| **Playwright** | 1.44+ | Browser automation | JavaScript-heavy sites (LinkedIn) |
| **BeautifulSoup4** | — | HTML parsing | Sites estáticos simples |
| **httpx** | — | HTTP async client | Async, compatible con FastAPI |
| **n8n** | — | Orquestación visual | Flujos complejos de datos, sin código |
| **pandas** | 2.x | Transformación de datos | ETL jobs, análisis exploratorio |

### Frontend

| Tecnología | Versión | Rol | Por qué |
|-----------|---------|-----|---------|
| **Next.js** | 14 | Framework React | App Router, SSR/SSG, performance |
| **TypeScript** | 5.x | Tipado | Correctitud, autocompletado |
| **Tailwind CSS** | 3.x | Estilos | Rapidez de desarrollo, consistencia |
| **shadcn/ui** | — | Componentes | Accesibles, personalizables, no lock-in |
| **Zustand** | — | Estado global | Simple, sin boilerplate |
| **React Query** | v5 | Data fetching | Cache, revalidación, loading states |
| **Recharts** | — | Visualizaciones | React-native, customizable |
| **Framer Motion** | — | Animaciones | UX premium |

### Infraestructura

| Tecnología | Versión | Rol | Por qué |
|-----------|---------|-----|---------|
| **Docker** | — | Containerización | Reproducibilidad, portabilidad |
| **Docker Compose** | v2 | Orquestación local | Dev environment simple |
| **GitHub Actions** | — | CI/CD | Integrado con GitHub, gratuito |
| **AWS** | — | Cloud hosting | EC2, RDS, S3, ECS (Fase 2+) |
| **Railway** | — | Hosting MVP | Más simple y barato para Fase 1 |

### Observabilidad

| Tecnología | Rol |
|-----------|-----|
| **structlog** | Logging estructurado en Python |
| **Prometheus** | Métricas |
| **Grafana** | Dashboards de métricas |
| **Sentry** | Error tracking |

### Calidad de código

| Tecnología | Rol |
|-----------|-----|
| **ruff** | Linter + formatter Python (reemplaza black + flake8) |
| **mypy** | Type checking estático |
| **pytest** | Testing framework |
| **pytest-asyncio** | Tests async |
| **pytest-cov** | Cobertura |
| **pre-commit** | Hooks de calidad antes de commit |
| **ESLint + Prettier** | Linting TypeScript |

---

## Variables de entorno requeridas

Ver [.env.example](../.env.example) para el listado completo.

Las variables críticas son:

```bash
# LLM
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/linkedin_intelligence
REDIS_URL=redis://localhost:6379

# App
SECRET_KEY=
ENVIRONMENT=development  # development | staging | production
```

---

## Versiones y compatibilidad

```
Python:   >= 3.11 (f-strings con =, tomllib nativo, performance)
Node.js:  >= 20 LTS
Docker:   >= 24
Postgres: >= 16 (mejoras de performance, pg_stat queries)
```

---

## Herramientas de desarrollo

```bash
# Setup del entorno
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Pre-commit hooks
pre-commit install

# Linting
ruff check .
ruff format .
mypy .

# Tests
pytest --cov=app tests/
```
