# Brief para Cursor — Sprint 001

## Tu rol

Sos el programador de este proyecto. Tu trabajo es implementar el código. No tomás decisiones de arquitectura ni de producto — todo ya está documentado. Si algo no está claro, preguntá antes de inventar.

## Antes de escribir una sola línea de código

Leé estos archivos en este orden:

1. `agents/CURSOR.md` — tu rol y las reglas que seguís
2. `docs/03-ARCHITECTURE.md` — cómo está organizado el sistema
3. `docs/04-TECH_STACK.md` — qué librerías usar y por qué
4. `docs/06-DATABASE.md` — el schema completo de la base de datos
5. `docs/07-API_SPEC.md` — los contratos exactos de cada endpoint
6. `docs/09-ATS_ENGINE.md` — el algoritmo del ATS Score
7. `docs/17-CODING_STANDARDS.md` — cómo escribir el código

## Qué tenés que construir

Todo lo de `tasks/sprint-001.md`. En orden:

---

### 1. Docker Compose (B-001)

Crear `docker-compose.yml` con:
- PostgreSQL 16 con extensión pgvector
- Redis 7
- Servicio `api` (FastAPI)
- Servicio `worker` (Celery)

Verificación: `docker compose up -d` → todos los servicios healthy.

---

### 2. FastAPI skeleton (B-002)

Crear `backend/` con esta estructura:

```
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py       # Pydantic Settings
│   │   └── logging.py      # structlog
│   ├── api/
│   │   ├── deps.py         # get_db, get_current_user
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       └── analyze.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models/
│   │       ├── __init__.py
│   │       └── job_posting.py
│   ├── schemas/
│   │   └── analyze.py
│   └── engine/
│       └── ats.py
├── tests/
│   ├── conftest.py
│   └── unit/
│       └── test_ats_engine.py
├── alembic/
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── alembic.ini
└── .python-version
```

Archivos clave:

**`backend/requirements.txt`**
```
fastapi==0.111.0
uvicorn[standard]==0.30.0
pydantic==2.7.0
pydantic-settings==2.3.0
sqlalchemy==2.0.30
asyncpg==0.29.0
alembic==1.13.1
pgvector==0.3.1
redis==5.0.4
celery==5.4.0
httpx==0.27.0
langchain==0.2.0
langchain-anthropic==0.1.15
langchain-openai==0.1.8
langgraph==0.1.0
sentence-transformers==3.0.0
pdfplumber==0.11.0
spacy==3.7.4
structlog==24.2.0
slowapi==0.1.9
```

**`backend/requirements-dev.txt`**
```
-r requirements.txt
pytest==8.2.0
pytest-asyncio==0.23.7
pytest-cov==5.0.0
httpx==0.27.0
ruff==0.4.7
mypy==1.10.0
pre-commit==3.7.1
```

**`backend/app/core/config.py`**
```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_VERSION: str = "0.1.0"
    SECRET_KEY: str
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

**`backend/app/main.py`**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health, analyze
from app.core.config import settings
import structlog

logger = structlog.get_logger()

app = FastAPI(
    title="LinkedIn Intelligence API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router, prefix="/api/v1")
```

Verificación: `curl http://localhost:8000/health` → `{"status": "ok"}`

---

### 3. Migraciones Alembic (B-003)

Setup de Alembic y primera migración con las tablas:
- `job_postings` (ver `docs/06-DATABASE.md`)
- `skills_catalog`
- `skill_demand`
- `users`

Verificación: `alembic upgrade head` sin errores.

---

### 4. Rate limiting (B-017)

Middleware con `slowapi`:
- 30 requests/minuto para usuarios anónimos
- Aplicado a `/api/v1/analyze/*`

---

### 5. ATS Engine (B-006)

Implementar `backend/app/engine/ats.py` siguiendo **exactamente** el algoritmo de `docs/09-ATS_ENGINE.md`:

- `CVParser`: extrae secciones del CV (contact, summary, experience, skills, education, projects)
- `ATSMatcher`: matching exacto + alias + semántico
- `calculate_ats_score()`: score ponderado + penalización por keywords críticas
- `RecommendationEngine`: genera hasta 5 recomendaciones priorizadas

Tests unitarios en `tests/unit/test_ats_engine.py`:
- Score 0 cuando no hay ninguna keyword
- Score 100 cuando están todas
- Alias matching funciona (langchain == LangChain)
- Penalización por keyword crítica faltante reduce el score
- Recomendaciones ordenadas por prioridad

---

### 6. Endpoint `POST /analyze/cv` (B-007)

Implementar en `backend/app/api/routes/analyze.py` siguiendo el contrato exacto de `docs/07-API_SPEC.md#post-analyzecv`.

