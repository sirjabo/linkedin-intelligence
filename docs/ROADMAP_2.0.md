# LinkedIn Intelligence 2.0 — Roadmap

> Actualizado: 2026-08-14  
> Branch actual: `claude/new-session-ce0sct`  
> Tests: 181 pasando  
> **ESTADO**: Backend Foundation completo. Roadmap del Real Application Agent en `ROADMAP_REAL_AGENT.md`.  
> Ver también: `PRODUCT_COMPLETION_GAP_ANALYSIS.md` (audit de las 58 capacidades)  
> Norte: **HIGH-QUALITY SUBMITTED APPLICATION por candidato activo**

---

## Regla de calidad

Una capacidad está implementada cuando:
- funciona en backend + frontend (cuando corresponde)
- tiene tests de unit + integración
- maneja errores + empty state + loading state
- respeta seguridad (ownership, auth)
- pasa acceptance criteria

No decir "implementado" porque existe un endpoint.

---

## Prioridades depriorizadas

- Content Calendar
- LinkedIn Post Generator
- AI Radar
- Reddit / HN signals
- Google Trends
- Market Intelligence (P2+)
- Browser extension (P3)
- Fine-tuning (P3)

---

## Fase 0 — Hardening de seguridad crítica (≈1 día)

> Estado: **EN PROGRESO**

### 0.1 Rate limiting en auth
Agregar `slowapi` con límites en `/auth/login` y `/auth/register`.

**Acceptance:** 429 después de N intentos, header Retry-After presente.

### 0.2 SSRF protection en source_url
Validar que `source_url` no apunte a IPs privadas (127.x, 10.x, 172.16-31.x, 192.168.x).

**Acceptance:** Requests a localhost devuelven 422.

### 0.3 Account deletion
`DELETE /candidates/me` elimina candidate + sources + profile + jobs + applications en cascade.

**Acceptance:** Usuario puede borrar toda su data. DB limpia después.

---

## Fase 1 — Matching 2.0 (≈2-3 días)

> Estado: **PENDIENTE**

### 1.1 Hard Constraints Layer (Layer 1)
Verificar antes del score:
- work authorization vs job_location / visa_required
- salary_max_job vs salary_min_candidate (blocker si > 30% gap)
- seniority_rank candidato vs seniority_required (blocker si > 2 niveles abajo)
- required certifications

Output: `{blocked: bool, blockers: list[str]}`

**Acceptance:** Candidato junior (rank=2) vs staff job (rank=5) → BLOCKED.

### 1.2 Career Fit (separado de Job Fit)
Nuevo campo `career_fit_score: float` en `MatchAnalysis`.
- Evalúa si el trabajo tiene sentido para la trayectoria
- Considera: trajectory_alignment, domain_growth, scope_match, stretch_factor
- LLM reasoning específico para career fit

**Acceptance:** job_fit 78, career_fit 94 mostrados por separado en UI.

### 1.3 Application Decision Engine
Reemplazar `recommendation: str` por:
```
decision: APPLY | APPLY_WITH_CUSTOMIZATION | STRETCH | LOW_FIT | DO_NOT_APPLY | BLOCKED
strengths: list[str]
gaps: list[str]
blockers: list[str]  # hard constraints
decision_rationale: str
what_would_change_decision: str
```

**Acceptance:** Decision BLOCKED cuando hay hard constraint. Decision diferenciada de LLM recommendation.

### 1.4 Per-requirement coverage (Layer 2)
Para cada JobRequirement:
```json
{
  "requirement": "5 years Python",
  "importance": 0.9,
  "candidate_match": 0.8,
  "evidence": "ProfileAgent extracted Python 4 years",
  "coverage": 0.72
}
```

**Acceptance:** Coverage mostrado en MatchScoreCard.

---

## Fase 2 — Candidate Knowledge Base 2.0 (≈2 días)

> Estado: **PENDIENTE**

### 2.1 Campos adicionales del candidato
Agregar al modelo `Candidate`:
- `work_authorization: str | None` (citizen / permanent_resident / work_visa / need_sponsorship)
- `availability: str | None` (immediate / 2_weeks / 1_month / 3_months)
- `career_goals: str | None`
- `salary_min_usd: int | None` (además del preference JSON existente)
- `languages: list[str] | None`

Migración Alembic 007.

### 2.2 Conflict resolution UI
Mostrar `conflicts` del CandidateProfile en `/profile`.
Usuario puede elegir cuál valor es correcto → queda registrado en `user_decision`.

### 2.3 Standard application answers
Nueva entidad `CandidateAnswer`:
- question (tipo semántico: "why_company" / "salary_expectation" / "work_auth" / etc.)
- answer (texto libre del candidato)
- Usado como input en form field mapping

Migración Alembic 008.

### 2.4 Profile Quality Score
Separar del health score:
- Evidence Coverage: qué porcentaje de skills tiene evidencia en EvidenceRecord
- Achievement Quality: porcentaje de experiencias con logros cuantificables
- Source Consistency: contradicciones entre fuentes detectadas

