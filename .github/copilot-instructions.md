# GitHub Copilot Instructions — LinkedIn Intelligence

## Proyecto

LinkedIn Intelligence es una plataforma de inteligencia de mercado laboral que analiza ofertas de trabajo y perfiles de LinkedIn para generar recomendaciones de optimización de perfil.

## Stack

- **Backend**: Python 3.11, FastAPI 0.111, SQLAlchemy 2.0 async, Pydantic v2, Celery
- **DB**: PostgreSQL 16 + pgvector, Redis
- **AI**: LangChain 0.2, LangGraph 0.1, Anthropic Claude (primario), OpenAI (fallback)
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, shadcn/ui
- **Testing**: pytest, pytest-asyncio, httpx

## Patrones que seguir

### Endpoints FastAPI
```python
@router.post("/analyze/cv", response_model=CVAnalysisResponse)
async def analyze_cv(
    request: CVAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> CVAnalysisResponse:
    engine = ATSEngine(db)
    return await engine.analyze(request.cv_text, request.target_role)
```

### Modelos SQLAlchemy
```python
class JobPosting(Base):
    __tablename__ = "job_postings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    embedding = Column(Vector(1536))  # pgvector
```

### Logging
```python
import structlog
logger = structlog.get_logger()
logger.info("event_name", key=value, key2=value2)
```

## Reglas

1. Type hints obligatorios en todas las funciones
2. Async/await para operaciones de I/O
3. Pydantic models (no dicts crudos) para datos estructurados
4. structlog para logging (no print, no logging.info con f-strings)
5. SQLAlchemy ORM o queries parametrizadas (nunca f-strings con SQL)
6. Secretos en .env, nunca hardcodeados

## Documentación de referencia

- Arquitectura: `docs/03-ARCHITECTURE.md`
- Schema DB: `docs/06-DATABASE.md`
- API: `docs/07-API_SPEC.md`
- ATS Engine: `docs/09-ATS_ENGINE.md`
- LinkedIn Engine: `docs/10-LINKEDIN_ENGINE.md`
- Coding standards: `docs/17-CODING_STANDARDS.md`
