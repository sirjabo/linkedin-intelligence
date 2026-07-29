# 12 · AI Agents

## Filosofía

Los agentes de IA se usan para tareas que requieren múltiples pasos, uso de herramientas o toma de decisiones iterativa. Para tareas simples (un LLM call), se usa RAG directo sin agentes.

**Regla**: Un agente se justifica cuando la tarea necesita:
1. Usar herramientas externas (DB queries, APIs)
2. Múltiples pasos con condicionales
3. Verificación y corrección iterativa
4. Estado que persiste entre pasos

---

## Framework: LangGraph

Usamos LangGraph (no LangChain Agents) por:
- **Control explícito** del flujo (no "react" loops abiertos)
- **Estado tipado** con Pydantic
- **Checkpointing** para agentes de larga duración
- **Trazabilidad** con LangSmith

---

## Agentes del sistema

### 1. ProfileAnalystAgent

**Propósito**: Análisis profundo de un perfil de LinkedIn, combinando análisis estructurado + contexto del mercado.

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

class ProfileAnalysisState(TypedDict):
    # Input
    profile_text: str
    target_role: str
    
    # Intermediate
    parsed_profile: dict
    market_context: list[dict]
    section_scores: dict
    
    # Output
    overall_score: int
    recommendations: list[dict]
    final_report: str

def build_profile_analyst_graph():
    
    graph = StateGraph(ProfileAnalysisState)
    
    # Nodos
    graph.add_node("parse_profile", parse_profile_node)
    graph.add_node("retrieve_market_context", retrieve_context_node)
    graph.add_node("score_sections", score_sections_node)
    graph.add_node("generate_recommendations", generate_recommendations_node)
    graph.add_node("compile_report", compile_report_node)
    
    # Flujo
    graph.set_entry_point("parse_profile")
    graph.add_edge("parse_profile", "retrieve_market_context")
    graph.add_edge("retrieve_market_context", "score_sections")
    graph.add_edge("score_sections", "generate_recommendations")
    graph.add_edge("generate_recommendations", "compile_report")
    graph.add_edge("compile_report", END)
    
    return graph.compile()

# Nodo: Parsear perfil con LLM
async def parse_profile_node(state: ProfileAnalysisState) -> ProfileAnalysisState:
    llm = ChatAnthropic(model="claude-sonnet-5")
    parser = LLMProfileParser(llm)
    state["parsed_profile"] = await parser.parse(state["profile_text"])
    return state

# Nodo: Recuperar contexto del mercado
async def retrieve_context_node(state: ProfileAnalysisState) -> ProfileAnalysisState:
    retriever = VectorRetriever()
    context = await retriever.retrieve(
        query=f"top profiles and jobs for {state['target_role']}",
        role_category=state["target_role"],
        k=20
    )
    state["market_context"] = [doc.dict() for doc in context]
    return state
```

### 2. CVOptimizerAgent

**Propósito**: Optimiza un CV para una oferta específica o un rol objetivo.

```python
class CVOptimizerState(TypedDict):
    cv_text: str
    job_description: str | None
    target_role: str
    
    # Intermediate
    cv_parsed: dict
    keywords_analyzed: dict
    weak_bullets: list[str]
    
    # Output
    ats_score: int
    optimized_bullets: dict[str, str]   # original → rewritten
    keywords_to_add: list[dict]
    final_recommendations: list[dict]

async def rewrite_bullet_node(state: CVOptimizerState) -> CVOptimizerState:
    """
    Reescribe bullets débiles con IA, incorporando:
    1. Keywords faltantes de alto peso
    2. Cuantificación de resultados
    3. Acción → Tarea → Resultado (estructura ATR)
    """
    llm = ChatAnthropic(model="claude-sonnet-5")
    
    rewritten = {}
    for bullet in state["weak_bullets"][:5]:  # Top 5 bullets más débiles
        prompt = f"""
        Reescribí este bullet de CV para un rol de {state['target_role']}.
        
        Bullet original: {bullet}
        
        Keywords a incorporar: {state['keywords_analyzed']['high_priority_missing'][:3]}
        
        Estructura ATR: [Acción fuerte] + [Tecnología/Herramienta] + [Resultado medible]
        
        Reglas:
        - Empezar con verbo de acción en pasado (Desarrollé, Implementé, Automaticé)
        - Máximo 2 líneas
        - Incluir al menos 1 número o métrica si es posible
        - No inventar datos que no estén en el original
        """
        response = await llm.ainvoke(prompt)
        rewritten[bullet] = response.content
    
    state["optimized_bullets"] = rewritten
    return state
```

### 3. TrendAnalystAgent

**Propósito**: Detecta y explica tendencias emergentes en el mercado laboral tech.

```python
class TrendAnalysisState(TypedDict):
    role_category: str
    country: str
    lookback_days: int
    
    # Data fetched
    current_week_skills: dict
    previous_week_skills: dict
    reddit_signals: list[str]
    hn_signals: list[str]
    
    # Analysis
    rising_skills: list[dict]
    declining_skills: list[dict]
    emerging_skills: list[dict]
    
    # Output
    radar_summary: str
    alerts: list[dict]

