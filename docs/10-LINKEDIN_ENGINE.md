# 10 · LinkedIn Engine

## Objetivo

El LinkedIn Engine analiza perfiles de LinkedIn y genera recomendaciones específicas para maximizar la visibilidad en búsquedas de recruiters y el impacto del perfil.

A diferencia del ATS Engine (que evalúa CVs para pasar filtros automáticos), el LinkedIn Engine se enfoca en el **algoritmo de búsqueda de LinkedIn** y en cómo los **recruiters** evalúan perfiles.

---

## Cómo funciona el algoritmo de LinkedIn

Basado en análisis de documentación pública, reportes de SEO de LinkedIn y pruebas propias:

### Factores de ranking en búsquedas de recruiters

1. **Título (headline)** — Máximo peso. Las keywords aquí tienen 3-5x más peso.
2. **Skills section** — Directamente indexada. Top 3 skills tienen el mayor peso.
3. **About section** — Primeras 3 líneas son las más pesadas (visible sin expandir).
4. **Experience titles** — Títulos de cada puesto, no las descripciones.
5. **Certificaciones** — Peso moderado, especialmente para búsquedas técnicas.
6. **Actividad reciente** — Perfiles activos (publicaciones, interacciones) rankean mejor.

### Lo que NO importa tanto

- Descripciones largas de experiencia (indexadas pero bajo peso)
- Educación (salvo para roles junior)
- Recomendaciones escritas

---

## Profile Scoring

### Componentes del Profile Score

```python
SECTION_WEIGHTS = {
    "title":         0.25,   # El factor más importante
    "about":         0.20,   # Primeras 300 caracteres son clave
    "skills":        0.20,   # Top 5 skills tienen máximo peso
    "experience":    0.20,   # Títulos de cargo + keywords en descripción
    "projects":      0.10,   # Proyectos con links tienen bonus
    "education":     0.05,
}
```

### Title Score

```python
def score_title(title: str, target_role: str) -> TitleScore:
    """
    Evalúa el título de LinkedIn contra el rol objetivo.
    
    Criterios:
    - ¿Incluye el título del rol objetivo?
    - ¿Incluye al menos 3 tecnologías clave?
    - ¿Tiene menos de 220 caracteres? (límite de LinkedIn)
    - ¿Empieza con el rol objetivo (no con el empleador actual)?
    """
    
    checks = {
        "role_mentioned": role_keyword_in_title(title, target_role),
        "tech_keywords": count_tech_keywords_in_title(title),
        "length_ok": len(title) <= 220,
        "role_first": title_starts_with_role(title, target_role),
        "no_just_company": not_only_company_role(title),
    }
    
    score = calculate_weighted_score(checks)
    return TitleScore(score=score, checks=checks, issues=get_issues(checks))
```

**Ejemplos de scoring de títulos**:

| Título | Score | Problema |
|--------|-------|---------|
| `Analista SSR en BBVA` | 12/100 | No menciona AI, no hay tecnologías |
| `Data Analyst \| Python \| SQL` | 45/100 | No menciona AI Engineering |
| `AI Engineer \| Python · LangChain · SQL` | 82/100 | Bueno, podría agregar más |
| `AI Engineer \| Analytics Engineer \| Python · LangChain · LangGraph · SQL · FastAPI · GenAI` | 96/100 | Excelente |

### About Score

```python
def score_about(about: str, target_role: str, role_keywords: list[str]) -> AboutScore:
    """
    Evalúa el About de LinkedIn.
    
    Estructura ideal de un About de AI Engineer (comprobada en perfiles top):
    
    Línea 1-2 (HOOK): ¿Qué hacés en una línea? 
        → "AI Engineer que construye aplicaciones LLM para automatizar procesos en banca y fintech."
    
    Línea 3-6 (VALOR): ¿Qué sabés hacer?
        → Stack técnico + logros específicos con números
    
    Línea 7-9 (DIFERENCIADOR): ¿Qué te hace único?
        → Combinación bancas + IA + analytics (raro y valioso)
    
    Línea 10-12 (CTA): ¿Qué buscás?
        → "Abierto a roles de AI Engineering en fintech, neobancos y startups de IA."
    """
    
    checks = {
        "has_hook": about[:200] contains role keywords,
        "tech_keywords_count": count_tech_keywords(about),
        "has_quantified_results": has_numbers_or_metrics(about),
        "optimal_length": 200 <= len(about) <= 2600,
        "has_cta": has_call_to_action(about[-200:]),
        "keyword_density": keyword_density_ok(about, role_keywords),
    }
```

---

## Benchmark Analysis

Compara el perfil del usuario contra los mejores perfiles para el rol objetivo.

