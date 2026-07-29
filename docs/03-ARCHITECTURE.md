# 03 · Arquitectura del Sistema

## Visión general

LinkedIn Intelligence sigue una arquitectura de microservicios ligera, diseñada para evolucionar desde un monolito modular (Fase 1) hacia servicios separados (Fase 4+). El principio guía es: **no añadir complejidad hasta que el problema lo requiera**.

---

## Diagrama de arquitectura

```mermaid
graph TB
    subgraph External["Fuentes Externas"]
        LI["🔗 LinkedIn\n(datos públicos)"]
        IND["🔍 Indeed"]
        GHO["🌿 Greenhouse"]
        GH["💻 GitHub"]
        RDT["💬 Reddit/HN"]
        GT["📈 Google Trends"]
        SO["📊 Stack Overflow\nDev Survey"]
    end

    subgraph Crawlers["Crawler Layer"]
        JC["Job Crawler"]
        PC["Profile Crawler"]
        TC["Trends Crawler"]
    end

    subgraph ETL["ETL Pipeline"]
        NRM["Normalizer"]
        EXT["Skills Extractor\n(LLM)"]
        EMB["Embeddings\nService"]
    end

    subgraph Storage["Storage Layer"]
        PG[("PostgreSQL 16\n+ pgvector")]
        RD[("Redis\nCache")]
        S3["S3\nBlob Storage"]
    end

    subgraph AI["AI / ML Layer"]
        RAG["RAG Engine"]
        ATS["ATS Scorer"]
        PRF["Profile Analyzer"]
        GEN["Content Generator"]
        AGT["LangGraph\nAgents"]
        LLM["LLM\nClaude / GPT-4"]
    end

    subgraph Backend["Backend - FastAPI"]
        API["REST API\n/api/v1"]
        WS["WebSockets\n(live updates)"]
        WRK["Celery Workers\n(async jobs)"]
        SCH["Celery Beat\n(scheduler)"]
    end

    subgraph Frontend["Frontend - Next.js"]
        DASH["Dashboard"]
        ANA["Analyzer UI"]
        RAD["AI Radar"]
    end

    subgraph Infra["Infra"]
        DOC["Docker\nCompose"]
        GHA["GitHub\nActions CI/CD"]
        MON["Prometheus\n+ Grafana"]
    end

    External --> Crawlers
    Crawlers --> ETL
    ETL --> Storage
    Storage --> AI
    AI --> Backend
    Backend --> Frontend
    SCH --> Crawlers
    WRK --> ETL
    Storage --> Backend
    Backend --> MON
```

---

## Componentes principales

### 1. Crawler Layer

Responsable de obtener datos de fuentes externas.

| Crawler | Fuente | Frecuencia | Output |
|---------|--------|-----------|--------|
| `JobCrawler` | Indeed, Greenhouse, Lever | Cada 6 horas | job_postings |
| `ProfileCrawler` | LinkedIn público | Diario | profile_snapshots |
| `TrendsCrawler` | Google Trends, Reddit, HN | Diario | trend_signals |
| `SurveyCrawler` | Stack Overflow Dev Survey | Mensual | survey_data |

**Principios**:
- Rate limiting estricto (respeta `robots.txt`)
- User-agent identificado y honesto
- Exponential backoff en errores
- Solo datos públicamente accesibles

### 2. ETL Pipeline

Transforma los datos crudos en información estructurada.

```
Raw Data
   │
   ▼
Normalizer          → Limpieza, deduplicación, formato estándar
   │
   ▼
Skills Extractor    → LLM extrae skills + tecnologías de texto libre
   │
   ▼
Embeddings Service  → Vectoriza perfiles y ofertas para similarity search
   │
   ▼
PostgreSQL + pgvector
```

### 3. Storage Layer

#### PostgreSQL 16 + pgvector
Base de datos principal. Almacena:
- Ofertas de trabajo normalizadas
- Snapshots de perfiles
- Skills y categorías
- Vectores de embeddings (pgvector)
- Datos de usuarios
- Análisis y reportes generados

#### Redis
- Cache de resultados de análisis (TTL 1 hora)
- Rate limiting de la API
- Cola de tareas Celery
- Sessions de usuario

#### S3 (o equivalente)
- CVs cargados por usuarios (si el usuario da opt-in)
- Reportes generados en PDF
- Logs archivados

