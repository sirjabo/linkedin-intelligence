# Brief para Cursor — Sprint 002

## Tu rol

Sos el programador de este proyecto. Tu trabajo es implementar el código. No tomás decisiones de arquitectura ni de producto — todo ya está documentado. Si algo no está claro, preguntá antes de inventar.

## Antes de empezar

Leé estos archivos en este orden:

1. `agents/CURSOR.md` — tu rol y las reglas que seguís
2. `docs/10-LINKEDIN_ENGINE.md` — el algoritmo del LinkedIn Engine
3. `docs/07-API_SPEC.md` — contratos de los nuevos endpoints
4. `docs/13-SECURITY.md` — implementación de JWT
5. `docs/17-CODING_STANDARDS.md` — cómo escribir el código

## Qué ya existe (Sprint 001)

Sprint 001 está completo. Ya tenés:

- `backend/app/engine/ats.py` — ATS Engine con ROLE_KEYWORDS y calculate_ats_score()
- `backend/app/engine/cv_parser.py` — CVParser
- `backend/app/api/routes/analyze.py` — POST /analyze/cv funcionando
- `backend/app/crawler/jobs/indeed.py` — Indeed Crawler
- `backend/app/api/middleware/rate_limit.py` — SlowAPI
- `frontend/src/app/page.tsx` — Landing page con formulario de CV
- `frontend/src/components/AnalysisResult.tsx` — Resultados del ATS Score
- Modelos SQLAlchemy: `job_posting`, `cv_analysis`, `user`, `skills_catalog`, `skill_demand`

**No toques ninguno de estos archivos a menos que haya un bug confirmado.**

---

## Qué tenés que construir

En este orden estricto:

---

### 1. LinkedIn Engine (B-011 + B-012)

Crear `backend/app/engine/linkedin.py` con estas clases, siguiendo **exactamente** el algoritmo de `docs/10-LINKEDIN_ENGINE.md`:

```
backend/app/engine/linkedin.py
```

**Clases requeridas**:

- `ProfileParser` — extrae secciones del texto de perfil (title, about, skills, experience, projects, education)
- `TitleScorer` — score 0-100 para el headline de LinkedIn
- `AboutScorer` — score 0-100 para la sección About
- `ProfileScorer` — score ponderado final usando `SECTION_WEIGHTS`
- Dataclasses: `ParsedProfile`, `TitleScore`, `AboutScore`, `SectionScores`, `ProfileAnalysisResult`, `Recommendation`

**Constantes que deben estar en el módulo**:

```python
SECTION_WEIGHTS = {
    "title":      0.25,
    "about":      0.20,
    "skills":     0.20,
    "experience": 0.20,
    "projects":   0.10,
    "education":  0.05,
}

# Keywords del rol en el título (para detectar role_mentioned)
ROLE_TITLE_KEYWORDS: dict[str, list[str]] = {
    "ai_engineer": ["ai engineer", "llm engineer", "genai engineer", "applied ai engineer", "machine learning engineer"],
    "data_engineer": ["data engineer", "etl engineer", "platform engineer"],
    "analytics_engineer": ["analytics engineer", "data analyst", "bi engineer"],
    "ml_engineer": ["ml engineer", "mlops engineer", "machine learning engineer"],
}

# Variantes de título sugeridas (hardcodeadas para MVP)
TITLE_VARIANTS: dict[str, list[str]] = {
    "ai_engineer": [
        "AI Engineer | Analytics Engineer | LLMs · RAG · LangChain · Python · FastAPI · SQL",
        "Analytics Engineer → AI Engineer | LLMs · RAG · Python · FastAPI · GenAI",
        "Data & AI Engineer | LangChain · LangGraph · Python · SQL · Cloud",
        "AI Engineer | Python · LangChain · LangGraph · SQL · RAG · FastAPI",
        "Applied AI Engineer | LLMs · RAG · Embeddings · Python · FastAPI",
    ],
    "data_engineer": [
        "Data Engineer | Python · Spark · Airflow · dbt · AWS",
        "Senior Data Engineer | ETL · Kafka · Spark · dbt · PostgreSQL",
        "Data Engineer | Airflow · dbt · Python · SQL · Cloud",
    ],
    "analytics_engineer": [
        "Analytics Engineer | dbt · SQL · Python · Looker · BigQuery",
        "Analytics Engineer | dbt · BigQuery · Python · Snowflake · Looker",
        "Data & Analytics Engineer | SQL · dbt · Python · BI · Cloud",
    ],
    "ml_engineer": [
        "ML Engineer | Python · TensorFlow · PyTorch · MLflow · AWS",
        "MLOps Engineer | Python · Kubeflow · MLflow · Docker · Kubernetes",
    ],
}
```

