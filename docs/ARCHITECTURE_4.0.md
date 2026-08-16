# LinkedIn Intelligence — Architecture 4.0

> Versión: 4.0  
> Fecha: 2026-08-15  
> North Star: **ENTREVISTAS CALIFICADAS GENERADAS POR CANDIDATO ACTIVO**  
> Basado en: auditoría de código real + directiva de producto  

---

## Resumen ejecutivo

La arquitectura 4.0 no reemplaza la fundación existente — la extiende con cuatro capas nuevas:

1. **Evidence Layer** — validación semántica + temporal + cross-source de toda claim del candidato
2. **Requirement Layer** — parsing req-by-req de JDs + matching granular por requisito
3. **Personalization Layer** — CV con ediciones bullet-level, estrategia company-specific, evaluación con LLM judge
4. **Feedback Layer** — learning loop activo que retroalimenta scoring, thresholds y recomendaciones

---

## Arquitectura de sistema (vista macro)

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14)                                          │
│  /profile  /applications/[id]  /jobs  /insights                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP/REST + polling 3s
┌─────────────────────▼───────────────────────────────────────────┐
│  FastAPI (Python 3.11)                                          │
│  Routers: auth, candidates, applications, jobs, forms,          │
│           match, recommendations, market, analyze, agent        │
└──┬──────────────────┬──────────────────┬────────────────────────┘
   │                  │                  │
   ▼                  ▼                  ▼
PostgreSQL        Redis              Celery Workers
+ pgvector     (cache + queues)    (async tasks)
(primary store)
```

---

## Capas de dominio

### Capa 1: Datos de candidato

```
ProfileAgent                    CandidateKnowledgeResolver 2.0
├── extract_profile()           ├── resolve(field, context) → ResolvedValue
│   └── ExtractedProfile        │   ├── DIRECT (campo del modelo)
│       ├── skills[]            │   ├── COMPUTED (skill_years, total_exp)
│       │   └── EvidenceRef[]   │   ├── FROM_KB (from_profile_data)
│       └── experience[]        │   ├── GENERATED (LLM)
│                               │   └── HUMAN_REQUIRED
└── consolidate_profiles()      └── _resolution_cache: dict[str, ResolvedValue]
    └── ConsolidatedProfile
```

**Nuevo en 4.0:**
- `ResolvedValue`: añade `confidence: float`, `evidence_refs: list[EvidenceRef]`, `method: ResolutionMethod`
- `_resolve_skill_years()`: extrae períodos de experiencia, deduplica solapamientos, computa años netos
- Cache por `application_id` — no recomputar en mismo contexto

### Capa 2: Evidence System

```
EvidenceBuilder                         ClaimValidator 3.0
├── build_from_profile(profile)         ├── validate_claims(cv_text, evidence_records)
│   └── EvidenceRecord[]                │   ├── SUPPORTED (≥3 matches semánticos/keyword)
│       ├── source_type                 │   ├── PLAUSIBLE (1-2 matches)
│       ├── content                     │   ├── UNSUPPORTED (0 matches)
│       ├── date_range                  │   └── CONTRADICTED (claim contradice evidencia)
│       └── skills_mentioned[]         ├── _semantic_similarity(claim, evidence) → float
│                                       │   └── pgvector cosine o sentence-transformers
└── build_evidence_refs(skill, exp)     └── _temporal_consistency(claim, experiences) → bool
    └── list[EvidenceRef]
```

**Cambio crítico en 4.0:**
```python
# ANTES (siempre vacío — bug P0):
validate_claims(cv_text, evidence_records=[])

# DESPUÉS (evidencia real del perfil):
evidence_records = EvidenceBuilder.build_from_profile(candidate_profile)
validate_claims(cv_text, evidence_records=evidence_records)
```

**Estado CONTRADICTED:**
```python
@dataclass
class ValidationResult:
    claim: str
    status: Literal["SUPPORTED", "PLAUSIBLE", "UNSUPPORTED", "CONTRADICTED"]
    match_count: int
    contradiction_source: str | None  # Evidence que contradice
    temporal_consistent: bool
    evidence_refs: list[EvidenceRef]
