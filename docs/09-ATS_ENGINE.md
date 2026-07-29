# 09 · ATS Engine

## ¿Qué es el ATS Score?

Los sistemas ATS (Applicant Tracking System) filtran CVs automáticamente antes de que un humano los vea. Según estudios, el 75% de los CVs no pasan este filtro, no porque el candidato no sea bueno, sino porque las palabras clave no coinciden con las que busca el sistema.

El **ATS Score** de LinkedIn Intelligence mide la probabilidad de que un CV pase los filtros ATS para un rol objetivo específico, basándose en análisis de miles de ofertas de trabajo reales.

---

## Algoritmo de scoring

### Paso 1: Extracción de keywords del rol objetivo

```python
def get_role_keywords(role: str, country: str = None) -> list[WeightedKeyword]:
    """
    Obtiene las keywords más importantes para un rol objetivo.
    Las keywords se obtienen de las ofertas de trabajo analizadas en los últimos 30 días.
    """
    # Query a la DB: top keywords por frecuencia en job_postings del rol
    keywords = db.query("""
        SELECT 
            skill_name,
            COUNT(*) as job_count,
            COUNT(*) * 1.0 / total_jobs AS frequency,
            -- Keywords más frecuentes tienen mayor peso
            CASE 
                WHEN frequency > 0.8 THEN 1.0   -- Aparece en >80% de ofertas
                WHEN frequency > 0.5 THEN 0.7   -- Aparece en 50-80%
                WHEN frequency > 0.3 THEN 0.5   -- Aparece en 30-50%
                ELSE 0.3                         -- Aparece en <30%
            END AS weight
        FROM skill_demand
        WHERE role_category = :role
        ORDER BY frequency DESC
        LIMIT 100
    """, role=role)
    return keywords
```

### Paso 2: Extracción de contenido del CV

```python
class CVParser:
    
    def parse(self, cv_text: str) -> ParsedCV:
        """Extrae secciones estructuradas del CV."""
        return ParsedCV(
            contact=self._extract_contact(cv_text),
            summary=self._extract_summary(cv_text),
            experience=self._extract_experience(cv_text),
            skills=self._extract_skills(cv_text),
            education=self._extract_education(cv_text),
            projects=self._extract_projects(cv_text),
            certifications=self._extract_certifications(cv_text),
        )
    
    def _extract_skills(self, text: str) -> list[str]:
        """
        Combina 3 métodos:
        1. Sección explícita de skills
        2. NER con spaCy para tecnologías en texto libre
        3. LLM fallback para skills implícitas
        """
        ...
```

### Paso 3: Matching exacto + semántico

```python
class ATSMatcher:
    
    def match(
        self, 
        cv_skills: list[str], 
        role_keywords: list[WeightedKeyword]
    ) -> MatchResult:
        
        matched = []
        missing = []
        
        for keyword in role_keywords:
            # Método 1: Matching exacto (case-insensitive)
            if self._exact_match(keyword.name, cv_skills):
                matched.append(keyword)
                continue
            
            # Método 2: Matching de alias (ej: "LangChain" == "langchain")
            if self._alias_match(keyword, cv_skills):
                matched.append(keyword)
                continue
            
            # Método 3: Matching semántico con embeddings
            # Solo para keywords de alto peso (evitar falsos positivos)
            if keyword.weight >= 0.7:
                similarity = self._semantic_match(keyword.name, cv_skills)
                if similarity > 0.85:
                    matched.append(keyword)
                    continue
            
            missing.append(keyword)
        
        return MatchResult(matched=matched, missing=missing)
```

### Paso 4: Cálculo del score

```python
def calculate_ats_score(match_result: MatchResult) -> int:
    """
    Score ponderado por el peso de cada keyword.
    
    Score = (suma de pesos de keywords encontradas) / 
            (suma de pesos de todas las keywords) * 100
    """
    total_weight = sum(k.weight for k in match_result.all_keywords)
    matched_weight = sum(k.weight for k in match_result.matched)
    
    raw_score = (matched_weight / total_weight) * 100
    
    # Penalización por keywords críticas faltantes
    # Si falta una keyword con peso > 0.9, penalizar 10 puntos
    critical_missing = [k for k in match_result.missing if k.weight >= 0.9]
    penalty = len(critical_missing) * 10
    
    return max(0, min(100, int(raw_score - penalty)))
```