**Lógica de TitleScorer**:

```python
def score(self, title: str, target_role: str) -> TitleScore:
    # 1. role_mentioned: alguna de las ROLE_TITLE_KEYWORDS aparece en el título (case-insensitive)
    # 2. tech_keywords_count: cuántas de las ROLE_KEYWORDS del ATS Engine aparecen en el título
    # 3. length_ok: len(title) <= 220
    # 4. role_first: el título empieza con el rol objetivo
    
    # Score ponderado:
    # role_mentioned   → 30 pts
    # tech_keywords    → 10 pts por keyword, máximo 40 (4 keywords)
    # length_ok        → 10 pts
    # role_first       → 10 pts (bonus encima de role_mentioned)
    # Máximo: 90 pts (no 100, para que sea difícil la perfección)
```

**Lógica de AboutScorer**:

```python
def score(self, about: str, target_role: str) -> AboutScore:
    # has_hook: las primeras 200 caracteres contienen keywords del rol
    # tech_keywords_count: total de keywords técnicas del rol en el texto
    # has_quantified_results: regex para números + % o años
    # optimal_length: 200 <= len(about) <= 2600
    # has_cta: últimas 200 chars contienen señales de CTA
    
    # Score:
    # has_hook             → 20 pts
    # tech_keywords_count  → 8 pts cada una, máximo 40 (5 keywords)
    # has_quantified_results → 15 pts
    # optimal_length       → 10 pts
    # has_cta              → 15 pts
    # Máximo: 100 pts
```

**Tests en `tests/unit/test_linkedin_engine.py`** (crearlo):

- TitleScorer: score bajo para "Analista SSR en BBVA" (< 20)
- TitleScorer: score alto para "AI Engineer | Python · LangChain · SQL" (> 70)
- AboutScorer: score 0 si about está vacío
- AboutScorer: detecta CTA en las últimas líneas
- ProfileScorer: overall_score ponderado correcto
- ProfileParser: extrae el título de la primera línea con rol
- Recomendaciones: la primera recomendación es siempre sobre la sección con menor score × peso

---

### 2. Endpoint `POST /analyze/linkedin` (B-010)

Crear `backend/app/schemas/linkedin.py`:

```python
from pydantic import BaseModel, Field
from typing import Literal

ImpactType = Literal["very_high", "high", "medium", "low"]

class LinkedInAnalysisRequest(BaseModel):
    profile_text: str = Field(min_length=50)
    linkedin_url: str = ""
    target_role: Literal["ai_engineer", "data_engineer", "analytics_engineer", "ml_engineer"]

class SectionScoresResponse(BaseModel):
    title: float
    about: float
    experience: float
    skills: float
    projects: float
    education: float

class TitleAnalysis(BaseModel):
    current: str
    issues: list[str]
    suggested_variants: list[str]

class RecommendationResponse(BaseModel):
    priority: int
    section: str
    message: str
    impact: ImpactType

class LinkedInAnalysisResponse(BaseModel):
    analysis_id: str
    overall_score: float
    target_role: str
    section_scores: SectionScoresResponse
    title_analysis: TitleAnalysis
    recommendations: list[RecommendationResponse]
    processing_time_ms: int
```

Agregar el endpoint en `backend/app/api/routes/analyze.py` (no crear nuevo archivo, agregarlo al existente):

