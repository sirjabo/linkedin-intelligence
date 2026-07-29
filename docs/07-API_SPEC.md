# 07 · API Specification

## Base URL

```
Development:  http://localhost:8000/api/v1
Staging:      https://staging.linkedin-intelligence.com/api/v1
Production:   https://api.linkedin-intelligence.com/api/v1
```

## Autenticación

Bearer token JWT en el header `Authorization`:

```
Authorization: Bearer <token>
```

Los endpoints marcados con 🔓 son públicos (no requieren autenticación).  
Los marcados con 🔐 requieren autenticación.

---

## Endpoints

### Auth

#### `POST /auth/register` 🔓
Registrar nuevo usuario.

**Request**:
```json
{
  "email": "joaco@example.com",
  "name": "Joaco",
  "password": "securepassword",
  "target_role": "ai_engineer"
}
```

**Response 201**:
```json
{
  "user_id": "uuid",
  "email": "joaco@example.com",
  "token": "jwt_token"
}
```

#### `POST /auth/login` 🔓
**Request**:
```json
{
  "email": "joaco@example.com",
  "password": "securepassword"
}
```

**Response 200**:
```json
{
  "token": "jwt_token",
  "expires_at": "2025-08-29T00:00:00Z"
}
```

---

### Analyze

#### `POST /analyze/cv` 🔓
Analiza un CV y devuelve ATS Score + recomendaciones.

**Request** (multipart/form-data):
```
file: [PDF file]          # opcional si se usa cv_text
cv_text: string           # opcional si se usa file
target_role: string       # 'ai_engineer' | 'data_engineer' | 'analytics_engineer'
target_job_id: uuid       # opcional: comparar vs. oferta específica
```

**Response 200**:
```json
{
  "analysis_id": "uuid",
  "ats_score": 72,
  "target_role": "ai_engineer",
  "summary": "Tu CV tiene un buen nivel técnico pero le faltan keywords clave de IA.",
  "keyword_analysis": {
    "found": [
      {"keyword": "Python", "count": 4, "weight": 0.9},
      {"keyword": "SQL", "count": 2, "weight": 0.8}
    ],
    "missing": [
      {"keyword": "LangChain", "weight": 0.85, "suggested_section": "skills"},
      {"keyword": "RAG", "weight": 0.80, "suggested_section": "projects"},
      {"keyword": "FastAPI", "weight": 0.75, "suggested_section": "experience"}
    ]
  },
  "section_scores": {
    "contact": 100,
    "summary": 65,
    "experience": 78,
    "skills": 60,
    "education": 90,
    "projects": 55
  },
  "recommendations": [
    {
      "priority": 1,
      "section": "skills",
      "type": "add_keyword",
      "message": "Agregá 'LangChain' y 'LangGraph' a tu sección de skills",
      "impact": "high"
    },
    {
      "priority": 2,
      "section": "experience",
      "type": "rewrite_bullet",
      "original": "Desarrollé scripts de automatización en Python",
      "suggested": "Desarrollé pipelines de automatización en Python con integración a APIs REST, reduciendo el tiempo de procesamiento en 40%",
      "impact": "medium"
    }
  ],
  "processing_time_ms": 2340
}
```

#### `POST /analyze/linkedin` 🔓
Analiza un perfil de LinkedIn.

**Request**:
```json
{
  "profile_text": "string con el contenido del perfil",
  "linkedin_url": "https://linkedin.com/in/joaco",
  "target_role": "ai_engineer"
}
```

**Response 200**:
```json
{
  "analysis_id": "uuid",
  "overall_score": 68,
  "target_role": "ai_engineer",
  "section_scores": {
    "title": 45,
    "about": 70,
    "experience": 72,
    "skills": 60,
    "projects": 55,
    "education": 85
  },
  "title_analysis": {
    "current": "Analista SSR en BBVA",
    "issues": ["No menciona el rol objetivo", "No incluye tecnologías clave"],
    "suggested_variants": [
      "AI Engineer | Analytics Engineer | Python · LangChain · SQL · GenAI",
      "Analytics Engineer → AI Engineer | LLMs · RAG · Python · FastAPI",
      "Data & AI Engineer | LangChain · LangGraph · Python · SQL · Cloud"
    ]
  },
  "recommendations": [
    {
      "priority": 1,
      "section": "title",
      "message": "Reemplazá el título actual por uno que mencione AI Engineer + tecnologías clave",
      "impact": "very_high"
    }
  ]
}
```

---

### Market

#### `GET /market/skills/{role}` 🔓
Skills más demandadas para un rol en las últimas N semanas.

**Path params**: `role` = `ai_engineer` | `data_engineer` | `analytics_engineer` | `ml_engineer`

**Query params**:
```
weeks: int = 4          # período de análisis
country: str = "AR"     # ISO country code
limit: int = 50         # máximo de skills a devolver
```