Request:
```json
{
  "cv_text": "string (min 100 chars)",
  "target_role": "ai_engineer | data_engineer | analytics_engineer"
}
```

Response:
```json
{
  "analysis_id": "uuid",
  "ats_score": 72,
  "target_role": "ai_engineer",
  "summary": "string",
  "keyword_analysis": {
    "found": [...],
    "missing": [...]
  },
  "section_scores": {...},
  "recommendations": [...],
  "processing_time_ms": 1200
}
```

Para el MVP, las keywords del rol objetivo pueden ser un diccionario hardcodeado (hasta que el crawler llene la DB):

```python
ROLE_KEYWORDS = {
    "ai_engineer": [
        {"name": "Python", "weight": 1.0},
        {"name": "LangChain", "weight": 0.90},
        {"name": "LangGraph", "weight": 0.85},
        {"name": "FastAPI", "weight": 0.80},
        {"name": "RAG", "weight": 0.80},
        {"name": "SQL", "weight": 0.75},
        {"name": "Docker", "weight": 0.70},
        {"name": "OpenAI API", "weight": 0.70},
        {"name": "Embeddings", "weight": 0.65},
        {"name": "Vector Database", "weight": 0.65},
        {"name": "Prompt Engineering", "weight": 0.60},
        {"name": "REST API", "weight": 0.60},
        {"name": "Git", "weight": 0.55},
        {"name": "AWS", "weight": 0.50},
        {"name": "PostgreSQL", "weight": 0.50},
    ],
    "data_engineer": [
        {"name": "Python", "weight": 1.0},
        {"name": "SQL", "weight": 0.95},
        {"name": "Spark", "weight": 0.85},
        {"name": "Airflow", "weight": 0.80},
        {"name": "dbt", "weight": 0.75},
        {"name": "AWS", "weight": 0.75},
        {"name": "Kafka", "weight": 0.70},
        {"name": "Docker", "weight": 0.65},
        {"name": "PostgreSQL", "weight": 0.60},
        {"name": "Git", "weight": 0.55},
    ],
    "analytics_engineer": [
        {"name": "SQL", "weight": 1.0},
        {"name": "dbt", "weight": 0.90},
        {"name": "Python", "weight": 0.85},
        {"name": "Looker", "weight": 0.70},
        {"name": "BigQuery", "weight": 0.70},
        {"name": "Snowflake", "weight": 0.65},
        {"name": "Git", "weight": 0.60},
        {"name": "Airflow", "weight": 0.55},
        {"name": "Tableau", "weight": 0.50},
    ],
}
```

---

### 7. Indeed Crawler (B-004) — opcional en Sprint 001

Si llegás con tiempo, implementar `backend/app/crawler/jobs/indeed.py`.

Si no, saltearlo — el ATS Engine con keywords hardcodeadas ya es suficiente para el MVP.

---

## Reglas que no podés romper

1. **Type hints** en todas las funciones, sin excepción
2. **async/await** en todos los endpoints y operaciones de I/O
3. **structlog** para logs, nunca `print()`
4. **Pydantic models** para todos los datos estructurados, nunca `dict` crudos
5. **Nunca SQL con f-strings** — usar SQLAlchemy ORM o queries parametrizadas
6. **Nunca secrets hardcodeados** — solo desde `settings` que lee `.env`
7. **Tests para el ATS Engine** — es el core del producto, necesita cobertura

## Cómo probar que todo funciona

```bash
# 1. Levantar servicios
docker compose up -d

# 2. Instalar dependencias
cd backend && pip install -r requirements.txt

# 3. Migraciones
alembic upgrade head

# 4. Levantar API
uvicorn app.main:app --reload

# 5. Health check
curl http://localhost:8000/health

# 6. Probar el endpoint
curl -X POST http://localhost:8000/api/v1/analyze/cv \
  -H "Content-Type: application/json" \
  -d '{
    "cv_text": "Soy Analytics Engineer con 5 años de experiencia en Python, SQL, pandas, n8n y Power BI. Trabajé en BBVA desarrollando pipelines de datos y automatizaciones. Tengo experiencia con PostgreSQL, Git y APIs REST.",
    "target_role": "ai_engineer"
  }'

# 7. Correr tests
pytest tests/ -v

# 8. Verificar linting
ruff check . && mypy .
```

## Cuándo terminaste

El sprint está completo cuando:
- [ ] `docker compose up -d` levanta sin errores
- [ ] `GET /health` responde `{"status": "ok"}`
- [ ] `POST /analyze/cv` devuelve un ATS Score entre 0-100
- [ ] Las keywords encontradas/faltantes son coherentes con el CV de prueba
- [ ] `pytest tests/` pasa al 100%
- [ ] `ruff check .` sin errores