```python
@router.post("/analyze/linkedin", response_model=LinkedInAnalysisResponse)
@limiter.limit("30/minute")
async def analyze_linkedin(
    request: Request,
    body: LinkedInAnalysisRequest,
) -> LinkedInAnalysisResponse:
    start = time.monotonic()
    
    parser = ProfileParser()
    scorer = ProfileScorer()
    
    parsed = parser.parse(body.profile_text)
    result = scorer.score(parsed, body.target_role)
    
    elapsed_ms = int((time.monotonic() - start) * 1000)
    
    return LinkedInAnalysisResponse(
        analysis_id=str(uuid4()),
        overall_score=result.overall_score,
        target_role=body.target_role,
        section_scores=SectionScoresResponse(
            title=result.section_scores.title,
            about=result.section_scores.about,
            experience=result.section_scores.experience,
            skills=result.section_scores.skills,
            projects=result.section_scores.projects,
            education=result.section_scores.education,
        ),
        title_analysis=TitleAnalysis(
            current=result.title_analysis["current"],
            issues=result.title_analysis["issues"],
            suggested_variants=result.title_analysis["suggested_variants"],
        ),
        recommendations=[
            RecommendationResponse(
                priority=r.priority,
                section=r.section,
                message=r.message,
                impact=r.impact,
            )
            for r in result.recommendations
        ],
        processing_time_ms=elapsed_ms,
    )
```

Verificación:
```bash
curl -X POST http://localhost:8000/api/v1/analyze/linkedin \
  -H "Content-Type: application/json" \
  -d '{
    "profile_text": "Joaquín Bravok\nAnalista SSR en BBVA\n\nAbout\nAnalista de datos con 5 años de experiencia en Python y SQL.\n\nExperience\nBBVA — Analytics Engineer\nDesarrollo de pipelines de datos con Python y SQL.\n\nSkills\nPython · SQL · Power BI · Excel · n8n",
    "target_role": "ai_engineer"
  }'
```

Respuesta esperada: `overall_score` entre 20-50, `title_analysis.issues` con al menos 1 problema, `recommendations` con al menos 3 items.

---

### 3. Endpoint `GET /market/skills/{role}` (B-009)

Crear `backend/app/api/routes/market.py`:

