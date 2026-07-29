# 19 · Architecture Decision Records (ADRs)

Las decisiones arquitectónicas importantes se documentan aquí para que cualquier colaborador (humano o IA) entienda el contexto y no deshaga decisiones deliberadas.

**Formato**: Cada ADR tiene contexto, decisión, y consecuencias.

---

## ADR-001: PostgreSQL + pgvector en lugar de Pinecone/Qdrant

**Fecha**: 2025-07  
**Estado**: Aceptado

### Contexto

El sistema necesita almacenar y consultar vectores de embeddings para:
- Búsqueda de similitud entre CVs/perfiles y ofertas de trabajo
- RAG pipeline: recuperar contexto relevante para el LLM
- Profile benchmark: encontrar perfiles similares

Las opciones eran:
1. **Pinecone** (SaaS managed)
2. **Qdrant** (open source, self-hosted)
3. **pgvector** (extensión de PostgreSQL)
4. **Weaviate** (open source)

### Decisión

Usar **pgvector** como extensión de PostgreSQL.

### Razones

1. **Simplicidad operativa**: Ya usamos PostgreSQL. Agregar una extensión no suma un servicio más.
2. **Costo**: pgvector es gratuito. Pinecone tiene costos significativos a escala.
3. **Joins nativos**: Con pgvector podemos hacer `SELECT job_postings.*, 1 - (embedding <=> $1) AS sim FROM job_postings WHERE role = 'ai_engineer'` en una sola query. Con Pinecone necesitaríamos dos round-trips.
4. **Volumen MVP**: Para el MVP (<1M vectores), pgvector con `ivfflat` index tiene performance más que suficiente.

### Consecuencias

- Si escalamos a >10M vectores, puede ser necesario migrar a Qdrant.
- El performance de queries vectoriales depende del hardware de PostgreSQL.
- Monitorear: si las queries vectoriales superan 200ms consistentemente, evaluar migración.

---

## ADR-002: FastAPI en lugar de Django / Flask

**Fecha**: 2025-07  
**Estado**: Aceptado

### Contexto

Necesitamos un framework para la API REST del backend.

### Decisión

**FastAPI**

### Razones

1. **Async nativo**: Las operaciones de I/O (DB, LLM calls, HTTP) se benefician del async.
2. **Tipado con Pydantic**: Validación automática, docs OpenAPI generados, errores descriptivos.
3. **Performance**: Benchmarks consistentemente mejores que Flask/Django para I/O bound.
4. **Ecosistema IA**: SQLAlchemy async, LangChain, todas las librerías de IA son compatibles.
5. **Django sería overkill**: Django ORM, Admin, templates — nada de esto necesitamos.

### Consecuencias

- Requiere familiaridad con async/await (no hay opción síncrona limpia).
- Algunas librerías legacy no son async-compatible (pocas en nuestro stack).

---

## ADR-003: Next.js 14 App Router en lugar de otras opciones

**Fecha**: 2025-07  
**Estado**: Aceptado

### Decisión

**Next.js 14 con App Router**

### Razones

1. **SSR/SSG**: El dashboard público y el landing necesitan SSR para SEO y performance.
2. **App Router**: Layouts anidados, loading states, error boundaries — todo resuelto.
3. **TypeScript-first**: Mejor que Vite/CRA para proyectos con tipos.
4. **shadcn/ui**: El ecosistema de componentes más maduro existe para Next.js/React.

### Consecuencias

- App Router tiene curva de aprendizaje vs Pages Router.
- Bundle más pesado que Vite para SPAs puras.

---

## ADR-004: Celery + Redis en lugar de Airflow / Prefect

**Fecha**: 2025-07  
**Estado**: Aceptado

### Contexto

Necesitamos un sistema para:
1. Crawlers programados (cada 6 horas, cada noche)
2. Jobs de ETL (normalización, extracción de skills)
3. Procesamiento async de análisis de CV (para no bloquear la API)

### Decisión

**Celery + Celery Beat + Redis**

### Razones

1. **Simplicidad**: Airflow tiene overhead operacional enorme (scheduler, webserver, DB propia).
2. **Integración Python**: Celery es Python nativo, se integra naturalmente con FastAPI.
3. **Redis ya está**: Redis es el broker y ya lo usamos para cache.
4. **Volumen MVP**: Para <100 tasks/hora, Celery es más que suficiente.

### Trade-offs

- Airflow tiene mejor UI de monitoreo de DAGs.
- Prefect tiene mejor manejo de dependencias entre tasks.
- Si el pipeline ETL crece mucho en complejidad, evaluar Prefect.

---

## ADR-005: Claude como LLM primario con fallback a GPT-4o

**Fecha**: 2025-07  
**Estado**: Aceptado

### Contexto

El sistema usa LLMs para:
- Extracción de skills de texto libre (bulk)
- Análisis de perfiles (razonamiento complejo)
- Generación de recomendaciones y contenido

### Decisión

- **Primario**: `claude-sonnet-5` para tareas de análisis y generación
- **Bulk/barato**: `claude-haiku-4-5` para extracción de skills en ETL masivo
- **Fallback**: `gpt-4o` si Anthropic API tiene outage

### Razones

1. **Calidad de escritura**: Claude produce texto más natural y profesional en español.
2. **Instrucciones largas**: Claude maneja mejor prompts con muchas instrucciones (perfecto para análisis de perfiles).
3. **Context window**: 200K tokens en Claude Sonnet — útil para analizar CVs + contexto de mercado juntos.

### Consecuencias

- Dependencia de Anthropic. Mitigado con fallback a GPT-4o.
- Monitorear: si la calidad del fallback es notablemente peor, invertir en redundancia activa.

---

## ADR-006: Railway para el MVP, AWS para producción

**Fecha**: 2025-07  
**Estado**: Aceptado

### Decisión

- **MVP/Fase 1**: Railway
- **Producción/Fase 4+**: AWS (ECS, RDS, ElastiCache)

### Razones Railway para MVP

1. Deploy con un comando, sin configuración de infraestructura.
2. PostgreSQL y Redis managed sin ops overhead.
3. Gratis hasta cierto uso, luego $20-50/mes — ideal para MVP.
4. CI/CD integrado con GitHub.

### Razones AWS para producción

1. SLA enterprise (99.9% uptime en RDS).
2. Autoscaling de workers según carga.
3. VPC para aislamiento de red.
4. Más opciones de instancias para workloads de ML.

### Consecuencias

- Migración de Railway a AWS en Fase 4 requiere trabajo (2-3 sprints).
- Los Dockerfiles son los mismos — solo cambia la plataforma de hosting.