```

### Capa 3: Matching Engine 3.0

```
MatchingEngine 3.0
├── match(profile, job) → MatchResult 3.0
│   ├── score: float                    # agregado weighted
│   ├── career_fit: float
│   ├── decision: Decision              # APPLY/STRETCH/DO_NOT_APPLY/BLOCKED
│   ├── requirements: list[RequirementMatch]  # NUEVO
│   │   ├── text: str
│   │   ├── type: "technical"|"soft"|"domain"|"cultural"
│   │   ├── importance: "MUST"|"NICE_TO_HAVE"
│   │   ├── candidate_status: "MATCHED"|"PARTIAL"|"MISSING"|"BLOCKER"|"UNCERTAIN"
│   │   ├── match_score: float
│   │   └── evidence_refs: list[EvidenceRef]
│   └── hard_constraints: list[Constraint]
│
├── _parse_requirements(jd_text) → list[Requirement]
│   └── LLM extrae requisitos estructurados con importance
│
├── _match_requirement(req, profile) → RequirementMatch
│   ├── keyword match (existing)
│   ├── synonym match (existing 26 grupos)
│   └── semantic match (pgvector) — NUEVO
│
└── _aggregate_score(requirements) → float
    └── weighted by importance, boosted by evidence_refs
```

**Decision blocker actualizado:**
```python
# Un BLOCKER en requisito MUST → BLOCKED independiente del score
if any(r.candidate_status == "BLOCKER" and r.importance == "MUST" 
       for r in requirements):
    decision = Decision.BLOCKED
```

### Capa 4: CV Engine 4.0

```
CVAgent 4.0
├── personalize_cv(profile, job_description) → PersonalizedCV 4.0
│   ├── summary_adapted: str
│   ├── headline_adapted: str
│   ├── skills_ordered: list[str]
│   ├── ats_keywords_added: list[str]
│   ├── changes: list[CVChange]           # existing
│   └── experience_personalized: list[ExperiencePersonalized]  # NUEVO
│       ├── company: str
│       ├── title: str
│       ├── bullets_original: list[str]
│       └── bullets_adapted: list[BulletChange]
│           ├── original: str
│           ├── adapted: str
│           ├── reason: str
│           ├── job_requirement: str       # qué req motivó el cambio
│           ├── evidence_refs: list[EvidenceRef]
│           └── confidence: float
│
└── _personalize_experience_bullets(exp, jd_requirements) → list[BulletChange]
    └── LLM edita bullet-by-bullet con reference a evidence_refs
```

**Evaluación de CV (LLM judge):**
```python
class CVFactualityCriterion(LLMEvaluationCriterion):
    """Verifica que cada claim esté respaldada por evidence_refs."""

class CVPersonalizationCriterion(LLMEvaluationCriterion):
    """% de bullets que mencionan algo específico del JD."""

class CVDifferentiationCriterion(EvaluationCriterion):
    """Distancia promedio entre CVs para mismo candidato, JDs distintos."""
```

### Capa 5: Application Strategy 2.0

```
ApplicationAgent 2.0
└── generate_strategy(profile, job, match_result) → ApplicationStrategy 2.0
    ├── overall_approach: str
    ├── positioning: str                  # NUEVO: cómo posicionarse
    ├── target_narrative: str             # NUEVO: narrativa para este tipo de rol
    ├── strengths_to_emphasize: list[str]
    ├── risks_to_address: list[str]
    ├── keywords_for_form: list[str]      # NUEVO: keywords ATS para texto libre
    ├── answer_strategy: dict[QuestionType, str]  # NUEVO: por tipo de pregunta
    ├── interview_preparation_strategy: str       # NUEVO
    ├── claims_to_avoid: list[str]                # NUEVO: basado en UNSUPPORTED claims
    ├── company_specific_angle: str               # NUEVO: desde JD real
    ├── cover_letter_key_points: list[str]
    └── recommendation: str
```

### Capa 6: Form Intelligence 2.0

```
SemanticType (extendido)
├── full_name, first_name, last_name, email, phone, location
├── linkedin_url, portfolio_url, github_url
├── work_authorization, salary_expectation, years_experience
├── cover_letter, resume_text, availability, education_level
├── custom_essay, file_upload, start_date
├── skill_years      # NUEVO: "How many years of Python?"
└── experience_essay # NUEVO: "Describe a project where..."