```python
from fastapi import APIRouter, Path, Query, Request
from app.api.middleware.rate_limit import limiter
from datetime import date, timedelta
from typing import Literal

router = APIRouter(tags=["market"])

# Hardcoded para MVP (hasta que los crawlers llenen la DB)
SKILLS_DATA: dict[str, list[dict]] = {
    "ai_engineer": [
        {"rank": 1,  "name": "Python",            "slug": "python",            "category": "language",   "frequency_pct": 94.2, "job_count": 1168, "trend": "stable",   "change_pct":  1.2},
        {"rank": 2,  "name": "LangChain",          "slug": "langchain",         "category": "ai_ml",      "frequency_pct": 67.8, "job_count":  841, "trend": "rising",   "change_pct": 22.4},
        {"rank": 3,  "name": "SQL",                "slug": "sql",               "category": "language",   "frequency_pct": 65.1, "job_count":  807, "trend": "stable",   "change_pct":  0.8},
        {"rank": 4,  "name": "FastAPI",            "slug": "fastapi",           "category": "framework",  "frequency_pct": 58.3, "job_count":  723, "trend": "rising",   "change_pct": 15.2},
        {"rank": 5,  "name": "Docker",             "slug": "docker",            "category": "devops",     "frequency_pct": 55.7, "job_count":  691, "trend": "stable",   "change_pct":  2.1},
        {"rank": 6,  "name": "RAG",                "slug": "rag",               "category": "ai_ml",      "frequency_pct": 51.2, "job_count":  635, "trend": "rising",   "change_pct": 31.5},
        {"rank": 7,  "name": "LangGraph",          "slug": "langgraph",         "category": "ai_ml",      "frequency_pct": 44.8, "job_count":  556, "trend": "rising",   "change_pct": 42.0},
        {"rank": 8,  "name": "OpenAI API",         "slug": "openai-api",        "category": "ai_ml",      "frequency_pct": 43.1, "job_count":  535, "trend": "stable",   "change_pct":  4.3},
        {"rank": 9,  "name": "AWS",                "slug": "aws",               "category": "cloud",      "frequency_pct": 42.6, "job_count":  528, "trend": "stable",   "change_pct":  1.9},
        {"rank": 10, "name": "PostgreSQL",         "slug": "postgresql",        "category": "database",   "frequency_pct": 38.5, "job_count":  478, "trend": "stable",   "change_pct": -0.5},
        {"rank": 11, "name": "Vector Database",    "slug": "vector-database",   "category": "database",   "frequency_pct": 36.2, "job_count":  449, "trend": "rising",   "change_pct": 28.7},
        {"rank": 12, "name": "Embeddings",         "slug": "embeddings",        "category": "ai_ml",      "frequency_pct": 33.8, "job_count":  419, "trend": "rising",   "change_pct": 19.4},
        {"rank": 13, "name": "Prompt Engineering", "slug": "prompt-engineering","category": "ai_ml",      "frequency_pct": 31.5, "job_count":  391, "trend": "stable",   "change_pct":  5.2},
        {"rank": 14, "name": "REST API",           "slug": "rest-api",          "category": "backend",    "frequency_pct": 28.9, "job_count":  358, "trend": "stable",   "change_pct": -1.2},
        {"rank": 15, "name": "Git",                "slug": "git",               "category": "devops",     "frequency_pct": 26.4, "job_count":  327, "trend": "stable",   "change_pct":  0.3},
    ],
    "data_engineer": [
        {"rank": 1,  "name": "Python",     "slug": "python",    "category": "language",  "frequency_pct": 96.1, "job_count": 1420, "trend": "stable",   "change_pct":  0.8},
        {"rank": 2,  "name": "SQL",        "slug": "sql",       "category": "language",  "frequency_pct": 93.4, "job_count": 1382, "trend": "stable",   "change_pct":  1.1},
        {"rank": 3,  "name": "Spark",      "slug": "spark",     "category": "framework", "frequency_pct": 72.3, "job_count": 1069, "trend": "stable",   "change_pct": -2.1},
        {"rank": 4,  "name": "Airflow",    "slug": "airflow",   "category": "platform",  "frequency_pct": 68.5, "job_count": 1014, "trend": "stable",   "change_pct":  3.4},
        {"rank": 5,  "name": "dbt",        "slug": "dbt",       "category": "platform",  "frequency_pct": 61.2, "job_count":  906, "trend": "rising",   "change_pct": 18.9},
        {"rank": 6,  "name": "AWS",        "slug": "aws",       "category": "cloud",     "frequency_pct": 58.7, "job_count":  869, "trend": "stable",   "change_pct":  2.3},
        {"rank": 7,  "name": "Kafka",      "slug": "kafka",     "category": "platform",  "frequency_pct": 47.3, "job_count":  700, "trend": "stable",   "change_pct": -1.8},
        {"rank": 8,  "name": "Docker",     "slug": "docker",    "category": "devops",    "frequency_pct": 43.1, "job_count":  638, "trend": "stable",   "change_pct":  4.1},
        {"rank": 9,  "name": "PostgreSQL", "slug": "postgresql","category": "database",  "frequency_pct": 38.9, "job_count":  576, "trend": "stable",   "change_pct":  1.5},
        {"rank": 10, "name": "Git",        "slug": "git",       "category": "devops",    "frequency_pct": 35.2, "job_count":  521, "trend": "stable",   "change_pct":  0.4},
    ],
    "analytics_engineer": [
        {"rank": 1,  "name": "SQL",        "slug": "sql",        "category": "language",  "frequency_pct": 97.8, "job_count": 1089, "trend": "stable",  "change_pct":  0.5},
        {"rank": 2,  "name": "dbt",        "slug": "dbt",        "category": "platform",  "frequency_pct": 82.3, "job_count":  917, "trend": "rising",  "change_pct": 24.6},
        {"rank": 3,  "name": "Python",     "slug": "python",     "category": "language",  "frequency_pct": 74.6, "job_count":  831, "trend": "stable",  "change_pct":  1.9},
        {"rank": 4,  "name": "BigQuery",   "slug": "bigquery",   "category": "database",  "frequency_pct": 58.1, "job_count":  647, "trend": "stable",  "change_pct":  3.2},
        {"rank": 5,  "name": "Looker",     "slug": "looker",     "category": "bi",        "frequency_pct": 51.4, "job_count":  573, "trend": "stable",  "change_pct": -1.4},
        {"rank": 6,  "name": "Snowflake",  "slug": "snowflake",  "category": "database",  "frequency_pct": 47.9, "job_count":  534, "trend": "rising",  "change_pct": 11.2},
        {"rank": 7,  "name": "Git",        "slug": "git",        "category": "devops",    "frequency_pct": 43.2, "job_count":  481, "trend": "stable",  "change_pct":  0.7},
        {"rank": 8,  "name": "Airflow",    "slug": "airflow",    "category": "platform",  "frequency_pct": 38.7, "job_count":  431, "trend": "stable",  "change_pct":  2.8},
        {"rank": 9,  "name": "Tableau",    "slug": "tableau",    "category": "bi",        "frequency_pct": 35.1, "job_count":  391, "trend": "declining","change_pct": -8.3},
    ],
    "ml_engineer": [
        {"rank": 1,  "name": "Python",      "slug": "python",      "category": "language",  "frequency_pct": 97.1, "job_count": 1351, "trend": "stable", "change_pct":  0.9},
        {"rank": 2,  "name": "TensorFlow",  "slug": "tensorflow",  "category": "ai_ml",     "frequency_pct": 71.2, "job_count":  991, "trend": "stable", "change_pct": -1.2},
        {"rank": 3,  "name": "PyTorch",     "slug": "pytorch",     "category": "ai_ml",     "frequency_pct": 68.9, "job_count":  959, "trend": "rising", "change_pct":  9.4},
        {"rank": 4,  "name": "Docker",      "slug": "docker",      "category": "devops",    "frequency_pct": 63.4, "job_count":  882, "trend": "stable", "change_pct":  2.7},
        {"rank": 5,  "name": "Kubernetes",  "slug": "kubernetes",  "category": "devops",    "frequency_pct": 52.1, "job_count":  726, "trend": "stable", "change_pct":  4.1},
        {"rank": 6,  "name": "MLflow",      "slug": "mlflow",      "category": "mlops",     "frequency_pct": 47.8, "job_count":  666, "trend": "rising", "change_pct": 15.3},
        {"rank": 7,  "name": "SQL",         "slug": "sql",         "category": "language",  "frequency_pct": 44.2, "job_count":  615, "trend": "stable", "change_pct":  1.1},
        {"rank": 8,  "name": "AWS",         "slug": "aws",         "category": "cloud",     "frequency_pct": 43.7, "job_count":  608, "trend": "stable", "change_pct":  2.3},
    ],
}


@router.get("/market/skills/{role}")
@limiter.limit("60/minute")
async def get_market_skills(
    request: Request,
    role: Literal["ai_engineer", "data_engineer", "analytics_engineer", "ml_engineer"] = Path(...),
    weeks: int = Query(default=4, ge=1, le=52),
    country: str = Query(default="AR", max_length=2),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    today = date.today()
    period_start = today - timedelta(weeks=weeks)

    skills = SKILLS_DATA.get(role, [])[:limit]

    return {
        "role": role,
        "country": country,
        "period": f"{period_start}/{today}",
        "total_jobs_analyzed": sum(s["job_count"] for s in skills),
        "skills": skills,
    }
```

