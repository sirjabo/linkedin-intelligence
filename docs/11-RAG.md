# 11 · RAG — Retrieval-Augmented Generation

## ¿Por qué RAG?

Los LLMs tienen conocimiento hasta su fecha de corte de entrenamiento. LinkedIn Intelligence necesita responder preguntas con datos de mercado actualizados diariamente:

- "¿Qué skills están creciendo esta semana para AI Engineer?"
- "¿Cómo está redactado el About de quienes trabajan en Mercado Libre hoy?"
- "¿Qué tecnologías mencionan las últimas 100 ofertas de Data Engineer en Argentina?"

Para esto, el LLM necesita contexto de nuestra base de datos. RAG resuelve exactamente ese problema.

---

## Arquitectura RAG

```
                    ┌─────────────────────────────────────┐
                    │           INDEXING PHASE             │
                    │                                     │
  Job Postings ────►│ Chunking → Embedding → pgvector     │
  Profiles ────────►│                                     │
  Trends ──────────►│                                     │
                    └─────────────────────────────────────┘
                    
                    ┌─────────────────────────────────────┐
                    │           RETRIEVAL PHASE            │
                    │                                     │
  User Query ──────►│ Query Embedding                     │
                    │        ↓                            │
                    │ Similarity Search (pgvector)        │
                    │        ↓                            │
                    │ Top-K Documents                     │
                    │        ↓                            │
                    │ Reranking (cross-encoder)           │
                    └─────────────────────────────────────┘
                    
                    ┌─────────────────────────────────────┐
                    │           GENERATION PHASE           │
                    │                                     │
  Retrieved Docs ──►│ Context Assembly                    │
  User Query ──────►│        ↓                            │
                    │ Prompt Construction                 │
                    │        ↓                            │
                    │ LLM (Claude / GPT-4)                │
                    │        ↓                            │
                    │ Structured Response                 │
                    └─────────────────────────────────────┘
```

---

## Implementación

### Chunking Strategy

Distintos documentos requieren distintas estrategias de chunking:

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

class DocumentChunker:
    
    # Para ofertas de trabajo (estructura semi-fija)
    JOB_CHUNK_SIZE = 1000
    JOB_CHUNK_OVERLAP = 200
    
    # Para perfiles de LinkedIn (texto más corto y denso)
    PROFILE_CHUNK_SIZE = 500
    PROFILE_CHUNK_OVERLAP = 100
    
    # Para documentación/tendencias (texto largo)
    TRENDS_CHUNK_SIZE = 1500
    TRENDS_CHUNK_OVERLAP = 300
    
    def chunk_job_posting(self, job: JobPosting) -> list[Document]:
        """
        Chunking especial para ofertas: preserva el título y empresa en cada chunk.
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.JOB_CHUNK_SIZE,
            chunk_overlap=self.JOB_CHUNK_OVERLAP,
        )
        
        # Cada chunk incluye el contexto de la oferta como metadata
        chunks = splitter.create_documents(
            texts=[job.description_clean],
            metadatas=[{
                "source": "job_posting",
                "job_id": str(job.id),
                "title": job.title,
                "company": job.company,
                "role_category": job.role_category,
                "country": job.country,
                "posted_at": job.posted_at.isoformat(),
            }]
        )
        return chunks
```

### Embedding Pipeline

```python
from langchain_openai import OpenAIEmbeddings
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    
    def __init__(self):
        # OpenAI para queries de producción (mejor calidad)
        self.openai_model = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # Local para batch indexing (sin costo)
        self.local_model = SentenceTransformer("BAAI/bge-m3")  # Multilingual
    
    def embed_query(self, text: str) -> list[float]:
        """Para queries en tiempo real: OpenAI."""
        return self.openai_model.embed_query(text)
    
    def embed_documents_batch(self, texts: list[str]) -> list[list[float]]:
        """Para indexing masivo: modelo local."""
        return self.local_model.encode(texts, batch_size=32).tolist()
```

### Retrieval con pgvector

```python
class VectorRetriever:
    
    def retrieve(
        self,
        query: str,
        role_category: str,
        country: str = None,
        k: int = 10,
        min_similarity: float = 0.7
    ) -> list[RetrievedDocument]:
        
        query_embedding = self.embedding_service.embed_query(query)
        
        # Búsqueda vectorial en pgvector con filtros de metadata
        results = await self.db.fetch("""
            SELECT 
                id,
                title,
                company,
                description_clean,
                skills,
                role_category,
                1 - (embedding <=> $1::vector) AS similarity
            FROM job_postings
            WHERE 
                role_category = $2
                AND ($3::text IS NULL OR country = $3)
                AND posted_at >= NOW() - INTERVAL '30 days'
                AND 1 - (embedding <=> $1::vector) >= $4
            ORDER BY embedding <=> $1::vector
            LIMIT $5
        """, query_embedding, role_category, country, min_similarity, k)
        
        return [RetrievedDocument(**row) for row in results]
```

### Reranking

Para mejorar la relevancia, se aplica un cross-encoder después del vector search:

```python
from sentence_transformers import CrossEncoder

class Reranker:
    
    def __init__(self):
        # Cross-encoder para reranking de alta precisión
        self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    
    def rerank(
        self,
        query: str,
        documents: list[RetrievedDocument],
        top_k: int = 5
    ) -> list[RetrievedDocument]:
        
        pairs = [(query, doc.content) for doc in documents]
        scores = self.model.predict(pairs)
        
        ranked = sorted(
            zip(documents, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [doc for doc, _ in ranked[:top_k]]
```

---

## Prompts del sistema

### RAG Prompt para análisis de perfil

```python
PROFILE_ANALYSIS_PROMPT = """
Eres un experto en optimización de perfiles de LinkedIn para roles técnicos en IA y datos.