MappedField (extendido)
├── field_id: str
├── semantic_type: SemanticType
├── label: str
├── required: bool
├── options: list[str] | None
├── confidence: float              # NUEVO
├── classification_source: "regex"|"llm"  # NUEVO
└── skill_target: str | None       # NUEVO: skill a resolver para skill_years
```

### Capa 7: Submission State Machine 2.0

```
Estados (extendidos)
┌─────────────────────────────────────────────────────┐
│  initializing                                       │
│      ↓                                              │
│  discovering (form discovery)                       │
│      ↓                                              │
│  mapping (field classification)                     │
│      ↓                                              │
│  awaiting_human (HUMAN_REQUIRED fields)             │
│      ↓                                              │
│  ready_to_fill                                      │
│      ↓                                              │
│  filling ──→ PAUSED ──→ filling (resume)   # NUEVO │
│      ↓                                              │
│  previewing                                         │
│      ↓                                              │
│  submitting (human_confirmed=True required)         │
│      ↓                                              │
│  submitted / failed                                 │
└─────────────────────────────────────────────────────┘
```

**ApplicationSubmission (extendida):**
```python
@dataclass
class ApplicationSubmission:
    application_id: str
    submitted_at: datetime
    confirmation_id: str | None        # extraído de confirmation page
    screenshot_confirmation: bytes     # screenshot post-submit
    form_data_submitted: dict          # snapshot de datos enviados
    ats_response: str | None           # respuesta del ATS si disponible
```

### Capa 8: AI Evaluation

```
EvaluationCriterion (base)
├── StructuralCriterion              # existing: field_not_empty, etc.
└── LLMEvaluationCriterion          # NUEVO
    ├── prompt_template: str
    ├── model: str = "claude-haiku-4-5-20251001"
    ├── score_range: tuple[float, float]
    └── evaluate(subject: str, context: dict) → EvaluationScore

Criterios nuevos:
├── CVFactualityCriterion
├── CVPersonalizationCriterion
├── CVDifferentiationCriterion
├── CoverLetterClicheCriterion
└── CoverLetterCompanyHookCriterion
```

### Capa 9: Learning Loop 3.0

```
LearningLoop 3.0
├── compute_calibration(outcomes) → CalibrationReport  # existing
├── _update_thresholds(report)                          # NUEVO
│   └── Actualiza APPLY_THRESHOLD cuando bias es estable ≥10 outcomes
├── _outcome_boosted_idf(skills, outcomes) → dict      # NUEVO
│   └── Boost IDF de skills que generaron entrevistas
└── run_experiment(group_a, group_b) → ExperimentResult  # NUEVO
    ├── interview_rate_a, interview_rate_b
    ├── p_value (chi2_contingency)
    └── significant: bool  # p < 0.05
```

---

## Flujo de datos completo — Happy path 4.0

```
1. Candidato sube CV PDF
   → pdf_extractor.extract_text()
   → profile_agent.extract_profile() → ExtractedProfile con EvidenceRef[]
   → profile_agent.consolidate_profiles() → ConsolidatedProfile

2. Candidato selecciona empleo
   → matching_engine.match(profile, job)
     → _parse_requirements(jd_text) → list[Requirement]
     → _match_requirement(req, profile) per req
     → MatchResult con requirements[], score, decision

3. start() — Intelligence Phase
   → EvidenceBuilder.build_from_profile(profile) → evidence_records[]
   → cv_agent.personalize_cv(profile, job) → PersonalizedCV con experience_personalized
   → validate_claims(cv_text, evidence_records=evidence_records)  ← NUEVO
   → application_agent.generate_strategy(profile, job, match_result)
   → communication_agent.generate_cover_letter()
   → cv_storage.save_cv_pdf(PersonalizedCV)  ← usa bullets personalizados
   → form discovery + field classification (Form Intelligence 2.0)
   → CandidateKnowledgeResolver.resolve(fields, profile)

4. Human Review
   → Frontend muestra: req-by-req match, CV diff, strategy, HUMAN_REQUIRED fields
   → Candidato revisa y confirma

5. submit(human_confirmed=True)
   → ATS Adapter fills form
   → Pre-submit validation
   → ATS submit
   → Confirmation detection → ApplicationSubmission con evidence
   → Frontend muestra confirmation_id + screenshot

6. Outcome logging
   → PATCH /applications/{id}/outcome
   → learning_loop.compute_calibration(outcomes)
   → _update_thresholds() si stable ≥10 outcomes
   → _outcome_boosted_idf() actualiza job_recommender