Registrar el router en `backend/app/main.py`:

```python
from app.api.routes import health, analyze, market

app.include_router(market.router, prefix="/api/v1")
```

Verificación:
```bash
curl "http://localhost:8000/api/v1/market/skills/ai_engineer?limit=5"
```

---

### 4. Auth JWT (B-016)

#### 4.1. Agregar dependencias a `backend/requirements.txt`

Al final del archivo existente, agregar:
```
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

#### 4.2. Crear `backend/app/schemas/auth.py`

```python
from pydantic import BaseModel, EmailStr
from typing import Literal

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    target_role: Literal["ai_engineer", "data_engineer", "analytics_engineer", "ml_engineer"] = "ai_engineer"

class RegisterResponse(BaseModel):
    user_id: str
    email: str
    token: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    token: str
    expires_at: str

class TokenPayload(BaseModel):
    sub: str
    plan: str = "free"
    exp: int
```

#### 4.3. Crear `backend/app/core/security.py`

```python
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_MINUTES = 30

def hash_password(password: str) -> str:
    return PWD_CONTEXT.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return PWD_CONTEXT.verify(plain, hashed)

def create_access_token(subject: str, plan: str = "free") -> tuple[str, datetime]:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "plan": plan,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token, expire

def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
```

#### 4.4. Crear `backend/app/api/routes/auth.py`

```python
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from uuid import uuid4

