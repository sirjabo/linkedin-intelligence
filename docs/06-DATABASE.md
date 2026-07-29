# 06 · Base de Datos

## Motor: PostgreSQL 16 + pgvector

### Por qué PostgreSQL

- ACID compliance para datos críticos de usuario
- `JSONB` para datos semi-estructurados (skills, metadata)
- `pgvector` elimina la necesidad de un vector DB externo en MVP
- Full-text search nativo (`tsvector`)
- `pg_trgm` para fuzzy matching de skills
- Extensible y bien soportado en AWS RDS

---

## Extensiones requeridas

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
```

---

## Esquema completo

### Tabla: `job_postings`

Ofertas de trabajo normalizadas.

```sql
CREATE TABLE job_postings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          VARCHAR(50) NOT NULL,        -- 'indeed' | 'greenhouse' | 'lever'
    external_id     VARCHAR(255) NOT NULL,
    url             TEXT,
    title           VARCHAR(255) NOT NULL,
    company         VARCHAR(255) NOT NULL,
    location        VARCHAR(255),
    country         VARCHAR(10),                  -- ISO code: 'AR', 'MX', 'ES'
    remote          BOOLEAN DEFAULT false,
    
    -- Categorización
    role_category   VARCHAR(100),                 -- 'ai_engineer', 'data_engineer', etc.
    seniority       VARCHAR(50),                  -- 'junior', 'mid', 'senior', 'staff', 'lead'
    
    -- Contenido
    description_raw     TEXT,
    description_clean   TEXT,
    skills              TEXT[],                   -- array de skills extraídas
    skills_jsonb        JSONB,                    -- skills categorizadas
    
    -- Compensación
    salary_min      DECIMAL(12,2),
    salary_max      DECIMAL(12,2),
    currency        VARCHAR(10),
    
    -- Vector
    embedding       vector(1536),                 -- OpenAI Ada / sentence-transformers
    
    -- Metadata
    posted_at       TIMESTAMPTZ,
    crawled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(source, external_id)
);

-- Índices
CREATE INDEX idx_job_postings_role ON job_postings(role_category);
CREATE INDEX idx_job_postings_country ON job_postings(country);
CREATE INDEX idx_job_postings_posted_at ON job_postings(posted_at DESC);
CREATE INDEX idx_job_postings_skills ON job_postings USING gin(skills);
CREATE INDEX idx_job_postings_embedding ON job_postings 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### Tabla: `skills_catalog`

Catálogo normalizado de skills con categorías.

```sql
CREATE TABLE skills_catalog (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL UNIQUE,
    slug            VARCHAR(255) NOT NULL UNIQUE,  -- 'langchain', 'python', 'aws'
    display_name    VARCHAR(255) NOT NULL,
    category        VARCHAR(100) NOT NULL,   -- ver categories abajo
    subcategory     VARCHAR(100),
    aliases         TEXT[],                  -- ['LangChain', 'lang-chain', 'langchain-python']
    is_active       BOOLEAN DEFAULT true,
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Categories: 'language', 'framework', 'cloud', 'database', 'ai_ml', 
--             'devops', 'tool', 'methodology', 'soft_skill', 'certification'
```

### Tabla: `skill_demand`

Demanda histórica de skills por rol (actualizada diariamente).

```sql
CREATE TABLE skill_demand (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    skill_id        UUID REFERENCES skills_catalog(id),
    role_category   VARCHAR(100) NOT NULL,
    country         VARCHAR(10),
    
    -- Métricas
    job_count       INTEGER NOT NULL,        -- # ofertas con esta skill esta semana
    total_jobs      INTEGER NOT NULL,        -- # total de ofertas para el rol
    frequency_pct   DECIMAL(5,2) NOT NULL,  -- job_count / total_jobs * 100
    
    -- Trending
    prev_week_pct   DECIMAL(5,2),
    change_pct      DECIMAL(5,2),           -- variación vs. semana anterior
    trend           VARCHAR(20),             -- 'rising', 'stable', 'declining'
    
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(skill_id, role_category, country, period_start)
);

CREATE INDEX idx_skill_demand_role_period ON skill_demand(role_category, period_start DESC);
CREATE INDEX idx_skill_demand_trending ON skill_demand(trend, change_pct DESC);
```

### Tabla: `profile_analyses`

Análisis de perfiles de LinkedIn realizados por usuarios.

