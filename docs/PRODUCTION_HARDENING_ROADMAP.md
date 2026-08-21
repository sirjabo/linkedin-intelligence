# PRODUCTION HARDENING ROADMAP
**Fecha**: 2026-08-17  
**Score actual**: 46 / 100 🔴  
**Score objetivo beta**: 91 / 100 🟢  
**Fuente**: `docs/PRODUCTION_READINESS_AUDIT.md` + `docs/PRODUCTION_SCORECARD.md`

---

## Principio de trabajo en esta fase

```
TEST REALISTICALLY → FIND BUG → FIX → ADD REGRESSION TEST → RE-RUN
```

No agregar features nuevas. Solo hardening, evidencia y fixes.

---

## Sprint PR-1 — Audit + Docs ✅ (este sprint)

**Entregables**:
- [x] `docs/PRODUCTION_READINESS_AUDIT.md`
- [x] `docs/ATS_CAPABILITY_MATRIX.md`
- [x] `docs/PRODUCTION_SCORECARD.md`
- [x] `docs/PRODUCTION_HARDENING_ROADMAP.md`
- [ ] Full test suite ejecutado con resultados (594 passing — hecho)
- [ ] Real AI evals con API key — **PENDIENTE** (no hay API key en este env)
- [ ] Release blockers identificados — **HECHO** (ver sección Blockers)
- [ ] Bugs priorizados — **HECHO** (ver sección Bugs P0)

**Score al final de PR-1**: 46 (sin nuevo código; solo visibilidad)

---

## Sprint PR-2 — Evidence + Matching + AI Evals reales

**Objetivo**: Eliminar ambigüedad semántica; calibrar matching; ejecutar AI evals.

### P0: Unificar "semantic" en Evidence System

**Problema**: Dos sistemas llamados "semantic":
- `claim_validator._semantic_similarity()` → TF-cosine (lexical, no semántico)
- `matching/semantic.SemanticMatcher` → embeddings reales

**Fix**:
1. Renombrar `_semantic_similarity()` → `_lexical_similarity()` en `claim_validator.py`
2. Crear output estructurado de validación:
   ```python
   @dataclass
   class ClaimScore:
       lexical_score: float
       semantic_score: float | None  # None si no hay embeddings
       temporal_consistent: bool
       contradicted: bool
       final_status: Literal["SUPPORTED", "PLAUSIBLE", "UNVERIFIED", "CONTRADICTED"]
   ```
3. Tests: `test_claim_validator.py` con assert sobre `ClaimScore.lexical_score`

**Archivos**: `app/services/claim_validator.py`, `app/services/matching/semantic.py`

### P0: Calibrar Matching Engine

**Problema**: Sin dataset de evaluación; BLOCKER false-positive rate desconocido.

**Fix**:
1. Crear `tests/fixtures/matching_calibration.py` con ≥20 pares (JD snippet, CV snippet, expected_label)
2. Correr engine sobre fixtures; calcular precision/recall/FP rate
3. Ajustar thresholds si BLOCKER FP > 2%

**Archivos**: `app/services/matching/engine.py`, nuevo `tests/test_matching_calibration.py`

### P0: Ejecutar AI evals con API key

**Problema**: 8 de 11 AI tests skipped. Sin evidencia de quality real.

**Fix**:
1. Configurar `ANTHROPIC_API_KEY` en entorno de test (o CI)
2. Correr `pytest tests/test_ai_evaluation_suite.py -v` sin skip
3. Registrar: modelo, tokens input/output, latency, costo, resultado
4. Documentar en `docs/AI_EVAL_RESULTS.md`

**Target**:
```
CV factuality >= 0.95
CV personalization >= 0.80
Cliché avoidance >= 0.90
Company hook present = 100%
```

### P1: CV Differentiation Test

**Fix**:
1. Test: 1 candidato fijo + 3 JDs distintos (senior data eng, junior frontend, PM)
2. Generar 3 CVs personalizados
3. Assert: summary no es idéntico entre los 3; skills ordenadas diferente
4. Archivo: `tests/test_cv_differentiation.py`