---

## Interpretación del score

| Score | Interpretación | Acción recomendada |
|-------|---------------|-------------------|
| 90-100 | Excelente — muy alta probabilidad de pasar ATS | Aplicar, pocas mejoras |
| 75-89 | Bueno — buena probabilidad | 2-3 keywords clave a agregar |
| 60-74 | Aceptable — pasa algunos sistemas | 5-8 mejoras concretas |
| 40-59 | Bajo — riesgo de no pasar | Revisión profunda necesaria |
| 0-39 | Crítico — muy probable que no pase | Reescritura recomendada |

---

## Recomendaciones automáticas

Además del score, el engine genera recomendaciones priorizadas:

```python
class RecommendationEngine:
    
    def generate(
        self,
        parsed_cv: ParsedCV,
        missing_keywords: list[WeightedKeyword],
        section_scores: dict[str, int]
    ) -> list[Recommendation]:
        
        recommendations = []
        
        # 1. Keywords críticas faltantes (peso > 0.8)
        for kw in sorted(missing_keywords, key=lambda k: k.weight, reverse=True):
            if kw.weight >= 0.8:
                section = self._best_section_for_keyword(kw, parsed_cv)
                recommendations.append(Recommendation(
                    priority=1,
                    type="add_keyword",
                    section=section,
                    message=f"Agregá '{kw.name}' a tu sección de {section}",
                    impact="high"
                ))
        
        # 2. Bullets de experiencia débiles
        weak_bullets = self._find_weak_bullets(parsed_cv.experience)
        for bullet in weak_bullets[:3]:  # Top 3 para no abrumar
            rewritten = self._rewrite_bullet_with_llm(bullet, missing_keywords)
            recommendations.append(Recommendation(
                priority=2,
                type="rewrite_bullet",
                section="experience",
                original=bullet,
                suggested=rewritten,
                impact="medium"
            ))
        
        # 3. Secciones faltantes
        if not parsed_cv.projects:
            recommendations.append(Recommendation(
                priority=3,
                type="add_section",
                section="projects",
                message="Agregá una sección de proyectos con demos de IA",
                impact="medium"
            ))
        
        return sorted(recommendations, key=lambda r: r.priority)
```

---

## Validación del score

Para mantener la precisión del ATS Score, se valida periódicamente:

1. **Ground truth**: Se toma una muestra de CVs reales + ofertas reales.
2. **Resultado real**: Se registra si el candidato pasó el proceso de selección.
3. **Correlación**: El score debe correlacionar con el éxito real (objetivo: r > 0.7).
4. **Recalibración**: Si la correlación baja de 0.6, se recalibran los pesos.

```python
# Métricas de calidad del ATS Engine
QUALITY_METRICS = {
    "score_accuracy_target": 0.85,    # 85% de exactitud vs. resultado real
    "false_positive_max": 0.15,       # Máximo 15% de falsos positivos
    "false_negative_max": 0.10,       # Máximo 10% de falsos negativos
    "recalibration_threshold": 0.70,  # Recalibrar si cae debajo de 70%
}
```

---

## Scoring por sección

Además del score global, se calcula un score por sección del CV:

| Sección | Peso en score global | Qué evalúa |
|---------|---------------------|-----------|
| Skills | 30% | Keywords técnicas explícitas |
| Experience | 30% | Keywords en bullets, cuantificación |
| Projects | 20% | Keywords técnicas en proyectos |
| Summary | 10% | Keywords en el resumen ejecutivo |
| Education | 5% | Títulos, certificaciones relevantes |
| Contact | 5% | Completitud del contacto |

---

## Mejoras futuras

- [ ] Soporte para ATS específicos (Workday, Taleo, Lever, Greenhouse) que tienen algoritmos propios
- [ ] Score de legibilidad para humanos (además del ATS Score)
- [ ] Análisis de formato visual del PDF (columnas, tablas, fuentes que confunden ATS)
- [ ] Modelo fine-tuned para mayor precisión de extracción de skills