---

## Fase 3 — Job Intelligence 2.0 (≈1-2 días)

> Estado: **PENDIENTE**

### 3.1 Company Intelligence
Nueva entidad `CompanyProfile`:
- company_name, industry, size, business_model
- culture_signals, tech_signals
- Separado de Job

### 3.2 Job deduplication
Antes de guardar: verificar (company, title, location) similar en últimos 30 días.
Hash de descripción normalizada.

### 3.3 MANDATORY / PREFERRED / INFERRED classification
El JobAgent debe clasificar requirements como MANDATORY / PREFERRED / INFERRED / UNKNOWN.
Hoy solo tiene must_have / nice_to_have.

---

## Fase 4 — Evidence System 2.0 (≈1-2 días)

> Estado: **PENDIENTE**

### 4.1 Evidence classification
Cambiar ClaimValidator de `verified/unverified` a:
- `SUPPORTED` — claim respaldado por evidencia fuerte
- `PLAUSIBLE` — claim plausible pero sin evidencia directa
- `UNSUPPORTED` — claim sin respaldo → rechazar

### 4.2 Evidence graph
Para cada claim en CV/cover letter/answers: trazar la ruta:
```
Candidate source → EvidenceRecord → Claim → Application content
```

### 4.3 Evidence confidence decay
Evidencia más antigua tiene menor peso.
Experiencia de hace 10 años != experiencia reciente para claims actuales.

---

## Fase 5 — Form Intelligence (≈3-5 días)

> Estado: **PENDIENTE** (requiere Playwright en producción)

### 5.1 ApplicationForm entity
```
ApplicationForm → Section → Field → Option
```
Cada Field: field_id, label, type, required, semantic_type, candidate_data_source

### 5.2 Form discovery
Playwright agent:
1. Abrir application URL
2. Detectar secciones, campos, labels, tipos
3. Clasificar semánticamente cada campo
4. Devolver ApplicationForm estructurado

### 5.3 Field → Candidate mapping
Mapear semantic_type a:
- DETERMINISTIC: `first_name → candidate.name`
- DERIVED_FROM_EVIDENCE: `years_python → calcular de experiencias`
- GENERATIVE: `why_company → LLM(candidate + job + company)`
- HUMAN_CONFIRMATION_REQUIRED: `visa_sponsorship`, `salary`, `relocation`

### 5.4 Human-in-the-loop
Para campos `HUMAN_CONFIRMATION_REQUIRED`:
- Mostrar al usuario qué campos necesitan su respuesta
- Guardar respuesta como CandidateAnswer para futuros usos

### 5.5 Form fill + validation
Completar campos automáticamente con confianza alta.
Validar antes de submit.

---

## Fase 6 — Submission + Confirmation (≈2-3 días)

> Estado: **PENDIENTE**

### 6.1 Submission entity
```
Submission: application_id, form_id, submitted_at, confirmation_id, confirmation_text,
            final_url, status (SUBMITTED | SUBMISSION_UNCONFIRMED | FAILED)
```

### 6.2 Submit action
Playwright: click submit, detectar página de confirmación.

### 6.3 Confirmation capture
Capturar: texto de confirmación, ID, URL resultante.
Solo marcar SUBMITTED con evidencia suficiente.

---

## Fase 7 — Golden E2E (≈2 días)

> Estado: **PENDIENTE**

Test Playwright completo:
```
Register → Upload CV → Build Profile → Search Jobs → Match → Strategy
→ CV → Cover Letter → Open Form → Fill → Confirm → Track → Outcome
```

Este es el acceptance test principal del producto.

---

## Fase 8 — Learning Loop real (≈1-2 días)

> Estado: **PENDIENTE**

Usar los outcomes registrados para ajustar pesos del motor:
- Outcomes acumulados por (match_tier, skill_overlap_score range)
- A/B experiment: pesos ajustados vs baseline
- Solo en producción con aprobación humana

---

## Fase 9 — AI Evaluation + Real Smoke Tests (≈2-3 días)

> Estado: **PENDIENTE**

```
evals/
├── synthetic_candidates/   # 20 candidatos sintéticos
├── jds/                    # 50 JDs de ejemplo
├── test_extraction.py      # profile extraction accuracy
├── test_matching.py        # matching semantic accuracy
├── test_cv.py              # CV personalization + hallucination
└── test_form.py            # form field mapping accuracy
```

---

## KPIs de seguimiento

| Métrica | Objetivo |
|---------|----------|
| Tests pasando | ≥90% en todo momento |
| Rate limiting activo | ✅ antes de deploy |
| Hard constraints catching rate | >95% de casos bloqueantes |
| CV hallucination rate | <2% en evals |
| Form field mapping accuracy | >85% en evals |
| Application → Interview rate | Métrica de negocio real |
