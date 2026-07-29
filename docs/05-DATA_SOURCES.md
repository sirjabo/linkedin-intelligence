# 05 · Fuentes de Datos

## Estrategia general

El sistema usa múltiples fuentes complementarias para construir una imagen completa del mercado laboral tech. Ninguna fuente por sí sola es suficiente. La estrategia prioriza:

1. **APIs oficiales** cuando existen y son accesibles.
2. **Datos públicos** respetando robots.txt y Terms of Service.
3. **Datasets abiertos** (surveys, archivos públicos).
4. **Terceros** para datos que no podemos obtener directamente.

---

## Fuentes de ofertas de trabajo

### Indeed

| Atributo | Valor |
|---------|-------|
| Tipo | Scraping de datos públicos |
| Frecuencia | Cada 6 horas |
| Cobertura | Argentina, México, España, Colombia, Chile, Global |
| Datos obtenidos | Título, empresa, descripción, skills, ubicación, salario (cuando está disponible), fecha |
| Limitaciones | Rate limits agresivos, requiere rotación de user-agents |
| Consideraciones legales | Indeed public data, no login requerido |

**Estrategia de ingestión**:
```
1. Search por role + location (ej. "AI Engineer" + "Argentina")
2. Paginación hasta 50 páginas por búsqueda
3. Deduplicación por job_id
4. Extracción de skills con LLM (descripción → skills estructuradas)
5. Almacenamiento en job_postings table
```

### Greenhouse

| Atributo | Valor |
|---------|-------|
| Tipo | API pública (Job Board API) |
| Endpoint | `https://boards-api.greenhouse.io/v1/boards/{company}/jobs` |
| Autenticación | No requerida |
| Frecuencia | Diaria |
| Cobertura | Empresas tech globales (Mercado Libre, Despegar, etc.) |

Empresas tech latam conocidas en Greenhouse:
- `mercadolibre`
- `despegar`
- `ualá`
- `lemon`
- `bitso`

### Lever

| Atributo | Valor |
|---------|-------|
| Tipo | API pública |
| Endpoint | `https://api.lever.co/v0/postings/{company}?mode=json` |
| Frecuencia | Diaria |
| Cobertura | Startups tech de Latam y EEUU |

### LinkedIn (datos públicos)

| Atributo | Valor |
|---------|-------|
| Tipo | Scraping con Playwright (solo páginas públicas) |
| Frecuencia | Nocturna (02:00 UTC) |
| Cobertura | Ofertas públicas + perfiles públicos |
| Limitaciones | Muy restrictivo, rate limits estrictos, ToS sensible |
| Consideraciones | Solo perfiles/ofertas 100% públicos, sin login |

**Importante**: LinkedIn es la fuente más valiosa pero la más restrictiva. El approach es conservador:
- Solo páginas sin autenticación
- 1 request cada 3-5 segundos con jitter
- User-agent de browser real
- No almacenamos PII de terceros
- Solo metadata agregada (skills frecuencia, no perfiles individuales)

---

## Fuentes de tendencias tecnológicas

### Google Trends

| Atributo | Valor |
|---------|-------|
| API | `pytrends` (unofficial API) |
| Frecuencia | Semanal |
| Datos | Índice de interés de búsqueda por término (0-100) |
| Uso | Detectar crecimiento/declive de tecnologías |

Queries de ejemplo:
```python
TECH_KEYWORDS = [
    "LangChain", "LangGraph", "MCP protocol", "RAG AI",
    "n8n automation", "FastAPI Python", "pgvector",
    "AI Engineer", "Analytics Engineer",
]
```

### Stack Overflow Developer Survey

| Atributo | Valor |
|---------|-------|
| Tipo | Dataset público anual |
| URL | `https://survey.stackoverflow.co/` |
| Frecuencia | Anual (con análisis mensual del dataset) |
| Datos | Tecnologías más usadas, salarios, herramientas |

### Reddit / Hacker News

| Atributo | Valor |
|---------|-------|
| Reddit API | `praw` (Python Reddit API Wrapper) |
| HN API | `https://hacker-news.firebaseio.com/v0/` (oficial) |
| Frecuencia | Diaria |
| Subreddits | r/MachineLearning, r/datascience, r/AIEngineering, r/cscareerquestions |
| Uso | Detectar tecnologías emergentes antes de que aparezcan en ofertas |

### GitHub

| Atributo | Valor |
|---------|-------|
| API | GitHub REST API v3 (autenticada) |
| Rate limit | 5.000 requests/hora |
| Datos | Topics de repos, lenguajes, README keywords |
| Uso | Detectar ecosistema de herramientas que usan AI Engineers |

Queries de ejemplo:
```python
# Buscar repos con topics de AI Engineering
topics = ["langchain", "langgraph", "rag", "llm", "ai-agents"]
# Analizar README y descripción para extraer tech stack
```

---

## Datos de usuarios (con consentimiento)

Cuando el usuario se registra y da opt-in explícito:

| Dato | Almacenamiento | Uso |
|------|---------------|-----|
| CV en PDF | S3 (encriptado) | Análisis de perfil |
| URL de LinkedIn | PostgreSQL | Análisis de perfil |
| Rol objetivo | PostgreSQL | Personalización |
| Historial de análisis | PostgreSQL | Tracking de progreso |

**Nunca** se almacena:
- Contraseñas de plataformas externas
- Tokens de acceso de terceros (más de 24h)
- Datos de terceros con PII identificable

---

## Pipeline de datos

```
Crawlers (cada fuente tiene su propio crawler)
       │
       ▼
Raw Data Store (PostgreSQL: tabla raw_jobs, raw_profiles)
       │
       ▼
Deduplication (hash de contenido)
       │
       ▼
Normalizer (formato estándar: JobPosting, ProfileSnapshot)
       │
       ▼
Skills Extractor (LLM → structured skills list)
       │
       ▼
Categorizer (skills → categorías: language, framework, cloud, etc.)
       │
       ▼
Embeddings Generator (texto → vector float[1536])
       │
       ▼
PostgreSQL + pgvector (datos listos para análisis)
```

---

## Esquema de datos de entrada

```python
class RawJobPosting(BaseModel):
    source: str                    # "indeed" | "greenhouse" | "lever"
    external_id: str               # ID único en la fuente
    url: str
    title: str
    company: str
    location: str
    description: str
    raw_html: str | None
    crawled_at: datetime
    
class NormalizedJobPosting(BaseModel):
    id: UUID
    source: str
    external_id: str
    title: str
    company: str
    location: str
    role_category: str             # "ai_engineer" | "data_engineer" | etc.
    seniority: str                 # "junior" | "mid" | "senior" | "staff"
    skills: list[str]              # extraídas por LLM
    skills_structured: SkillsMap   # categorías
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    remote: bool
    description_clean: str
    embedding: list[float]         # pgvector
    created_at: datetime
    updated_at: datetime
```

---

## Calidad de datos

### Métricas de calidad monitoreadas
- **Completeness**: % de registros con title, company, description completos
- **Freshness**: edad promedio de los datos en la DB
- **Deduplication rate**: % de duplicados detectados y eliminados
- **Skills extraction accuracy**: validado manualmente con sample semanal

### Alertas automáticas
- Si una fuente no ingestó datos en > 12 horas → alerta
- Si el % de duplicados supera 30% → revisar hash logic
- Si skills extraction tarda > 5 segundos por oferta → revisar LLM
