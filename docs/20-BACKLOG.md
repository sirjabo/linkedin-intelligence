# 20 · Backlog

Backlog priorizado. Los items están ordenados de mayor a menor prioridad dentro de cada sección.

**Leyenda**: 🔴 Crítico · 🟠 Alto · 🟡 Medio · 🟢 Bajo · 🔵 Idea futura

---

## En progreso

*(vacío — ver sprint activo en tasks/)*

---

## Listo para desarrollo (sprint 1)

| ID | Título | Prioridad | Tamaño | Descripción |
|----|--------|-----------|--------|-------------|
| B-001 | Docker Compose base | 🔴 | S | PostgreSQL + pgvector + Redis + API skeleton |
| B-002 | FastAPI skeleton + health check | 🔴 | S | Estructura de proyecto, middleware, logging |
| B-003 | Migraciones Alembic base | 🔴 | S | Setup + primeras tablas (job_postings, skills_catalog) |
| B-004 | Indeed Crawler v1 | 🔴 | M | Crawler básico de ofertas de trabajo |
| B-005 | Skills Extractor (LLM) | 🔴 | M | Extraer skills de descripciones con Claude Haiku |
| B-006 | ATS Score calculator | 🔴 | M | Algoritmo de matching keywords + score |
| B-007 | `POST /analyze/cv` endpoint | 🔴 | M | Endpoint completo con parser PDF |

---

## Backlog Fase 1 (MVP)

| ID | Título | Prioridad | Tamaño |
|----|--------|-----------|--------|
| B-008 | Greenhouse Crawler | 🟠 | S |
| B-009 | `GET /market/skills/{role}` endpoint | 🟠 | M |
| B-010 | `POST /analyze/linkedin` endpoint | 🟠 | L |
| B-011 | LinkedIn Engine — Title Scorer | 🟠 | M |
| B-012 | LinkedIn Engine — About Scorer | 🟠 | M |
| B-013 | Frontend: Landing page | 🟠 | M |
| B-014 | Frontend: CV Analyzer form + results | 🟠 | L |
| B-015 | Frontend: Skills Radar chart | 🟡 | M |
| B-016 | Auth: registro + login JWT | 🟡 | M |
| B-017 | Rate limiting middleware | 🟡 | S |
| B-018 | Deploy a Railway (staging) | 🟡 | S |
| B-019 | CI/CD básico con GitHub Actions | 🟡 | S |

---

## Backlog Fase 2 (Benchmark)

| ID | Título | Prioridad | Tamaño |
|----|--------|-----------|--------|
| B-020 | Profile embedding + indexing | 🟠 | M |
| B-021 | Profile Benchmark endpoint | 🟠 | L |
| B-022 | Keyword Gap Analyzer | 🟠 | M |
| B-023 | Title Optimizer (5 variantes) | 🟠 | M |
| B-024 | Frontend: Benchmark dashboard | 🟡 | L |
| B-025 | Lever Crawler | 🟡 | S |
| B-026 | Deduplication de job postings | 🟡 | S |

---

## Backlog Fase 3 (Generación IA)

| ID | Título | Prioridad | Tamaño |
|----|--------|-----------|--------|
| B-030 | RAG pipeline completo | 🟠 | L |
| B-031 | `POST /generate/about` con 3 variantes | 🟠 | M |
| B-032 | Post Generator para LinkedIn | 🟡 | M |
| B-033 | Content Calendar 30 días | 🟡 | L |
| B-034 | LangGraph ProfileAnalystAgent | 🟡 | L |
| B-035 | A/B testing de resultados | 🟢 | M |

---

## Backlog Fase 4 (Job Tracking)

| ID | Título | Prioridad | Tamaño |
|----|--------|-----------|--------|
| B-040 | Job Tracker CRUD | 🟠 | M |
| B-041 | Fit Score CV vs. oferta | 🟠 | M |
| B-042 | Skills Roadmap generator | 🟡 | L |
| B-043 | Application Optimizer | 🟡 | L |
| B-044 | Email alerts de nuevas ofertas | 🟢 | M |

---

## Backlog Fase 5 (AI Radar)

| ID | Título | Prioridad | Tamaño |
|----|--------|-----------|--------|
| B-050 | Nightly pipeline con Celery Beat | 🟠 | L |
| B-051 | Trend detection algorithm | 🟠 | M |
| B-052 | `GET /radar/daily` endpoint | 🟠 | M |
| B-053 | Market Intelligence Dashboard | 🟡 | XL |
| B-054 | Google Trends integration | 🟡 | M |
| B-055 | Reddit/HN signal crawler | 🟡 | M |
| B-056 | Salary benchmarks | 🟢 | L |
| B-057 | Personalized alert system (email/webhook) | 🟢 | L |

---

## Ideas futuras (sin compromiso)

| ID | Título | Descripción |
|----|--------|-------------|
| B-100 | LinkedIn OAuth integration | Analizar el perfil real del usuario con su consentimiento |
| B-101 | Chrome extension | Analizar perfiles de LinkedIn directamente en el browser |
| B-102 | Slack bot | Alertas de tendencias vía Slack |
| B-103 | Multi-idioma | Soporte para inglés + portugués |
| B-104 | API pública | Permitir que terceros consuman los datos de mercado |
| B-105 | Mobile app | React Native para tracking de ofertas |
| B-106 | Team plan | Dashboard compartido para equipos de reclutamiento |
| B-107 | Fine-tuned embedding model | Modelo propio entrenado en datos del sector tech latam |

---

## Bugs conocidos

*(ninguno todavía — el proyecto está en setup inicial)*

---

## Deuda técnica documentada

| Item | Descripción | Cuándo atacar |
|------|-------------|---------------|
| TD-001 | LinkedIn crawler muy conservador | Cuando tengamos más datos y podamos validar la estrategia | 
| TD-002 | Skills extractor usa LLM para cada oferta (caro) | Fase 3: fine-tune o few-shot más eficiente |
| TD-003 | No hay autoscaling de workers | Fase 4 cuando el volumen lo requiera |
| TD-004 | Cache de resultados sin invalidación inteligente | Fase 3 |
