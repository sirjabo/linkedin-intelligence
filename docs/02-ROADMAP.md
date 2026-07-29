# 02 · Roadmap

## Horizonte: 12 meses

```
Q3 2025          Q4 2025          Q1 2026          Q2 2026
│                │                │                │
├─ Fase 1 ───────┤                │                │
│  MVP           │                │                │
│                ├─ Fase 2 ───────┤                │
│                │  Benchmark     │                │
│                │                ├─ Fase 3 ───────┤
│                │                │  Generación IA │
│                │                │                │
│                │                │         Fase 4 ┤
│                │                │         Jobs   │
│                │                │                ├─ Fase 5 ─
│                │                │                │  Radar
```

---

## Fase 1 — MVP (Semanas 1-8)

**Objetivo**: Tener un producto funcional que un usuario pueda usar para analizar su perfil.

### Sprint 1 (Sem 1-2): Infraestructura base
- [ ] Repositorio configurado (docs, estructura de carpetas, CI/CD básico)
- [ ] Docker Compose con PostgreSQL + Redis + pgvector
- [ ] FastAPI skeleton con health check
- [ ] Migraciones con Alembic
- [ ] Primera ingesta manual de ofertas (Indeed + LinkedIn scraping básico)

### Sprint 2 (Sem 3-4): Pipeline de datos
- [ ] Crawler de ofertas de trabajo (Indeed, Greenhouse)
- [ ] Normalización y almacenamiento de ofertas
- [ ] Extracción de skills desde ofertas con LLM
- [ ] Job de clasificación por rol y categoría

### Sprint 3 (Sem 5-6): CV Analyzer
- [ ] Endpoint `POST /analyze/cv`
- [ ] Parser de PDF con extracción de secciones
- [ ] ATS Score calculator
- [ ] Keyword gap analysis vs. rol objetivo
- [ ] Tests unitarios y de integración

### Sprint 4 (Sem 7-8): LinkedIn Analyzer + Frontend básico
- [ ] Endpoint `POST /analyze/linkedin`
- [ ] Profile Score calculator por sección
- [ ] Skills Radar endpoint `GET /market/skills/{role}`
- [ ] Frontend Next.js con formulario y visualización de resultados
- [ ] Deploy en staging

**Entregable Fase 1**: App funcional deployada, análisis de CV y Skills Radar operativos.

---

## Fase 2 — Benchmark (Semanas 9-16)

**Objetivo**: Dar contexto al usuario de dónde está parado vs. el mercado.

### Sprint 5-6: Profile Benchmark
- [ ] Scraping de perfiles públicos de LinkedIn (respetando ToS)
- [ ] Vectorización de perfiles con embeddings
- [ ] Endpoint de comparación y percentil
- [ ] Visualización del benchmark en frontend

### Sprint 7-8: Keyword Gap + Title Optimizer
- [ ] Análisis de frecuencia de keywords en perfiles top
- [ ] Endpoint `GET /optimize/title`
- [ ] Generador de variantes de título con LLM
- [ ] Dashboard de keyword gap

**Entregable Fase 2**: Dashboard de benchmark completo.

---

## Fase 3 — Generación con IA (Semanas 17-24)

**Objetivo**: Pasar de "qué cambiar" a "así queda cambiado".

### Sprint 9-10: AI About Writer
- [ ] RAG con perfiles top como contexto
- [ ] Endpoint `POST /generate/about`
- [ ] 3 variantes de About por usuario
- [ ] A/B testing de resultados

### Sprint 11-12: Content Calendar + Post Generator
- [ ] Generador de calendario de 30 días
- [ ] Post generator con tono personalizado
- [ ] Integración de tendencias actuales en el contenido

**Entregable Fase 3**: Suite completa de generación de contenido.

---

## Fase 4 — Job Tracking (Semanas 25-32)

**Objetivo**: Conectar el perfil del usuario con las oportunidades concretas.

### Sprint 13-14: Job Tracker
- [ ] CRUD de ofertas guardadas por usuario
- [ ] Fit score CV vs. oferta
- [ ] Gap analysis por oferta

### Sprint 15-16: Skills Roadmap
- [ ] Generación de roadmap personalizado
- [ ] Integración con recursos de aprendizaje
- [ ] Tracking de progreso del roadmap

**Entregable Fase 4**: Sistema de tracking y roadmap personalizado.

---

## Fase 5 — AI Radar (Semanas 33-48)

**Objetivo**: Inteligencia de mercado en tiempo real, diferenciador clave.

### Sprint 17-20: Nightly Pipeline
- [ ] Job scheduler con Celery/Celery Beat
- [ ] Procesamiento nocturno de miles de ofertas
- [ ] Detección de tendencias emergentes (algoritmo de variación porcentual)
- [ ] Sistema de alertas por email/webhook

### Sprint 21-24: Market Intelligence Dashboard
- [ ] Dashboard de tendencias en tiempo real
- [ ] Comparativa histórica de skills (gráficos de tiempo)
- [ ] Salarios por rol y región
- [ ] Ranking de empresas que contratan

**Entregable Fase 5**: Plataforma de inteligencia de mercado completa.

---

## Hitos clave

| Hito | Fecha estimada | Descripción |
|------|---------------|-------------|
| `v0.1-alpha` | Sem 4 | CV Analyzer funcional |
| `v0.2-alpha` | Sem 8 | MVP completo en staging |
| `v0.3-beta` | Sem 12 | Benchmark + Keyword Gap |
| `v0.5-beta` | Sem 16 | AI About Writer |
| `v1.0-rc` | Sem 24 | Producto completo Fase 1-3 |
| `v1.0` | Sem 32 | Lanzamiento público |
| `v2.0` | Sem 48 | AI Radar + SaaS completo |

---

## Deuda técnica planificada

Items que se harán intencionalmente simples en Fase 1 y se mejorarán después:

| Item | Implementación Fase 1 | Mejora futura |
|------|----------------------|---------------|
| Auth | JWT básico | OAuth2 + LinkedIn SSO |
| Scraping | Scripts Python simples | Framework de crawling con rotación de proxies |
| Embeddings | OpenAI Ada | Fine-tuned model + local inference |
| Cache | Redis simple | Cache inteligente con invalidación granular |
| Frontend | Next.js básico | Diseño UX profesional |
| Observability | Logs en consola | Datadog / OpenTelemetry |

---

## Decisiones por tomar

- [ ] ¿SaaS freemium o open source + servicios?
- [ ] ¿Hosting en AWS o Railway para el MVP?
- [ ] ¿Usar LinkedIn OAuth para análisis del perfil propio o solo texto/URL?
- [ ] ¿Modelo de embeddings propio o solo OpenAI?