**Score esperado al final de PR-2**: 58 / 100

---

## Sprint PR-3 — ATS Real-World Validation + Mock Lab

**Objetivo**: Primera evidencia real de que los adapters funcionan.

### P0: Expandir Mock ATS Lab a 70% cobertura

Agregar a `tests/mock_ats/server.py`:

| Prioridad | Escenario | Implementación |
|-----------|-----------|---------------|
| P0 | two-step form (`/step1` → `/step2` → `/confirm`) | Nuevo endpoint |
| P0 | five-step form | Nuevo endpoint |
| P0 | validation error (campo requerido vacío) | Respuesta 422 con mensaje |
| P0 | failed submission | Respuesta 500 |
| P0 | duplicate submit protection | Idempotency key check |
| P1 | iframe form | `<iframe>` que embedda form |
| P1 | radio buttons | `<input type="radio">` |
| P1 | multi-select | `<select multiple>` |
| P1 | number input | `<input type="number">` |
| P1 | date input | `<input type="date">` |
| P1 | conditional field | JS que muestra campo B si A = "yes" |
| P1 | dynamic load | Campo que aparece 2s después |
| P2 | salary field | `<input name="salary">` |
| P2 | sponsorship field | `<select name="sponsorship">` |
| P2 | delayed confirmation | Redirect 3s después de submit |
| P2 | expired session | 401 si token expirado |
| P2 | selector changed | Campo que cambia ID mid-flow |

### P0: Validation Program Real (pre-submit only)

Ejecutar contra URLs reales en modo discovery + clasificación (sin submit):

```
15 jobs en Greenhouse
15 jobs en Lever  
10 jobs en Workday (HIGH RISK)
5 jobs en Ashby
5 jobs en SmartRecruiters
10 forms genéricos
```

Registrar en `docs/ATS_VALIDATION_LOG.md`:
```
| ATS | URL | Fields found | Classified | Errors |
```

**Acceptance criteria**:
```
Form discovery >= 95% (≥57/60)
Field classification >= 90% (por lote)
```

### P1: Fixture de forms reales por ATS

Para cada ATS donde se encontraron bugs, crear fixture HTML en `tests/fixtures/ats_forms/`:
- `greenhouse_sample.html`
- `lever_sample.html`
- `workday_sample.html`

Usar estos fixtures en tests de clasificación (sin browser real).

**Score esperado al final de PR-3**: 67 / 100

---

## Sprint PR-4 — File Upload + Pre-submit + Duplicate Protection

**Objetivo**: Cerrar los tres blockers más directamente relacionados con safety.

### P0: Pre-submit Validator estructurado

Crear `app/services/pre_submit_validator.py`:

```python
@dataclass
class PreSubmitResult:
    passed: bool
    blocks: list[str]  # razones de bloqueo

class PreSubmitValidator:
    def validate(self, session, form, profile) -> PreSubmitResult:
        blocks = []
        # 1. Required fields completos
        for field in form.fields:
            if field.is_required and not field.resolved_value:
                blocks.append(f"required field empty: {field.label}")
        # 2. Files attached
        if not session.cv_file_uploaded:
            blocks.append("CV file not uploaded")
        # 3. No contradicted claims
        if session.has_contradicted_claims:
            blocks.append("contradicted claims in CV")
        # 4. Sensitive fields confirmed
        for field in form.fields:
            if field.semantic_type in SENSITIVE_TYPES and not field.human_confirmed:
                blocks.append(f"sensitive field not confirmed: {field.label}")
        return PreSubmitResult(passed=not blocks, blocks=blocks)
```

Integrar en `submit()` antes de `session.status = "submitting"`.

Tests: `tests/test_pre_submit_validator.py` con cada condición de bloqueo.

### P0: Duplicate Submit Protection

En `submit()` del orchestrator:

