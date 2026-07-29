# 21 · Glosario

## Términos del dominio

**ATS (Applicant Tracking System)**  
Software usado por empresas para gestionar candidatos. Filtra CVs automáticamente por keywords antes de que un humano lo vea. El 75% de los CVs no pasan este filtro.

**ATS Score**  
Métrica 0-100 que estima la probabilidad de que un CV pase los filtros ATS de un sistema para un rol objetivo específico.

**Profile Score**  
Métrica 0-100 que evalúa la calidad y optimización de un perfil de LinkedIn para aparecer en búsquedas de recruiters.

**Keyword Gap**  
Diferencia entre las keywords que tiene el perfil/CV del usuario y las keywords que tienen los mejores perfiles/ofertas para el rol objetivo.

**Skill Demand**  
Frecuencia con la que una skill aparece en ofertas de trabajo para un rol específico, expresada como porcentaje (ej: "Python aparece en el 94% de las ofertas de AI Engineer").

**AI Radar**  
Feature que detecta skills y tecnologías que aumentaron su presencia en el mercado laboral en los últimos días/semanas. Corre automáticamente cada noche.

**Role Category**  
Clasificación estandarizada de roles usada internamente. Valores: `ai_engineer`, `data_engineer`, `analytics_engineer`, `ml_engineer`.

**Seniority**  
Nivel de experiencia requerido en una oferta. Valores: `junior`, `mid`, `senior`, `staff`, `lead`, `principal`.

**Trending**  
Descripción de la variación semanal de una skill. Valores: `rising` (+>10%), `stable` (±10%), `declining` (<-10%).

---

## Términos técnicos

**pgvector**  
Extensión de PostgreSQL que permite almacenar y consultar vectores de embeddings. Permite hacer similarity search directamente en la base de datos sin un servicio externo.

**Embedding**  
Representación vectorial de un texto en un espacio de alta dimensión. Textos semánticamente similares tienen embeddings cercanos. Se usa para similarity search y RAG.

**RAG (Retrieval-Augmented Generation)**  
Técnica que combina búsqueda de documentos relevantes (retrieval) con generación de texto con LLM. Permite responder preguntas con información actualizada que el LLM no conoce de su entrenamiento.

**Similarity Search**  
Búsqueda de documentos similares a una query usando distancia entre vectores de embeddings. En este proyecto se usa cosine similarity.

**LangGraph**  
Framework para construir agentes de IA con flujos de trabajo complejos y estado. Permite definir grafos de nodos (pasos) con condiciones y ciclos.

**Celery**  
Sistema de colas de tareas para Python. Permite ejecutar funciones de forma asíncrona (en workers separados) o programada (con Celery Beat).

**Celery Beat**  
Componente de Celery que ejecuta tareas en schedule (cron-like). Se usa para los crawlers nocturnos.

**IVFFlat Index**  
Tipo de índice aproximado para búsqueda vectorial en pgvector. Permite búsquedas más rápidas en tablas grandes a cambio de menor precisión exacta.

**Cross-encoder**  
Modelo que toma dos textos como input y produce un score de relevancia. Más preciso que los embeddings para reranking, pero más lento.

**Conventional Commits**  
Convención de formato para mensajes de commit: `tipo(scope): descripción`. Tipos: feat, fix, docs, refactor, test, chore.

**ADR (Architecture Decision Record)**  
Documento que captura una decisión de arquitectura importante: contexto, opciones consideradas, decisión tomada y consecuencias.

---

## Roles del mercado laboral (clasificación interna)

| Slug interno | Roles equivalentes |
|-------------|-------------------|
| `ai_engineer` | AI Engineer, LLM Engineer, GenAI Engineer, Applied AI Engineer |
| `data_engineer` | Data Engineer, ETL Engineer, Platform Engineer (data) |
| `analytics_engineer` | Analytics Engineer, Data Analyst (senior), BI Engineer |
| `ml_engineer` | ML Engineer, MLOps Engineer, Machine Learning Engineer |
