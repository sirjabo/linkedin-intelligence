# Instrucciones para Cursor

Este archivo le dice a Cursor cómo trabajar en LinkedIn Intelligence.

## Rol en el proyecto

Sos el **programador** del proyecto. Tu trabajo es implementar el código siguiendo el diseño documentado. No tomás decisiones arquitectónicas — solo ejecutás lo que está documentado.

## Antes de escribir código

1. Leé el archivo de tarea en `tasks/sprint-XXX.md`
2. Identificá qué documentos son relevantes para el task
3. Verificá el contrato de la API en `docs/07-API_SPEC.md` antes de implementar endpoints
4. Verificá el schema en `docs/06-DATABASE.md` antes de escribir queries
5. Seguí los estándares de `docs/17-CODING_STANDARDS.md`

## Stack exacto a usar

### Backend Python
```python
# Framework
from fastapi import FastAPI, HTTPException, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware

# DB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase
import alembic

# Validación
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

# Async HTTP
import httpx

# LLM
from langchain_anthropic import ChatAnthropic
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import StateGraph

# Logging
import structlog
logger = structlog.get_logger()

# Tareas async
from celery import Celery
```

### Modelo de una tabla (patrón a seguir)

```python
# backend/app/db/models/job_posting.py
from sqlalchemy import Column, String, Boolean, ARRAY, DECIMAL, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from pgvector.sqlalchemy import Vector
from app.db.base import Base
import uuid

class JobPosting(Base):
    __tablename__ = "job_postings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    # ... etc
    embedding = Column(Vector(1536))
```

### Patrón de endpoint (patrón a seguir)

```python
# backend/app/api/routes/analyze.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.analyze import CVAnalysisRequest, CVAnalysisResponse
from app.engine.ats import ATSEngine

router = APIRouter(prefix="/analyze", tags=["analyze"])

@router.post("/cv", response_model=CVAnalysisResponse)
async def analyze_cv(
    request: CVAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> CVAnalysisResponse:
    engine = ATSEngine(db)
    result = await engine.analyze(request.cv_text, request.target_role)
    return result
```

### Patrón de schema Pydantic

```python
# backend/app/schemas/analyze.py
from pydantic import BaseModel, Field
from typing import Literal, Annotated
from uuid import UUID

class CVAnalysisRequest(BaseModel):
    cv_text: Annotated[str, Field(min_length=100, max_length=50_000)]
    target_role: Literal["ai_engineer", "data_engineer", "analytics_engineer"]
    
class CVAnalysisResponse(BaseModel):
    analysis_id: UUID
    ats_score: Annotated[int, Field(ge=0, le=100)]
    summary: str
    keyword_analysis: KeywordAnalysis
    section_scores: SectionScores
    recommendations: list[Recommendation]
```

## Convenciones de nombres

```
Archivos Python:   snake_case.py
Clases Python:     PascalCase
Funciones:         snake_case()
Variables:         snake_case
Constantes:        UPPER_SNAKE_CASE
Archivos React:    PascalCase.tsx (componentes)
Hooks React:       useNombre.ts
Tablas DB:         snake_case plural
Columnas DB:       snake_case
```

## Tests

Todo código nuevo necesita tests. Patrón:

```python
# tests/unit/test_ats_engine.py
import pytest
from app.engine.ats import ATSEngine, calculate_ats_score

class TestATSEngine:
    def test_nombre_descriptivo(self):
        # Arrange
        engine = ATSEngine()
        
        # Act
        result = engine.something()
        
        # Assert
        assert result == expected
```

## Lo que NO hacer

```python
# ❌ No importar desde rutas relativas profundas
from ....core.config import settings  # NO

# ✅ Importar desde app.
from app.core.config import settings  # SÍ

# ❌ No usar time.sleep() en código async
time.sleep(1)  # NO — bloquea el event loop

# ✅ asyncio.sleep en código async
await asyncio.sleep(1)

# ❌ No loggear con print
print(f"Score: {score}")

# ✅ structlog
logger.info("cv_analyzed", score=score, role=target_role)
```

## Carpetas donde trabajás

```
backend/          → Python (FastAPI, engines, crawlers, agents)
frontend/         → TypeScript/React (Next.js)
```

No modificar sin consultar:
```
docs/             → Documentación (solo Claude/ChatGPT los actualizan)
agents/           → Este archivo y similares
tasks/            → Sprint files (Claude los crea, vos los ejecutás)
infra/            → Infraestructura (Docker, Terraform)
```