```python
if session.status in ("submitting", "submitted"):
    raise AgentError(f"Cannot submit: session already in status '{session.status}'")
```

Test: intento de doble submit → error.

### P0: File Upload E2E Test

Test que:
1. Abre el mock ATS con Playwright (si Chromium disponible)
2. Genera un PDF de CV real via `cv_storage.py`
3. Hace upload via `playwright_adapter.upload_file()`
4. Verifica que el form fue enviado con el archivo

Agregar al mock ATS: endpoint que responde con el filename del archivo recibido.

### P0: Sensitive Fields Coverage

Auditar `_ALWAYS_HUMAN` en `form_intelligence.py`.

Verificar que incluye:
- `salary`, `salary_expectation`, `salary_range`
- `sponsorship`, `visa_sponsorship`
- `work_authorization`, `work_auth`
- `relocation`, `relocation_willing`
- `demographic`, `race`, `ethnicity`, `gender`, `disability`
- `veteran_status`

Test explícito: cada uno de estos → `resolution_type = HUMAN_REQUIRED`.

**Score esperado al final de PR-4**: 74 / 100

---

## Sprint PR-5 — Session Resilience + Browser Hardening

**Objetivo**: El sistema no debe caerse ni perder estado ante condiciones adversas.

### P0: Browser Retry Strategy

En `PlaywrightAdapter.fill_text()` y `click()`:

```python
async def fill_text(self, css_selector, value, retries=3) -> bool:
    for attempt in range(retries):
        try:
            await target.locator(css_selector).first.fill(value, timeout=5_000)
            return True
        except TimeoutError:
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
        except Exception as exc:
            logger.warning("fill_failed", selector=css_selector, attempt=attempt, error=str(exc))
            break
    return False
```

Test: fill en elemento que tarda 2s → retry → success.

### P0: Stale Element Recovery

En form fill loop del orchestrator:
```python
# Si fill falla 3 veces → re-discover el campo por aria-label/name
# Si aún falla → marcar campo como HUMAN_REQUIRED
```

Test: mock browser que falla 2 veces, luego funciona.

### P1: Migrar pause metadata a columna estructurada

En `ApplicationAgentSession`:
```python
pause_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Sacar el JSON de `error_message` (campo de texto string) → columna dedicada.

Migración Alembic: `021_pause_metadata.py`.

### P1: Dynamic DOM Waits

En `PlaywrightAdapter`:
```python
async def wait_for_element(self, selector, timeout=10_000) -> bool:
    try:
        await self._page.wait_for_selector(selector, timeout=timeout)
        return True
    except TimeoutError:
        return False
```

Usar antes de fill en campos que pueden cargarse dinámicamente.

### P1: Dialog/Popup Handling

```python
async def __aenter__(self):
    ...
    self._page.on("dialog", lambda d: asyncio.create_task(d.dismiss()))