from app.api.deps import get_db
from app.api.middleware.rate_limit import limiter
from app.core.security import hash_password, verify_password, create_access_token
from app.db.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse

logger = structlog.get_logger()
router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest) -> RegisterResponse:
    async for db in get_db():
        result = await db.execute(select(User).where(User.email == body.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            id=uuid4(),
            email=body.email,
            name=body.name,
            hashed_password=hash_password(body.password),
            target_role=body.target_role,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token, _ = create_access_token(subject=str(user.id))
        logger.info("user_registered", user_id=str(user.id), email=user.email)

        return RegisterResponse(
            user_id=str(user.id),
            email=user.email,
            token=token,
        )


@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    async for db in get_db():
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(body.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token, expires_at = create_access_token(subject=str(user.id))
        logger.info("user_logged_in", user_id=str(user.id))

        return LoginResponse(
            token=token,
            expires_at=expires_at.isoformat(),
        )
```

#### 4.5. Actualizar `backend/app/db/models/user.py`

El modelo `User` ya existe. Verificá que tenga estos campos (si faltan, agregarlos):
- `hashed_password: Mapped[str]`
- `name: Mapped[str]`
- `target_role: Mapped[str]`

Si el modelo actual tiene `password_hash` en vez de `hashed_password`, usá el nombre que ya tiene — no rompas lo que funciona.

#### 4.6. Registrar router en `backend/app/main.py`

```python
from app.api.routes import health, analyze, market, auth

app.include_router(auth.router, prefix="/api/v1")
```

#### 4.7. Actualizar `get_current_user` en `backend/app/api/deps.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import decode_token
from jose import JWTError

bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
```

Verificación:
```bash
# Registrar usuario
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test", "password": "test1234", "target_role": "ai_engineer"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test1234"}'
```

---

### 5. Greenhouse Crawler (B-008)

Crear `backend/app/crawler/jobs/greenhouse.py`.

El patrón es idéntico al IndeedCrawler ya existente. Greenhouse tiene una API pública JSON:

```
GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true
```

```python
import structlog
from httpx import AsyncClient
from app.crawler.base.base_crawler import BaseCrawler

logger = structlog.get_logger()

# Empresas tech que usan Greenhouse y contratan roles de datos/IA
GREENHOUSE_COMPANIES = [
    "anthropic",
    "notion",
    "figma",
    "vercel",
    "linear",
    "mercadolibre",
    "auth0",
    "globant",
]

TARGET_ROLES = ["data engineer", "analytics engineer", "ai engineer", "ml engineer", "machine learning"]

class GreenhouseCrawler(BaseCrawler):

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"

    async def crawl_company(self, company: str, client: AsyncClient) -> list[dict]:
        """Fetch all jobs for one Greenhouse company board."""
        url = self.BASE_URL.format(company=company)
        
        try:
            response = await client.get(url, params={"content": "true"}, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("greenhouse_fetch_failed", company=company, error=str(exc))
            return []

        jobs = data.get("jobs", [])
        relevant = []

        for job in jobs:
            title_lower = job.get("title", "").lower()
            if any(role in title_lower for role in TARGET_ROLES):
                relevant.append({
                    "title": job.get("title", ""),
                    "company": company,
                    "location": self._extract_location(job),
                    "url": job.get("absolute_url", ""),
                    "description": job.get("content", ""),
                    "source": "greenhouse",
                    "external_id": str(job.get("id", "")),
                })

        logger.info("greenhouse_company_crawled", company=company, total=len(jobs), relevant=len(relevant))
        return relevant

    async def run(self) -> list[dict]:
        """Crawl all configured companies."""
        all_jobs: list[dict] = []
        async with AsyncClient() as client:
            for company in GREENHOUSE_COMPANIES:
                jobs = await self.crawl_company(company, client)
                all_jobs.extend(jobs)
                await self._sleep_between_requests()  # usar el método del BaseCrawler
        
        logger.info("greenhouse_crawl_complete", total_jobs=len(all_jobs))
        return all_jobs

    def _extract_location(self, job: dict) -> str:
        offices = job.get("offices", [])
        if offices:
            return offices[0].get("name", "Remote")
        return "Remote"
```

No hay tests requeridos para el crawler en este sprint.

---

### 6. Frontend: Skills Radar chart (B-015)

#### 6.1. Instalar Recharts

En `frontend/`:
```bash
npm install recharts
```

#### 6.2. Crear `frontend/src/components/SkillsRadar.tsx`

```tsx
"use client";

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface Skill {
  name: string;
  frequency_pct: number;
  trend: "rising" | "stable" | "declining";
}

interface SkillsRadarProps {
  role: string;
  skills: Skill[];
}

const TREND_COLORS = {
  rising: "#22c55e",
  stable: "#3b82f6",
  declining: "#ef4444",
} as const;

export default function SkillsRadar({ role, skills }: SkillsRadarProps) {
  const top10 = skills.slice(0, 10);

  const chartData = top10.map((s) => ({
    subject: s.name,
    value: s.frequency_pct,
    trend: s.trend,
  }));

  return (
    <div className="w-full">
      <h2 className="text-xl font-semibold mb-4 text-center">
        Skills más demandadas — {role.replace("_", " ").toUpperCase()}
      </h2>
      <ResponsiveContainer width="100%" height={400}>
        <RadarChart data={chartData}>
          <PolarGrid />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={{ fontSize: 10 }}
          />
          <Radar
            name="Frecuencia %"
            dataKey="value"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.35}
          />
          <Tooltip
            formatter={(value: number) => [`${value.toFixed(1)}%`, "Frecuencia"]}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Tabla debajo del radar */}
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2 pr-4">#</th>
              <th className="text-left py-2 pr-4">Skill</th>
              <th className="text-right py-2 pr-4">Frecuencia</th>
              <th className="text-right py-2">Tendencia</th>
            </tr>
          </thead>
          <tbody>
            {skills.map((skill, i) => (
              <tr key={skill.name} className="border-b last:border-0">
                <td className="py-2 pr-4 text-gray-500">{i + 1}</td>
                <td className="py-2 pr-4 font-medium">{skill.name}</td>
                <td className="py-2 pr-4 text-right">{skill.frequency_pct.toFixed(1)}%</td>
                <td className="py-2 text-right">
                  <span
                    className="text-xs font-medium"
                    style={{ color: TREND_COLORS[skill.trend] }}
                  >
                    {skill.trend === "rising" ? "↑" : skill.trend === "declining" ? "↓" : "→"}{" "}
                    {skill.trend}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

#### 6.3. Crear `frontend/src/app/market/page.tsx`

```tsx
"use client";

import { useEffect, useState } from "react";
import SkillsRadar from "@/components/SkillsRadar";

type Role = "ai_engineer" | "data_engineer" | "analytics_engineer" | "ml_engineer";

const ROLE_LABELS: Record<Role, string> = {
  ai_engineer: "AI Engineer",
  data_engineer: "Data Engineer",
  analytics_engineer: "Analytics Engineer",
  ml_engineer: "ML Engineer",
};

export default function MarketPage() {
  const [role, setRole] = useState<Role>("ai_engineer");
  const [skills, setSkills] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/market/skills/${role}?limit=15`)
      .then((r) => r.json())
      .then((data) => setSkills(data.skills ?? []))
      .finally(() => setLoading(false));
  }, [role]);

  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-3xl font-bold mb-2">Skills Radar</h1>
      <p className="text-gray-500 mb-8">
        Skills más demandadas en el mercado laboral tech argentino.
      </p>

      <div className="flex gap-2 mb-10 flex-wrap">
        {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
          <button
            key={r}
            onClick={() => setRole(r)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              role === r
                ? "bg-indigo-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {ROLE_LABELS[r]}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">Cargando...</div>
      ) : (
        <SkillsRadar role={role} skills={skills} />
      )}
    </main>
  );
}
```

#### 6.4. Actualizar `frontend/src/app/layout.tsx`

Agregar link a `/market` en el nav si ya existe alguno. Si no hay nav, no crear uno — dejalo para Sprint 003.

---

### 7. CI/CD con GitHub Actions (B-019)

Crear `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, "claude/**", "cursor/**"]
  pull_request:
    branches: [main]