```python
class ProfileBenchmark:
    
    def compare(
        self,
        user_profile: ParsedProfile,
        target_role: str,
        percentile_target: int = 90
    ) -> BenchmarkResult:
        
        # Obtener vectores de los mejores perfiles del rol
        top_profiles = self._get_top_profiles(target_role, limit=100)
        
        # Vectorizar el perfil del usuario
        user_embedding = self.embeddings.encode(user_profile.full_text)
        
        # Calcular similitud con cada perfil top
        similarities = [
            cosine_similarity(user_embedding, p.embedding) 
            for p in top_profiles
        ]
        
        user_percentile = percentileofscore(similarities, max(similarities))
        
        # Identificar las mayores brechas
        gaps = self._identify_gaps(user_profile, top_profiles)
        
        return BenchmarkResult(
            percentile=user_percentile,
            similar_profiles=self._find_most_similar(user_embedding, top_profiles, k=5),
            top_gaps=gaps[:5],
            strengths=self._identify_strengths(user_profile, top_profiles),
        )
    
    def _identify_gaps(
        self,
        user: ParsedProfile,
        top_profiles: list[ParsedProfile]
    ) -> list[Gap]:
        """
        Compara skills, estructura y keywords del usuario vs. los top perfiles.
        """
        
        # Skills que el 70%+ de los top perfiles tienen y el usuario no
        top_skills = Counter()
        for profile in top_profiles:
            top_skills.update(profile.skills)
        
        missing_skills = [
            skill for skill, count in top_skills.most_common(50)
            if count / len(top_profiles) >= 0.7 
            and skill not in user.skills
        ]
        
        return [
            Gap(
                area="skills",
                item=skill,
                prevalence_pct=top_skills[skill] / len(top_profiles) * 100,
                priority=self._calculate_priority(skill, top_skills, user),
            )
            for skill in missing_skills
        ]
```

---

## Title Optimizer

Genera variantes de título optimizadas para el algoritmo de LinkedIn.

```python
TITLE_TEMPLATES = [
    # Template 1: Rol doble + Stack
    "{primary_role} | {secondary_role} | {tech1} · {tech2} · {tech3} · {tech4}",
    
    # Template 2: Arrow progression
    "{current_domain} → {target_role} | {tech1} · {tech2} · {tech3}",
    
    # Template 3: Full stack emphasis
    "{role} | {domain} | {tech1} · {tech2} · {tech3} · {category}",
    
    # Template 4: Value-first
    "{domain} {role} | {company_type} | {tech_stack}",
]

class TitleOptimizer:
    
    def generate(
        self,
        current_role: str,
        target_role: str,
        top_skills: list[str],
        experience_domain: str
    ) -> list[TitleVariant]:
        
        variants = []
        
        for template in TITLE_TEMPLATES:
            title = self._fill_template(
                template, current_role, target_role, top_skills
            )
            
            score = self._score_title(title, target_role)
            keywords_covered = self._count_keywords_covered(title, top_skills)
            
            variants.append(TitleVariant(
                title=title,
                score=score,
                keywords_covered=keywords_covered,
                rationale=self._generate_rationale(title, target_role),
            ))
        
        # También generar con LLM para variantes más creativas
        llm_variants = self._generate_with_llm(
            current_role, target_role, top_skills, experience_domain
        )
        variants.extend(llm_variants)
        
        return sorted(variants, key=lambda v: v.score, reverse=True)[:5]
```

---

## Keyword Gap Analysis

```python
class KeywordGapAnalyzer:
    
    def analyze(
        self,
        user_profile: ParsedProfile,
        target_role: str
    ) -> KeywordGapReport:
        
        # Keywords en perfiles top (frecuencia >= 50%)
        top_profile_keywords = self._get_top_profile_keywords(target_role)
        
        # Keywords en ofertas top (frecuencia >= 40%)
        top_job_keywords = self._get_top_job_keywords(target_role)
        
        # Intersección y diferencias
        user_keywords = set(user_profile.all_keywords)
        
        missing_from_profiles = top_profile_keywords - user_keywords
        missing_from_jobs = top_job_keywords - user_keywords
        
        # Keywords que aparecen en AMBOS (perfiles y ofertas) tienen máxima prioridad
        high_priority_missing = missing_from_profiles & missing_from_jobs
        
        # Mapear dónde agregar cada keyword
        placement_map = {
            kw: self._best_placement(kw, user_profile)
            for kw in high_priority_missing
        }
        
        return KeywordGapReport(
            high_priority=list(high_priority_missing),
            medium_priority=list(missing_from_jobs - missing_from_profiles),
            placement_suggestions=placement_map,
        )
    
    def _best_placement(self, keyword: str, profile: ParsedProfile) -> str:
        """
        Decide en qué sección agregar una keyword:
        - Tecnología de programación → skills + experience
        - Framework de IA → skills + projects
        - Cloud platform → skills + experience
        - Metodología → experience + about
        """
        ...
```

---

## Contenido recomendado para AI Engineer (perfil de referencia)

Esta es la estructura que aparece en el 80%+ de los mejores perfiles de AI Engineer con alta visibilidad:

### Título ideal
```
AI Engineer | Analytics Engineer | LLMs · RAG · LangChain · Python · FastAPI · SQL
```

### About ideal (estructura)
```
[Hook: 1-2 líneas con el rol y propuesta de valor]
[Stack técnico: 3-4 líneas mencionando tecnologías]
[Diferenciador: lo que te hace único - en tu caso, bancario + IA]
[Proyectos destacados: 1-2 líneas con proyectos concretos]
[CTA: qué tipo de roles te interesan]
```

### Skills top para AI Engineer (Argentina, Jul 2025)
```
Python · SQL · LangChain · LangGraph · FastAPI · PostgreSQL · Docker
OpenAI API · Claude API · RAG · Embeddings · Vector Databases
AWS · GitHub Actions · n8n · Prompt Engineering · REST APIs
```