```

---

## Modelo de datos — Cambios en 4.0

### Tablas nuevas / modificadas

```sql
-- NUEVA: cache de resolución por aplicación
CREATE TABLE resolution_cache (
    id UUID PRIMARY KEY,
    application_id UUID REFERENCES applications(id),
    field_name TEXT NOT NULL,
    resolved_value TEXT,
    confidence FLOAT,
    method TEXT, -- DIRECT/COMPUTED/FROM_KB/GENERATED/HUMAN_REQUIRED
    evidence_refs JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- NUEVA: evidencia de submission
ALTER TABLE application_submissions ADD COLUMN
    confirmation_id TEXT,
    screenshot_confirmation BYTEA,
    form_data_submitted JSONB;

-- NUEVA: requisitos de match por application
CREATE TABLE application_requirements (
    id UUID PRIMARY KEY,
    application_id UUID REFERENCES applications(id),
    requirement_text TEXT NOT NULL,
    requirement_type TEXT, -- technical/soft/domain/cultural
    importance TEXT, -- MUST/NICE_TO_HAVE
    candidate_status TEXT, -- MATCHED/PARTIAL/MISSING/BLOCKER/UNCERTAIN
    match_score FLOAT,
    evidence_refs JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- NUEVA: experimentos A/B
CREATE TABLE experiments (
    id UUID PRIMARY KEY,
    candidate_id UUID REFERENCES candidates(id),
    experiment_name TEXT NOT NULL,
    group_assignment TEXT, -- A/B
    strategy_params JSONB,
    outcome TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Modelos Pydantic nuevos

```python
# Evidence
@dataclass
class EvidenceRecord:
    source_type: Literal["experience", "education", "skill", "project", "certification"]
    content: str
    date_from: date | None
    date_to: date | None
    skills_mentioned: list[str]

# Match 3.0
@dataclass
class RequirementMatch:
    text: str
    type: Literal["technical", "soft", "domain", "cultural"]
    importance: Literal["MUST", "NICE_TO_HAVE"]
    candidate_status: Literal["MATCHED", "PARTIAL", "MISSING", "BLOCKER", "UNCERTAIN"]
    match_score: float
    evidence_refs: list[EvidenceRef]

# Knowledge Resolver 2.0
@dataclass
class ResolvedValue:
    answer: str | None
    confidence: float  # 0.0–1.0
    method: ResolutionMethod
    evidence_refs: list[EvidenceRef]
    human_input_required: bool
    auto_fill_suggestion: str | None

# Form Intelligence 2.0
@dataclass
class MappedField:
    field_id: str
    semantic_type: SemanticType
    label: str
    required: bool
    options: list[str] | None
    confidence: float              # NUEVO
    classification_source: Literal["regex", "llm"]  # NUEVO
    skill_target: str | None       # NUEVO
```

---

## Stack tecnológico — Sin cambios de fundación

| Componente | Tecnología | Versión |
|------------|------------|---------|
| Backend | FastAPI + Python | 3.11 |
| ORM | SQLAlchemy async | 2.x |
| Validación | Pydantic v2 | 2.x |
| DB | PostgreSQL + pgvector | 16 |
| Cache | Redis | 7 |
| Tasks | Celery | 5.x |
| Browser | Playwright (Chromium pre-installed) | async |
| LLM | Anthropic SDK (`claude-haiku-4-5-20251001`) | latest |
| PDF | ReportLab | 4.x |
| Async files | aiofiles | latest |
| Frontend | Next.js 14 + TypeScript | 14 |
| Semantic similarity | sentence-transformers o pgvector cosine | — |
| Hypothesis testing | scipy.stats | — |

---

## Principios de diseño que no cambian

1. **No auto-submit**: `human_confirmed=True` siempre requerido en `submit()`
2. **No datos personales reales en tests**: fixtures sintéticas únicamente
3. **No scraping no autorizado de LinkedIn**: el sistema procesa texto que el usuario pega
4. **Graceful degradation**: `_run_intelligence_phase()` captura excepciones; submission continúa sin inteligencia
5. **Evidence-first claims**: ninguna personalización sin `evidence_ref` — inventar facts está prohibido
6. **Linting clean**: `ruff check .` + `mypy app/` sin errores antes de cada merge
7. **TypeVar generics**: `structured_output[T]()` mantiene tipos concretos en agentes

---

*Ver `docs/ROADMAP_4.0.md` para el plan de sprints A–L*  
*Ver `docs/PRODUCT_COMPLETION_GAP_ANALYSIS.md` para estado actual de cada capacidad*