**Response 200**:
```json
{
  "role": "ai_engineer",
  "country": "AR",
  "period": "2025-06-30/2025-07-28",
  "total_jobs_analyzed": 1240,
  "skills": [
    {
      "rank": 1,
      "name": "Python",
      "slug": "python",
      "category": "language",
      "frequency_pct": 94.2,
      "job_count": 1168,
      "trend": "stable",
      "change_pct": 1.2
    },
    {
      "rank": 2,
      "name": "LangChain",
      "slug": "langchain",
      "category": "ai_ml",
      "frequency_pct": 67.8,
      "job_count": 841,
      "trend": "rising",
      "change_pct": 22.4
    }
  ]
}
```

#### `GET /market/trends` 🔓
Tendencias del mercado en tiempo real.

**Query params**: `role`, `country`, `days=7`

**Response 200**:
```json
{
  "generated_at": "2025-07-28T08:00:00Z",
  "rising": [
    {
      "skill": "MCP Protocol",
      "change_pct": 42.0,
      "period_days": 7,
      "message": "MCP Protocol aumentó 42% en ofertas de AI Engineer esta semana"
    }
  ],
  "declining": [...],
  "new_skills": [...]
}
```

#### `GET /market/companies` 🔓
Empresas que más contratan para un rol.

---

### Optimize

#### `POST /optimize/title` 🔓
Genera variantes de título optimizadas.

**Request**:
```json
{
  "current_title": "Analista SSR en BBVA",
  "target_role": "ai_engineer",
  "skills": ["Python", "SQL", "LangChain", "n8n"],
  "years_experience": 5
}
```

**Response 200**:
```json
{
  "variants": [
    {
      "title": "AI Engineer | Analytics Engineer | Python · LangChain · SQL · GenAI",
      "score": 92,
      "keywords_included": ["AI Engineer", "Python", "LangChain"],
      "rationale": "Menciona el rol objetivo primero, incluye 3 de las 5 skills más buscadas"
    }
  ]
}
```

#### `POST /optimize/cv-for-job` 🔐
Optimiza CV para una oferta específica.

---

### Generate

#### `POST /generate/about` 🔐
Genera versiones del About de LinkedIn con IA.

**Request**:
```json
{
  "name": "Joaco",
  "current_role": "Analytics Engineer en BBVA",
  "target_role": "AI Engineer",
  "skills": ["Python", "SQL", "LangChain", "LangGraph", "n8n", "FastAPI"],
  "experience_summary": "5 años en analytics y data engineering, experiencia en banking y marketing analytics",
  "tone": "professional"
}
```

**Response 200**:
```json
{
  "variants": [
    {
      "style": "technical",
      "text": "AI Engineer y Analytics Engineer con 5 años de experiencia...",
      "keywords_included": [...],
      "word_count": 120
    },
    {
      "style": "narrative", 
      "text": "...",
      "keywords_included": [...],
      "word_count": 135
    },
    {
      "style": "results_focused",
      "text": "...",
      "keywords_included": [...],
      "word_count": 110
    }
  ]
}
```

#### `POST /generate/post` 🔐
Genera publicación para LinkedIn.

#### `POST /generate/calendar` 🔐
Genera calendario de 30 días de publicaciones.

---

### Radar

#### `GET /radar/daily` 🔓
Resumen diario del AI Radar.

**Response 200**:
```json
{
  "date": "2025-07-28",
  "highlights": [
    "MCP Protocol creció 42% en ofertas de AI Engineer esta semana",
    "LangGraph superó a CrewAI en menciones por primera vez",
    "Las ofertas de AI Engineer en Argentina aumentaron 18% vs. el mes anterior"
  ],
  "top_rising": [...],
  "top_declining": [...],
  "new_companies_hiring": [...]
}
```

---

## Paginación

Todos los endpoints de lista usan cursor-based pagination:

```
GET /jobs?cursor=<opaque_cursor>&limit=20
```

**Response**:
```json
{
  "data": [...],
  "pagination": {
    "cursor": "next_cursor_value",
    "has_more": true,
    "total": 1240
  }
}
```

---

## Códigos de error

| Código | Significado |
|--------|------------|
| 400 | Parámetros inválidos |
| 401 | No autenticado |
| 403 | Sin permisos |
| 404 | Recurso no encontrado |
| 422 | Error de validación (Pydantic) |
| 429 | Rate limit superado |
| 500 | Error interno |

**Formato de error**:
```json
{
  "error": {
    "code": "INVALID_ROLE",
    "message": "El rol 'foo' no es válido. Roles soportados: ai_engineer, data_engineer...",
    "docs_url": "https://docs.linkedin-intelligence.com/errors/INVALID_ROLE"
  }
}
```

---

## Rate Limits

| Plan | Requests/min | Análisis de CV/día |
|------|-------------|-------------------|
| Free | 30 | 3 |
| Pro | 120 | 20 |
| Team | 500 | ilimitado |