```

Descartar diálogos automáticamente para no bloquear el flow.

### P2: Crash Simulation Test

Test que:
1. Inicia session (status=filling)
2. "Mata" el proceso (simula crash via KeyboardInterrupt capturado)
3. Crea nueva instancia del orchestrator
4. Llama `resume()` en la misma session_id
5. Verifica que el estado es correcto

**Score esperado al final de PR-5**: 80 / 100

---

## Sprint PR-6 — Application Control Center Frontend

**Objetivo**: El flujo completo es navegable desde la UI.

### P1: Pantallas faltantes

| Pantalla | Estado actual | Acción |
|----------|--------------|--------|
| Pre-submit Review | NO existe | Crear `/applications/[id]/review` |
| Track Outcome | Básico | Expandir con timeline |
| Answer Pending Fields | Existe | Mejorar UX |
| Upload Status | NO existe | Crear indicador de upload |

### P1: UX de campos pendientes

Mostrar:
```
22 fields detected
19 auto-resolved
3 need your confirmation
```

No mostrar detalles técnicos del resolver.

### P2: Frontend tests básicos

Agregar al menos:
- Test de que `/applications/[id]` renderiza sin error
- Test de que el botón "Confirmar y Enviar" requiere confirmación explícita

**Score esperado al final de PR-6**: 83 / 100

---

## Sprint PR-7 — Observability + Security + Privacy + Cost

**Objetivo**: El sistema es observable, seguro y cuesta lo que debe costar.

### P1: Error Taxonomy

Crear `app/core/error_codes.py`:

```python
class ErrorCode(str, Enum):
    ATS_UNSUPPORTED = "ATS_UNSUPPORTED"
    FORM_NOT_FOUND = "FORM_NOT_FOUND"
    FIELD_UNRESOLVED = "FIELD_UNRESOLVED"
    FILE_UPLOAD_FAILED = "FILE_UPLOAD_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    BROWSER_TIMEOUT = "BROWSER_TIMEOUT"
    BROWSER_CRASHED = "BROWSER_CRASHED"
    SUBMIT_FAILED = "SUBMIT_FAILED"
    SUBMISSION_UNCONFIRMED = "SUBMISSION_UNCONFIRMED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    LLM_ERROR = "LLM_ERROR"
    EVIDENCE_BLOCKED = "EVIDENCE_BLOCKED"
    DUPLICATE_SUBMIT = "DUPLICATE_SUBMIT"
    PRE_SUBMIT_BLOCKED = "PRE_SUBMIT_BLOCKED"
```

Reemplazar strings libres de error en `AgentError`.

### P1: application_id en todos los log events

En el orchestrator, añadir `application_id=` a todos los `logger.*` calls.

### P1: Cost per Application

En `cost_tracker.py`:
```python
def session_summary(application_id: str) -> dict:
    records = [r for r in _records if r.application_id == application_id]
    return {
        "application_id": application_id,
        "total_cost_usd": sum(r.cost_usd for r in records),
        "calls": len(records),
        "models_used": list({r.model for r in records}),
    }
```

### P1: Budget Alert

Si `session_summary.total_cost_usd > settings.MAX_APPLICATION_COST_USD`:
```
logger.error("cost_budget_exceeded", ...)
```

### P2: Security Review formal

Completar `docs/SECURITY_PRODUCTION_REVIEW.md` con:
- SSRF: validar que ssrf.py cubre IPs internas y localhost
- Prompt injection: agregar sanitización de form field values antes de enviar al LLM
- File upload: validar mime type real (no solo extensión)
- Browser isolation: verificar que Playwright no tiene acceso a filesystem del host

### P2: Privacy Review formal

Completar `docs/PRIVACY_PRODUCTION_REVIEW.md` con:
- Screenshots: definir retention policy (max 30 días)
- CV stored: definir retention (max 90 días o delete on request)
- Logs: verificar que no hay PII en structlog fields

**Score esperado al final de PR-7**: 87 / 100

---

## Sprint PR-8 — Golden E2E + CI/CD + Beta Release

**Objetivo**: Release bloqueado por CI; Golden E2E obligatorio.

### P0: Golden E2E Test

Crear `tests/test_golden_e2e.py`:

```python
@pytest.mark.e2e
@pytest.mark.skipif(not CHROMIUM_AVAILABLE, reason="requires Chromium")
async def test_golden_e2e_complete_application_flow():
    """
    Full flow: candidate setup → job → JD parsing → matching → decision
    → strategy → CV personalization → evidence validation → cover letter
    → application answers → browser session → mock ATS form → field classification
    → knowledge resolution → file upload → human-required answers → pause
    → resume → validation → human confirmation → submit → confirmation → tracking
    """
    # 1. Setup candidate + profile
    # 2. Create job + parse JD (mocked LLM)
    # 3. Run matching
    # 4. Generate strategy + CV + cover letter (mocked LLM)
    # 5. Open mock ATS (multi-step form)
    # 6. Start agent session
    # 7. Verify fields discovered and classified
    # 8. Answer human-required fields
    # 9. Pause session
    # 10. Resume session
    # 11. Pre-submit validation → PASS
    # 12. Confirm + submit
    # 13. Verify confirmation detected
    # 14. Verify application.status = "applied"
    # 15. Verify ApplicationSubmission created
    pass  # implementar en PR-8