jobs:
  backend:
    name: Backend Tests
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: linkedin_intelligence_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    defaults:
      run:
        working-directory: backend

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Lint with ruff
        run: ruff check .

      - name: Type check with mypy
        run: mypy app/ --ignore-missing-imports

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/linkedin_intelligence_test
          REDIS_URL: redis://localhost:6379
          SECRET_KEY: test-secret-key-for-ci-only
          ENVIRONMENT: test
        run: pytest tests/ -v --tb=short

  frontend:
    name: Frontend Build
    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: frontend

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Type check
        run: npx tsc --noEmit

      - name: Build
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000
        run: npm run build
```

---

## Reglas que no podés romper

1. **Type hints** en todas las funciones, sin excepción
2. **async/await** en todos los endpoints y operaciones de I/O
3. **structlog** para logs, nunca `print()`
4. **Pydantic models** para todos los datos estructurados
5. **Nunca secrets hardcodeados** — solo desde `settings` que lee `.env`
6. **Nunca SQL con f-strings**
7. **No rompas lo que ya funciona** — Sprint 001 está verde, no lo toques sin razón

---

## Orden de ejecución recomendado

```
1. LinkedIn Engine (linkedin.py) + tests unitarios
2. POST /analyze/linkedin (agregar al routes/analyze.py)
3. GET /market/skills/{role} (nuevo routes/market.py)
4. Auth JWT (core/security.py + routes/auth.py)
5. Greenhouse Crawler
6. Frontend: SkillsRadar + /market page
7. GitHub Actions CI
```

---

## Cómo probar que todo funciona

```bash
# 1. Instalar nuevas dependencias
cd backend && pip install python-jose[cryptography] passlib[bcrypt]

