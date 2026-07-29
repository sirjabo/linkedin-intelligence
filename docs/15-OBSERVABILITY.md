# 15 · Observabilidad

## Los tres pilares

| Pilar | Herramienta | Propósito |
|-------|------------|-----------|
| **Logs** | structlog + Sentry | Qué pasó y cuándo |
| **Métricas** | Prometheus + Grafana | Cuánto y qué tan rápido |
| **Trazas** | LangSmith | Flujo de operaciones LLM/Agents |

---

## Logging

### Configuración

```python
# app/core/logging.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if DEV else structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()
```

### Convenciones de logging

```python
# ✅ Correcto: structured, con contexto
logger.info(
    "cv_analysis_completed",
    analysis_id=str(analysis.id),
    ats_score=analysis.ats_score,
    target_role=analysis.target_role,
    duration_ms=duration_ms,
    keywords_found=len(analysis.keywords_found),
)

# ❌ Incorrecto: string sin estructura
logger.info(f"Analysis {id} completed with score {score}")
```

### Qué loggear (y qué NO)

**Loggear**:
- Inicio y fin de cada request (con duration)
- Errores con stack trace
- Resultados de crawlers (items, duration, errors)
- Operaciones de DB lentas (> 1 segundo)
- Llamadas a LLMs (prompt tokens, completion tokens, model, duration)

**NO loggear**:
- API keys ni secrets
- Contenido completo del CV del usuario (solo metadata)
- Passwords
- Tokens JWT completos

---

## Métricas

### Métricas de aplicación

```python
# app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# API
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Análisis
cv_analyses_total = Counter('cv_analyses_total', 'Total CV analyses', ['target_role'])
ats_score_distribution = Histogram(
    'ats_score',
    'Distribution of ATS scores',
    buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)

# Crawlers
crawler_items_total = Counter(
    'crawler_items_total',
    'Items crawled',
    ['source', 'status']   # status: new | duplicate | error
)

crawler_duration_seconds = Histogram(
    'crawler_run_duration_seconds',
    'Duration of crawler runs',
    ['source']
)

# LLM
llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['model', 'type']   # type: prompt | completion
)

llm_cost_usd = Counter(
    'llm_cost_usd_total',
    'Total LLM cost in USD',
    ['model']
)

# DB
db_job_postings_total = Gauge('db_job_postings_total', 'Total job postings in DB')
db_latest_crawl_age_hours = Gauge(
    'db_latest_crawl_age_hours',
    'Hours since last successful crawl',
    ['source']
)
```

### Dashboard Grafana

Panels clave para el dashboard principal:

1. **Request rate** — requests/segundo por endpoint
2. **Error rate** — % de requests con error 5xx
3. **P95 latency** — latencia p95 por endpoint
4. **ATS Score distribution** — histograma de scores generados
5. **Crawler health** — último crawl exitoso por fuente
6. **LLM spend** — gasto diario en APIs de LLM
7. **DB size** — crecimiento de job_postings por día
8. **Active users** — usuarios únicos por hora

---

## Alertas

### Alertas críticas (PagerDuty/email inmediato)

```yaml
# Prometheus alerting rules

- alert: APIDown
  expr: up{job="linkedin-intelligence-api"} == 0
  for: 1m
  annotations:
    summary: "API is down"

- alert: HighErrorRate
  expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "Error rate > 5% for 5 minutes"

- alert: DatabaseDown
  expr: pg_up == 0
  for: 1m
  
- alert: CrawlerStale
  expr: db_latest_crawl_age_hours{source="indeed"} > 12
  for: 0m
  annotations:
    summary: "Indeed crawler hasn't run in 12+ hours"
```

### Alertas de negocio (email diario)

- LLM spend > $20/día
- 0 análisis en las últimas 2 horas (posible issue de UX)
- ATS Score promedio cayó >10 puntos (posible regression)

---

## Health Check

```python
# app/api/health.py

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks = {}
    
    # DB connectivity
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    
    # Redis connectivity
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    
    # Data freshness
    latest_job = await db.scalar(
        select(func.max(JobPosting.crawled_at))
    )
    age_hours = (datetime.utcnow() - latest_job).total_seconds() / 3600
    checks["data_freshness_hours"] = round(age_hours, 1)
    checks["data_fresh"] = age_hours < 12
    
    overall = "ok" if all(v == "ok" for v in checks.values() if isinstance(v, str)) else "degraded"
    
    return {
        "status": overall,
        "checks": checks,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }
```

---

## Error Tracking con Sentry

```python
# app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    environment=settings.ENVIRONMENT,
    integrations=[
        FastApiIntegration(transaction_style="endpoint"),
        SqlalchemyIntegration(),
    ],
    traces_sample_rate=0.1,        # 10% de requests trackeados
    profiles_sample_rate=0.01,     # 1% profiling
    send_default_pii=False,        # No enviar PII a Sentry
)
```

---

## Runbooks

### "Los crawlers no corrieron"

1. Verificar `db_latest_crawl_age_hours` en Grafana
2. Revisar logs de Celery Beat: `docker logs beat`
3. Revisar logs del worker específico: `docker logs worker`
4. Verificar conectividad a la fuente desde el worker
5. Relanzar manualmente: `celery -A app.worker call crawler.tasks.run_indeed`

### "La API está lenta (P95 > 5s)"

1. Identificar el endpoint lento en Grafana
2. Revisar si hay queries de DB lentas en logs
3. Verificar si el pool de conexiones de DB está saturado
4. Revisar métricas de LLM (si la latencia viene del LLM)
5. Revisar uso de CPU/memoria del container

### "El ATS Score parece incorrecto"

1. Verificar que `skill_demand` tiene datos recientes (< 7 días)
2. Verificar que el Skills Extractor del ETL corrió recientemente
3. Tomar una muestra manual y comparar con el score calculado
4. Si la correlación cayó, relanzar la recalibración de pesos