Tenés acceso a información actualizada del mercado laboral:

CONTEXTO DEL MERCADO (últimas 4 semanas):
{retrieved_context}

PERFIL DEL USUARIO:
{user_profile}

ROL OBJETIVO: {target_role}

Tu tarea es analizar el perfil del usuario y generar recomendaciones específicas y accionables.

Para cada recomendación:
1. Indica la sección del perfil a mejorar
2. Explica el problema específico
3. Proporciona el texto reescrito o la keyword exacta a agregar
4. Explica por qué esto mejora la visibilidad (basándote en el contexto del mercado)

Responde en español argentino, tono profesional pero directo.
No des consejos genéricos — cada recomendación debe ser específica para este perfil y este mercado.
"""
```

### RAG Prompt para generación de About

```python
ABOUT_GENERATION_PROMPT = """
Sos un experto en personal branding para profesionales tech de habla hispana.

Contexto del mercado — cómo escriben el About los mejores perfiles de {target_role}:
{top_profiles_examples}

Keywords más buscadas para {target_role} esta semana:
{top_keywords}

Información del usuario:
- Nombre: {name}
- Rol actual: {current_role}
- Rol objetivo: {target_role}
- Stack técnico: {skills}
- Experiencia: {experience_summary}
- Diferenciador clave: {differentiator}

Generá 3 versiones del About para LinkedIn:

1. VERSIÓN TÉCNICA: Enfocada en el stack técnico y proyectos. Para atraer hiring managers técnicos.
2. VERSIÓN NARRATIVA: Cuenta una historia de evolución profesional. Para atraer recruiters generalistas.  
3. VERSIÓN ORIENTADA A RESULTADOS: Enfocada en impacto de negocio. Para atraer roles senior.

Cada versión debe:
- Tener entre 200 y 400 palabras
- Incluir las top 5 keywords del rol objetivo de forma natural
- Seguir esta estructura: Hook → Stack/Valor → Diferenciador → CTA
- Estar en español, tono profesional moderno (no formal-rígido)
- NO sonar como generado por IA (evitar frases cliché)
"""
```

---

## Índices de documentos

| Índice | Fuente | Embeddings | Uso |
|--------|--------|-----------|-----|
| `job_postings_idx` | Ofertas de trabajo | OpenAI Ada | Análisis de keywords, skills radar |
| `profile_snapshots_idx` | Perfiles públicos | OpenAI Ada | Benchmark, ejemplos de About |
| `trend_signals_idx` | Reddit, HN, Trends | Local BGE | AI Radar, tendencias emergentes |

---

## Métricas de calidad RAG

```python
RAG_QUALITY_METRICS = {
    # Retrieval
    "retrieval_precision_at_5": 0.80,   # 80% de los top-5 son relevantes
    "retrieval_recall": 0.75,            # 75% de documentos relevantes recuperados
    
    # Generation
    "factual_accuracy": 0.90,            # 90% de los datos son verificables
    "hallucination_rate_max": 0.05,      # Máximo 5% de alucinaciones
    
    # Performance
    "retrieval_latency_ms": 200,         # Vector search < 200ms
    "generation_latency_ms": 3000,       # Respuesta completa < 3s
}
```