# 2. Levantar servicios
docker compose up -d

# 3. Levantar API
uvicorn app.main:app --reload

# 4. LinkedIn analysis
curl -X POST http://localhost:8000/api/v1/analyze/linkedin \
  -H "Content-Type: application/json" \
  -d '{
    "profile_text": "Analista SSR en BBVA\n\nAbout\nAnalista de datos con experiencia en Python y SQL.\n\nSkills\nPython · SQL · Excel",
    "target_role": "ai_engineer"
  }'

# 5. Skills radar
curl "http://localhost:8000/api/v1/market/skills/ai_engineer?limit=5"

# 6. Auth
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "name": "Test", "password": "test1234", "target_role": "ai_engineer"}'

# 7. Tests
pytest tests/ -v

# 8. Linting
ruff check . && mypy app/ --ignore-missing-imports

# 9. Frontend
cd frontend && npm run dev
# Ir a http://localhost:3000/market
```

---

## Cuándo terminaste

El sprint está completo cuando:

- [ ] `POST /analyze/linkedin` devuelve overall_score + title_analysis + recommendations
- [ ] `GET /market/skills/ai_engineer` devuelve lista de skills con trend y frequency_pct
- [ ] `POST /auth/register` crea usuario y devuelve token JWT
- [ ] `POST /auth/login` devuelve token JWT para usuario existente
- [ ] `GET /health` sigue respondiendo `{"status": "ok"}` (no rompiste nada)
- [ ] `pytest tests/` pasa al 100% incluyendo `test_linkedin_engine.py`
- [ ] `ruff check .` sin errores
- [ ] Página `/market` en el frontend muestra el radar chart con las skills
- [ ] `.github/workflows/ci.yml` existe y el YAML es válido