```

Este test debe pasar para release. Si falla → release bloqueado.

### P0: CI/CD Pipeline

Crear `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: ruff check .
      - run: pytest tests/ --ignore=tests/test_intelligence_phase.py -q
      - run: pytest tests/test_ai_evaluation_suite.py -v
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        if: github.event_name == 'push'
```

### P1: Health Check Endpoint

Verificar que `GET /api/health` existe y responde correctamente.  
Si no existe, crear en `app/api/routes/health.py`.

### P1: Release Tag

```bash
git tag v0.9-beta
git push origin v0.9-beta
```

Beta incluye:
- Full golden flow documentado
- Known limitations: Workday PARTIAL, sin retry en browser
- Logging activo
- Error reporting

**Score esperado al final de PR-8**: 91 / 100 🟢

---

## Bugs P0 (bloquean cualquier release)

| # | Bug | Archivo | Severidad | Sprint |
|---|-----|---------|----------|--------|
| B1 | Real-model evals nunca ejecutadas | `test_ai_evaluation_suite.py` | CRITICAL | PR-2 |
| B2 | Cero validación ATS real | `tests/mock_ats/` | CRITICAL | PR-3 |
| B3 | Sin duplicate submit protection | `orchestrator.py:466` | CRITICAL | PR-4 |
| B4 | Sin pre-submit validator estructurado | `orchestrator.py:458` | CRITICAL | PR-4 |
| B5 | "semantic" definido dos veces diferente | `claim_validator.py`, `matching/semantic.py` | HIGH | PR-2 |
| B6 | Campos sensibles sin test explícito | `form_intelligence.py` | CRITICAL | PR-4 |
| B7 | File upload sin test E2E | `playwright_adapter.py` | HIGH | PR-4 |

## Bugs P1 (bloquean beta)

| # | Bug | Archivo | Sprint |
|---|-----|---------|--------|
| B8 | Sin retry en browser fill | `playwright_adapter.py` | PR-5 |
| B9 | Sin stale element recovery | `playwright_adapter.py` | PR-5 |
| B10 | Pause metadata en error_message (frágil) | `orchestrator.py:265` | PR-5 |
| B11 | Sin error taxonomy | N/A (nuevo) | PR-7 |
| B12 | CI/CD inexistente | N/A (nuevo) | PR-8 |
| B13 | Mock ATS lab 26% cobertura | `tests/mock_ats/server.py` | PR-3 |
| B14 | BLOCKER FP rate desconocido | `matching/engine.py` | PR-2 |
| B15 | Sin SUBMITTED_CONFIRMED enum | `browser/adapter.py` | PR-4 |

---

## Definition of Done — Beta v0.9

```
✅ Golden E2E pasa
✅ Real AI evals pasan thresholds
✅ CV differentiation validada (1 candidato × 3 JDs)
✅ Evidence validation sin ambigüedad semántica
✅ Matching calibrado (BLOCKER FP < 2%)
✅ Generic ATS: mock lab ≥ 70% cobertura
✅ Greenhouse: ≥ 15 flows reales sin submit (discovery only)
✅ Lever: ≥ 15 flows reales
✅ Workday: marcado PARTIAL con gaps documentados
✅ CV upload E2E testeado
✅ Pause/resume testeado incluyendo crash
✅ Duplicate submit protegido + test
✅ Pre-submit validator con todos los checks
✅ Confirmation detection con SUBMITTED_CONFIRMED/UNCONFIRMED
✅ Frontend flujo completo navegable
✅ CI/CD bloqueando PRs en failures
✅ Security review completada
✅ Budget alert activo
✅ Overall score >= 90
```

---

*Actualizar este doc al final de cada sprint con: score alcanzado, blockers cerrados, nuevos bugs encontrados.*