TREND_ANALYST_TOOLS = [
    get_skill_demand_tool,        # Query DB para demanda de skills
    get_reddit_signals_tool,      # Señales de Reddit
    get_hackernews_signals_tool,  # Señales de HN
    get_google_trends_tool,       # Google Trends
    calculate_trend_tool,         # Calcular % de cambio
]

async def analyze_trends_node(state: TrendAnalysisState) -> TrendAnalysisState:
    """
    Detecta skills con cambio de >15% en 7 días.
    Cruza con señales de Reddit/HN para validar que es tendencia real.
    """
    changes = {}
    for skill in state["current_week_skills"]:
        current = state["current_week_skills"].get(skill, 0)
        previous = state["previous_week_skills"].get(skill, 0)
        
        if previous > 0:
            change_pct = ((current - previous) / previous) * 100
            changes[skill] = change_pct
    
    # Skills que subieron >15% y tienen validación social
    rising = [
        {
            "skill": skill,
            "change_pct": pct,
            "validated_by_reddit": skill in state["reddit_signals"],
            "validated_by_hn": skill in state["hn_signals"],
        }
        for skill, pct in changes.items()
        if pct >= 15
    ]
    
    state["rising_skills"] = sorted(rising, key=lambda x: x["change_pct"], reverse=True)
    return state
```

### 4. ContentCreatorAgent

**Propósito**: Genera contenido para LinkedIn (About, posts, calendario).

```python
class ContentCreationState(TypedDict):
    content_type: str  # 'about' | 'post' | 'calendar'
    user_profile: dict
    target_role: str
    market_context: list[dict]
    
    # For posts
    topic: str | None
    post_format: str | None  # 'text' | 'carousel' | 'poll'
    
    # Output
    generated_content: str | list[str]
    optimization_notes: str

async def generate_about_node(state: ContentCreationState) -> ContentCreationState:
    llm = ChatAnthropic(model="claude-sonnet-5")
    
    # Obtener ejemplos de los mejores About del rol objetivo
    best_abouts = await retrieve_best_abouts(
        role=state["target_role"],
        k=10
    )
    
    prompt = build_about_prompt(
        user=state["user_profile"],
        examples=best_abouts,
        market=state["market_context"],
    )
    
    # Generar 3 variantes
    variants = []
    for style in ["technical", "narrative", "results_focused"]:
        response = await llm.ainvoke(
            prompt + f"\n\nEstilo: {style}"
        )
        variants.append(response.content)
    
    state["generated_content"] = variants
    return state
```

---

## Herramientas de los agentes

```python
# tools/database_tools.py

@tool
def get_top_skills_for_role(role: str, country: str = "AR", limit: int = 20) -> str:
    """
    Obtiene las skills más demandadas para un rol en las últimas 4 semanas.
    Útil para: analizar perfiles, generar recomendaciones, crear contenido.
    
    Args:
        role: Rol objetivo ('ai_engineer', 'data_engineer', 'analytics_engineer')
        country: Código ISO del país (por defecto 'AR' para Argentina)
        limit: Cantidad de skills a devolver
    """
    skills = db.query_top_skills(role=role, country=country, limit=limit)
    return format_skills_for_llm(skills)

@tool
def search_similar_profiles(
    profile_summary: str,
    target_role: str,
    k: int = 5
) -> str:
    """
    Busca perfiles similares al del usuario para benchmark.
    Útil para: comparación, extracción de ejemplos de About y títulos.
    
    Args:
        profile_summary: Resumen del perfil a comparar
        target_role: Rol objetivo
        k: Cantidad de perfiles similares a devolver
    """
    ...

@tool
def get_trending_skills(role: str, days: int = 7) -> str:
    """
    Obtiene skills que más crecieron en los últimos N días.
    """
    ...
```

---

## Observabilidad de agentes

Todos los agentes se tracean con LangSmith:

```python
from langchain_core.tracers import LangChainTracer

tracer = LangChainTracer(
    project_name="linkedin-intelligence",
)

# Cada run del agente queda en LangSmith con:
# - Input/output de cada nodo
# - Tokens usados
# - Latencia por nodo
# - Errores y retries
```

---

## Costos estimados por operación

| Operación | Modelo | Tokens aprox. | Costo |
|-----------|--------|--------------|-------|
| Análisis de CV | claude-sonnet-5 | 3.000 | ~$0.015 |
| Análisis de LinkedIn | claude-sonnet-5 | 4.000 | ~$0.020 |
| Generación de About (3 versiones) | claude-sonnet-5 | 6.000 | ~$0.030 |
| Nightly Trend Analysis | claude-sonnet-5 | 8.000 | ~$0.040 |
| Skills extraction (por oferta) | claude-haiku-4-5 | 500 | ~$0.0003 |

*Precios aproximados a Julio 2025. Ver [claude-api skill] para precios actuales.*
