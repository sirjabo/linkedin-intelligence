# 16 · Testing

## Estrategia

```
                    E2E Tests (5%)
                   ─────────────
                  Integration Tests (20%)
                 ─────────────────────────
                Unit Tests (75%)
               ─────────────────────────────
```

La pirámide se respeta: muchos tests unitarios rápidos, menos tests de integración, muy pocos E2E.

---

## Setup

```bash
# Instalar dependencias de testing
pip install pytest pytest-asyncio pytest-cov httpx factory-boy freezegun

# Correr todos los tests
pytest

# Con coverage
pytest --cov=app --cov-report=html tests/

# Solo tests rápidos (sin DB)
pytest -m "not integration"

# Solo tests de un módulo
pytest tests/unit/test_ats_engine.py -v
```

---

## Estructura

```
tests/
├── conftest.py              # Fixtures globales
├── unit/
│   ├── test_ats_engine.py
│   ├── test_linkedin_engine.py
│   ├── test_cv_parser.py
│   ├── test_crawler_indeed.py
│   └── test_skills_extractor.py
├── integration/
│   ├── test_api_analyze.py
│   ├── test_api_market.py
│   ├── test_db_queries.py
│   └── test_rag_pipeline.py
└── e2e/
    └── test_full_cv_analysis.py
```

---

## Fixtures

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.main import app
from app.db.base import Base

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test_linkedin"

@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    async with AsyncSession(db_engine) as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def sample_cv_text():
    return """
    Joaquín Bravok
    joaco@example.com | LinkedIn: /in/joaco
    
    EXPERIENCIA
    Analytics Engineer - BBVA Argentina (2022-2025)
    - Desarrollo de pipelines de datos con Python y SQL
    - Análisis de datos de marketing con pandas y Power BI
    - Automatización de reportes con n8n
    
    SKILLS
    Python, SQL, pandas, Power BI, n8n, Git, PostgreSQL
    
    EDUCACIÓN
    Licenciatura en Sistemas - Universidad de Buenos Aires
    """

@pytest.fixture
def sample_linkedin_profile():
    return """
    Título: Analista SSR en BBVA
    
    Sobre mí:
    Profesional con experiencia en análisis de datos y automatización...
    
    Experiencia:
    Analytics Engineer - BBVA (2022-presente)
    
    Skills: Python, SQL, Power BI, n8n
    """
```

---

## Tests unitarios

### ATS Engine

```python
# tests/unit/test_ats_engine.py
import pytest
from app.engine.ats import ATSMatcher, calculate_ats_score

class TestATSMatcher:
    
    def test_exact_match_found(self):
        matcher = ATSMatcher()
        result = matcher.match(
            cv_skills=["Python", "SQL", "pandas"],
            role_keywords=[
                WeightedKeyword(name="Python", weight=0.9),
                WeightedKeyword(name="LangChain", weight=0.8),
            ]
        )
        assert len(result.matched) == 1
        assert result.matched[0].name == "Python"
        assert len(result.missing) == 1
    
    def test_alias_match(self):
        matcher = ATSMatcher()
        result = matcher.match(
            cv_skills=["langchain"],  # lowercase
            role_keywords=[WeightedKeyword(name="LangChain", weight=0.8)]
        )
        assert len(result.matched) == 1
    
    def test_score_calculation_all_present(self):
        keywords = [
            WeightedKeyword(name="Python", weight=1.0),
            WeightedKeyword(name="SQL", weight=0.8),
        ]
        result = MatchResult(matched=keywords, missing=[])
        score = calculate_ats_score(result)
        assert score == 100
    
    def test_score_penalizes_critical_missing(self):
        all_keywords = [
            WeightedKeyword(name="Python", weight=1.0),
            WeightedKeyword(name="LangChain", weight=0.95),   # Crítica
        ]
        result = MatchResult(
            matched=[all_keywords[0]],
            missing=[all_keywords[1]]   # Falta keyword crítica
        )
        score = calculate_ats_score(result)
        # Penalización: Python (1.0) / total (1.95) = 51% - 10 penalty = 41
        assert score < 50

class TestATSScoreRange:
    
    @pytest.mark.parametrize("cv_skills, expected_range", [
        ([], (0, 10)),
        (["Python"], (20, 50)),
        (["Python", "SQL", "LangChain", "FastAPI"], (60, 85)),
    ])
    def test_score_ranges(self, cv_skills, expected_range):
        score = compute_ats_score_for_role(cv_skills, "ai_engineer")
        assert expected_range[0] <= score <= expected_range[1]
```

### LinkedIn Engine

```python
# tests/unit/test_linkedin_engine.py

class TestTitleScorer:
    
    def test_weak_title_scores_low(self):
        scorer = TitleScorer()
        result = scorer.score("Analista SSR en BBVA", target_role="ai_engineer")
        assert result.score < 30
    
    def test_optimized_title_scores_high(self):
        scorer = TitleScorer()
        title = "AI Engineer | Analytics Engineer | Python · LangChain · SQL · GenAI"
        result = scorer.score(title, target_role="ai_engineer")
        assert result.score >= 80
    
    def test_title_too_long_penalized(self):
        scorer = TitleScorer()
        title = "A" * 221  # Supera el límite de LinkedIn
        result = scorer.score(title, target_role="ai_engineer")
        assert result.checks["length_ok"] is False
```

---

## Tests de integración

```python
# tests/integration/test_api_analyze.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
class TestCVAnalysis:
    
    async def test_analyze_cv_returns_score(self, client: AsyncClient, sample_cv_text):
        response = await client.post(
            "/api/v1/analyze/cv",
            json={"cv_text": sample_cv_text, "target_role": "ai_engineer"}
        )
        assert response.status_code == 200
        data = response.json()
        assert 0 <= data["ats_score"] <= 100
        assert "keyword_analysis" in data
        assert "recommendations" in data
    
    async def test_analyze_cv_with_invalid_role(self, client: AsyncClient, sample_cv_text):
        response = await client.post(
            "/api/v1/analyze/cv",
            json={"cv_text": sample_cv_text, "target_role": "invalid_role"}
        )
        assert response.status_code == 422
    
    async def test_analyze_cv_too_short(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/analyze/cv",
            json={"cv_text": "Too short", "target_role": "ai_engineer"}
        )
        assert response.status_code == 422
    
    async def test_rate_limit_applied(self, client: AsyncClient, sample_cv_text):
        for _ in range(10):
            await client.post("/api/v1/analyze/cv", ...)
        response = await client.post("/api/v1/analyze/cv", ...)
        assert response.status_code == 429
```

---

## Tests de LLM (con mocks)

```python
# Para tests de funciones que usan LLMs, mockeamos la respuesta
from unittest.mock import AsyncMock, patch

async def test_about_generation_structure():
    mock_llm_response = """
    Soy AI Engineer con experiencia en LangChain y FastAPI...
    [estructura correcta del About]
    """
    
    with patch("app.agents.content_creator.ChatAnthropic") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(
            return_value=MagicMock(content=mock_llm_response)
        )
        
        result = await generate_about(
            user_profile=sample_profile,
            target_role="ai_engineer"
        )
        
        assert len(result.variants) == 3
        assert all(len(v.text) >= 200 for v in result.variants)
```

---

## Cobertura objetivo

| Módulo | Target coverage |
|--------|----------------|
| `app/engine/ats.py` | 90% |
| `app/engine/linkedin.py` | 85% |
| `app/api/` | 80% |
| `app/crawler/` | 70% |
| `app/agents/` | 60% (mocked LLM) |

```bash
# Verificar cobertura mínima en CI
pytest --cov=app --cov-fail-under=75 tests/
```