### 4. AI / ML Layer

#### RAG Engine
Recupera contexto relevante (mejores perfiles, ofertas similares) y lo usa para generar respuestas con LLM.

```
Query del usuario
      │
      ▼
Embedding de la query
      │
      ▼
Similarity search en pgvector
      │
      ▼
Top-K documentos relevantes
      │
      ▼
LLM (Claude / GPT-4) + contexto
      │
      ▼
Respuesta accionable
```

#### ATS Scorer
Algoritmo híbrido:
1. Extracción de keywords del rol objetivo desde la DB
2. Matching exacto + matching semántico
3. Ponderación por frecuencia de aparición en ofertas reales
4. Score normalizado 0-100

#### LangGraph Agents
Agentes con herramientas para tareas complejas:
- `ProfileAnalystAgent`: analiza perfil completo
- `CVOptimizerAgent`: optimiza CV para una oferta específica
- `TrendAnalystAgent`: interpreta señales de tendencias del mercado
- `ContentCreatorAgent`: genera posts y calendario de contenido

### 5. Backend — FastAPI

```
/api/v1/
├── /analyze
│   ├── POST /cv
│   └── POST /linkedin
├── /market
│   ├── GET /skills/{role}
│   ├── GET /trends
│   └── GET /companies
├── /optimize
│   ├── POST /title
│   ├── POST /about
│   └── POST /cv-for-job
├── /generate
│   ├── POST /about
│   ├── POST /post
│   └── POST /calendar
├── /jobs
│   ├── GET /
│   ├── POST /
│   └── GET /{id}/fit
└── /radar
    └── GET /daily
```

### 6. Frontend — Next.js 14

- App Router con Server Components
- Tailwind CSS + shadcn/ui
- Zustand para estado global
- React Query para data fetching
- Recharts para visualizaciones

---

## Flujos principales

### Flujo: Análisis de CV

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant LLM as LLM Service
    participant DB as PostgreSQL

    User->>FE: Sube PDF del CV
    FE->>API: POST /analyze/cv {file, role_target}
    API->>API: Extrae texto del PDF
    API->>DB: Obtiene top keywords para {role_target}
    API->>LLM: Extrae skills/exp del CV
    LLM-->>API: Estructurado {skills, experience, education}
    API->>API: Calcula ATS Score
    API->>DB: Guarda resultado (si user auth)
    API-->>FE: {ats_score, keyword_matches, gaps, suggestions}
    FE-->>User: Muestra dashboard con resultados
```

### Flujo: Nightly Radar

```mermaid
sequenceDiagram
    participant SCH as Celery Beat
    participant CRL as Crawlers
    participant ETL as ETL Pipeline
    participant DB as PostgreSQL
    participant AGT as Trend Agent
    participant USR as Users (email)

    SCH->>CRL: Trigger 02:00 UTC
    CRL->>CRL: Descarga nuevas ofertas
    CRL->>ETL: Raw job postings
    ETL->>ETL: Normaliza + extrae skills
    ETL->>DB: Inserta job_postings
    DB->>AGT: Calcula variación vs. semana anterior
    AGT->>AGT: Detecta skills +15% en 7 días
    AGT->>USR: Envía alertas personalizadas
```

---

## Decisiones arquitectónicas

Ver [19-DECISIONS.md](./19-DECISIONS.md) para el historial completo de ADRs.

| ADR | Decisión |
|-----|---------|
| ADR-001 | PostgreSQL + pgvector sobre Qdrant/Pinecone |
| ADR-002 | FastAPI sobre Django/Flask |
| ADR-003 | Next.js App Router sobre CRA/Vite |
| ADR-004 | Celery sobre RQ/Airflow para el MVP |
| ADR-005 | Claude como LLM primario con fallback a GPT-4 |

---

## Consideraciones de escalabilidad

### Fase 1 (MVP)
- Todo en un solo servidor (Docker Compose)
- PostgreSQL + pgvector en la misma instancia
- API y workers en procesos separados

### Fase 3+
- Separar crawlers en workers independientes
- Read replicas para PostgreSQL
- CDN para assets del frontend

### Fase 5 (AI Radar)
- Vector DB dedicado si pgvector llega a su límite
- Message queue (Kafka/SQS) para el pipeline de datos
- Autoscaling de workers según carga