```sql
CREATE TABLE profile_analyses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id),    -- NULL si anónimo
    
    -- Input
    profile_text    TEXT NOT NULL,
    target_role     VARCHAR(100) NOT NULL,
    
    -- Scores
    overall_score       SMALLINT CHECK (overall_score BETWEEN 0 AND 100),
    title_score         SMALLINT,
    about_score         SMALLINT,
    experience_score    SMALLINT,
    skills_score        SMALLINT,
    projects_score      SMALLINT,
    education_score     SMALLINT,
    
    -- Resultados
    skills_present      TEXT[],
    skills_missing      TEXT[],
    recommendations     JSONB,     -- lista de recomendaciones con prioridad
    
    -- Vector para búsqueda de similares
    embedding       vector(1536),
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabla: `cv_analyses`

Análisis de CVs (ATS Score).

```sql
CREATE TABLE cv_analyses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id),
    
    -- Input
    cv_text         TEXT NOT NULL,
    target_role     VARCHAR(100) NOT NULL,
    target_job_id   UUID REFERENCES job_postings(id),  -- si analiza vs. oferta específica
    
    -- ATS Score
    ats_score           SMALLINT CHECK (ats_score BETWEEN 0 AND 100),
    keyword_match_pct   DECIMAL(5,2),
    
    -- Resultados
    keywords_found      JSONB,     -- {keyword: count, weight: float}
    keywords_missing    JSONB,     -- keywords faltantes con peso
    section_scores      JSONB,     -- score por sección del CV
    suggestions         JSONB,     -- mejoras sugeridas
    
    -- Metadata
    cv_hash         VARCHAR(64),   -- SHA-256 del texto (para deduplication)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabla: `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    name            VARCHAR(255),
    target_role     VARCHAR(100),
    
    -- Subscription
    plan            VARCHAR(50) DEFAULT 'free',   -- 'free', 'pro', 'team'
    plan_expires_at TIMESTAMPTZ,
    
    -- LinkedIn
    linkedin_url    TEXT,
    linkedin_data   JSONB,   -- datos del perfil público (con consentimiento)
    
    -- Settings
    country         VARCHAR(10),
    language        VARCHAR(10) DEFAULT 'es',
    alerts_enabled  BOOLEAN DEFAULT true,
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabla: `trend_alerts`

Tendencias detectadas por el Nightly Radar.

```sql
CREATE TABLE trend_alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    skill_id        UUID REFERENCES skills_catalog(id),
    role_category   VARCHAR(100),
    country         VARCHAR(10),
    
    alert_type      VARCHAR(50),   -- 'rising_fast', 'new_skill', 'declining'
    change_pct      DECIMAL(5,2),
    period_days     INTEGER,       -- últimos N días
    message         TEXT,          -- "MCP creció 42% en ofertas de AI Engineer"
    
    detected_at     TIMESTAMPTZ DEFAULT NOW(),
    is_sent         BOOLEAN DEFAULT false
);
```

---

## Modelo entidad-relación simplificado

```
users ──────────────────────────────────────────┐
  │                                             │
  ├──< profile_analyses (user_id)              │
  │                                             │
  └──< cv_analyses (user_id)                  │
                                               │
job_postings >──────────< skill_demand        │
      │                        │              │
      │                   skills_catalog      │
      │                        │              │
      └── cv_analyses          └── trend_alerts
          (target_job_id)
```

---

## Migraciones

Las migraciones se manejan con Alembic.

```bash
# Crear una nueva migración
alembic revision --autogenerate -m "add trend_alerts table"

# Aplicar migraciones
alembic upgrade head

# Ver historial
alembic history

# Revertir última
alembic downgrade -1
```

Convención de nombres: `YYYYMMDD_descripcion_breve`

---

## Configuración de pgvector

```sql
-- Para tablas grandes, usar IVFFlat index
-- lists = sqrt(número de vectores)
CREATE INDEX ON job_postings 
    USING ivfflat (embedding vector_cosine_ops) 
    WITH (lists = 100);

-- Búsqueda de los 10 más similares
SELECT id, title, company,
       1 - (embedding <=> '[...]'::vector) AS similarity
FROM job_postings
WHERE role_category = 'ai_engineer'
ORDER BY embedding <=> '[...]'::vector
LIMIT 10;
```

---

## Backup y retención

| Tabla | Retención | Backup |
|-------|-----------|--------|
| job_postings | 12 meses | Diario |
| skill_demand | Indefinido | Diario |
| profile_analyses | 6 meses (anónimos: 30 días) | Diario |
| cv_analyses | 6 meses (anónimos: 24h) | Diario |
| users | Hasta baja de cuenta | Diario |
| trend_alerts | 3 meses | Semanal |
