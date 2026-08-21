# PRODUCTION SCORECARD
**Fecha**: 2026-08-17  
**Branch**: `claude/new-session-ce0sct`  
**Tests**: 594 passing, 0 failing

---

## Metodología de scoring

Cada categoría se puntúa de 0 a 100.  
Ponderación basada en riesgo de producción.

| Nivel | Rango | Interpretación |
|-------|-------|---------------|
| 🟢 Ready | 90–100 | Listo para producción |
| 🟡 Acceptable | 75–89 | Listo con monitoreo activo |
| 🟠 At Risk | 50–74 | Necesita trabajo antes de producción |
| 🔴 Blocker | 0–49 | Bloquea release |

**Threshold de release**:  
`overall >= 90 AND no category < 85`

---

## Scorecard actual

### 1. Backend Reliability — Score: **62 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| API routes funcionan | 90 | Tests E2E básicos pasan |
| Error handling | 70 | AgentError existe; sin error taxonomy |
| Retry logic | 20 | No existe en browser/forms |
| Duplicate submit protection | 10 | No existe estructuralmente |
| Pre-submit validator | 20 | Solo HTML5 browser check |
| Session resilience | 55 | pause/resume implementado; crash no testeado |
| Database integrity | 80 | SQLAlchemy + migrations robustos |

**Bloqueadores**: retry logic, duplicate protection, pre-submit validator

---

### 2. AI Quality — Score: **35 / 100** 🔴

| Sub-item | Score | Nota |
|----------|-------|------|
| CV factuality | 0 | No evaluado con modelo real |
| CV personalization | 0 | No evaluado con modelo real |
| Evidence support rate | 0 | No evaluado con modelo real |
| Cliché avoidance | 0 | Test existe pero skipped sin API key |
| Matching quality | 0 | No calibrado con datos reales |
| Job requirement extraction | 0 | No evaluado con modelo real |
| Mocks disponibles | 100 | Todo testeado con mocks |

**Nota**: El score bajo no significa que la AI no funcione — significa que **no tenemos evidencia** de que funcione. Sin ANTHROPIC_API_KEY en CI, esta categoría no puede superar 35.

**Bloqueador crítico**: ejecutar AI evals con API key real.

---

### 3. Matching Quality — Score: **50 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| Requirement extraction | 60 | Implementado; sin calibración real |
| MATCHED precision | 0 | Sin dataset de evaluación |
| BLOCKER FP rate | 0 | Sin medición |
| Semantic similarity | 70 | TF-cosine implementado |
| Embedding similarity | 60 | SemanticMatcher implementado |
| Evidence coverage | 50 | evidence_refs plural implementado |
| Two "semantic" concepts | -10 | Penalización por ambigüedad conceptual |

**Bloqueador**: calibration dataset; unificar definición de "semantic"; medir BLOCKER FP rate

---

### 4. CV Quality — Score: **55 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| Personalization logic | 80 | cv_agent implementado |
| Differentiation test | 0 | No existe (1 candidato × 3 JDs) |
| Factuality check | 70 | claim_validator implementado |
| Evidence refs populated | 60 | evidence_refs plural; sin garantía de llenado |
| Real-model eval | 0 | No ejecutado |
| Hallucination protection | 70 | ClaimValidator bloquea contradictions |

**Bloqueador**: differentiation test; real-model eval

---

### 5. ATS Reliability — Score: **30 / 100** 🔴

| Sub-item | Score | Nota |
|----------|-------|------|
| Greenhouse (mock) | 70 | Pasa mock ATS |
| Lever (mock) | 65 | iframe parcial |
| Workday (mock) | 50 | Sin custom dropdown support |
| Ashby (mock) | 65 | Básico |
| SmartRecruiters (mock) | 60 | Básico |
| Generic (mock) | 55 | 9/35 escenarios cubiertos |
| Validación real | 0 | Cero flows reales ejecutados |
| Mock ATS lab cobertura | 26 | 9/35 escenarios (26%) |

**Bloqueador crítico**: cero validación real; cobertura de mock lab insuficiente

---

### 6. Browser Reliability — Score: **40 / 100** 🔴

| Sub-item | Score | Nota |
|----------|-------|------|
| Navigate + form discovery | 75 | PlaywrightAdapter funcional |
| Fill text/select | 70 | Implementado |
| File upload | 55 | Implementado; sin test E2E real |
| Retry en fill | 0 | No implementado |
| Stale element recovery | 0 | No implementado |
| Selector fallback | 10 | aria-label como fallback en clasificación, no en fill |
| Dynamic DOM waits | 30 | Solo domcontentloaded wait |
| Dialog/popup handling | 0 | No implementado |
| iframe completo | 40 | switch_to_frame parcial |
| Memory cleanup | 60 | context manager implementado |

**Bloqueador**: retry, stale recovery, dynamic DOM waits, popup handling

---

### 7. Submission Reliability — Score: **50 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| submit() funciona en mock | 75 | PASS |
| human_confirmed guard | 90 | Hardcoded |
| Duplicate protection | 5 | No implementado |
| Confirmation detection | 55 | JS keywords; sin SUBMITTED_CONFIRMED enum |
| Confirmation ID extraction | 60 | Regex funcional en mock |
| Submit retry | 0 | No implementado |
| Submit timeout | 30 | Solo timeout implícito del browser |

**Bloqueador**: duplicate protection; confirmar distinción SUBMITTED_CONFIRMED vs SUBMISSION_UNCONFIRMED

---

### 8. Frontend UX — Score: **55 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| Application list | 80 | Implementado |
| Application detail | 70 | Flujo agente implementado |
| Start → awaiting_human | 75 | Funciona |
| Answer pending fields | 70 | UI implementada |
| Confirm + Submit | 75 | Botón explícito |
| View confirmation | 60 | Básico |
| Track outcome | 50 | Solo status; sin timeline rico |
| Pre-submit review | 20 | No hay pantalla de pre-submit review |
| Frontend tests | 0 | Cero tests de frontend |

**Bloqueador**: pantalla de pre-submit review; frontend tests

---

### 9. Security — Score: **65 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| Auth + ownership | 85 | JWT + ownership checks |
| SSRF protection | 80 | ssrf.py implementado |
| Rate limiting | 75 | limiter.py implementado |
| Prompt injection | 30 | Sin sanitización de form fields hacia LLM |
| Malicious file upload | 40 | Sin validación de contenido de archivo |
| Browser isolation | 50 | Playwright context aislado; sin sandbox extra |
| Secrets handling | 80 | env vars; sin hardcoded keys |
| Security review formal | 0 | Pendiente |

**Bloqueador**: prompt injection; formal security review

---

### 10. Privacy — Score: **50 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| Sin PII en logs | 70 | structlog con campos controlados |
| Screenshots retention | 10 | Sin retention policy |
| Candidate data deletion | 30 | Sin endpoint de borrado |
| CV storage policy | 30 | Sin retention |
| Privacy review formal | 0 | Pendiente |

**Bloqueador**: retention policy; privacy review formal

---

### 11. Observability — Score: **60 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| Structured logging | 80 | structlog en todo el backend |
| Cost tracking | 65 | cost_tracker.py |
| Application fields metrics | 70 | fields_total, fields_auto_filled |
| application_id en todos los eventos | 40 | No consistente |
| Duration tracking | 30 | Sin timestamps de inicio/fin por step |
| retry_count tracking | 0 | No existe |
| Budget alert | 0 | No existe |
| Error codes estructurados | 0 | Sin error taxonomy |

**Bloqueador**: application_id consistente; error taxonomy; budget alert

---

### 12. Cost — Score: **45 / 100** 🟠

| Sub-item | Score | Nota |
|----------|-------|------|
| Cost estimado por llamada | 80 | cost_tracker por modelo |
| Cost por application | 0 | Sin agregado por application_id |
| Budget alert | 0 | No implementado |
| Model routing validado | 50 | model_router existe; sin test de routing |
| Fast vs Reasoning model | 60 | Configurado; sin validación |

**Bloqueador**: cost por application; budget alert

---

## Overall Score

| Categoría | Score | Peso | Ponderado |
|-----------|-------|------|----------|
| Backend Reliability | 62 | 15% | 9.3 |
| AI Quality | 35 | 20% | 7.0 |
| Matching Quality | 50 | 10% | 5.0 |
| CV Quality | 55 | 10% | 5.5 |
| ATS Reliability | 30 | 15% | 4.5 |
| Browser Reliability | 40 | 10% | 4.0 |
| Submission Reliability | 50 | 5% | 2.5 |
| Frontend UX | 55 | 5% | 2.75 |
| Security | 65 | 5% | 3.25 |
| Privacy | 50 | 2% | 1.0 |
| Observability | 60 | 2% | 1.2 |
| Cost | 45 | 1% | 0.45 |

**OVERALL: 46.45 / 100** 🔴

---

## Veredicto

```
PRODUCCIÓN: NO READY
BETA CONTROLADA: NO READY
STAGING + DOGFOODING: POSIBLE con mitigaciones

Blockers P0 (bloquean todo release):
  1. AI Quality: cero evaluación con modelo real
  2. ATS Reliability: cero validación contra ATS reales
  3. Browser: sin retry / stale recovery
  4. Duplicate submit: no protegido

Blockers P1 (bloquean beta):
  5. Pre-submit validator estructurado
  6. Mock ATS lab < 30% cobertura
  7. Evidence "semantic" ambiguo
  8. CI/CD inexistente
  9. Frontend sin tests

Target para beta:
  Overall >= 75
  AI Quality >= 85 (requiere API key en CI)
  ATS Reliability >= 70 (requiere 50 flows reales)
  Browser Reliability >= 70 (requiere retry + stale)
```

---

## Evolución esperada por Sprint

| Sprint | Acción | Score esperado |
|--------|--------|---------------|
| Actual (hoy) | Baseline | **46** 🔴 |
| PR-1 | Audit + docs | 46 (sin código nuevo) |
| PR-2 | Evidence unify + AI evals reales | **58** 🟠 |
| PR-3 | ATS real validation + mock lab 70% | **67** 🟠 |
| PR-4 | File upload E2E + pre-submit + duplicate | **74** 🟠 |
| PR-5 | Browser retry + stale + resilience | **80** 🟡 |
| PR-6 | Frontend complete | **83** 🟡 |
| PR-7 | Observability + security + privacy + cost | **87** 🟡 |
| PR-8 | Golden E2E + CI/CD + beta release | **91** 🟢 |

---

*Última actualización: 2026-08-17 — actualizar con cada sprint completado*
