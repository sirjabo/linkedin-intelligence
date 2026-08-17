# ATS CAPABILITY MATRIX
**Fecha**: 2026-08-17  
**Branch**: `claude/new-session-ce0sct`

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| `PASS` | Implementado y testeado (al menos con mock) |
| `PARTIAL` | Implementado pero con gaps o solo testeado con mocks |
| `FAIL` | No funciona o no implementado |
| `N/A` | No aplica para este ATS |
| `UNTESTED` | Código existe pero sin ningún test real |

**IMPORTANTE**: Ningún `PASS` aquí proviene de validación contra ATS reales.  
Todo el testing fue contra mocks internos o unit tests con `AsyncMock`.  
La columna "Evidence" indica el nivel de confianza real.

---

## Matriz principal

| Capacidad | Greenhouse | Lever | Workday | Ashby | SmartRecruiters | Generic |
|-----------|-----------|-------|---------|-------|----------------|---------|
| URL detection | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` |
| before_discover() | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` |
| Form discovery | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` |
| Field classification | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` |
| normalize_field() | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `N/A` |
| Multi-step nav | `PARTIAL` | `N/A` | `PARTIAL` | `N/A` | `N/A` | `N/A` |
| iframe support | `N/A` | `PARTIAL` | `PARTIAL` | `N/A` | `N/A` | `UNTESTED` |
| File upload | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` |
| Custom questions | `UNTESTED` | `PARTIAL` | `UNTESTED` | `UNTESTED` | `UNTESTED` | `UNTESTED` |
| EEO detection | `PASS` | `N/A` | `UNTESTED` | `N/A` | `N/A` | `N/A` |
| Submit | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` |
| Confirmation | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` |
| Confirmation ID | `PARTIAL` | `N/A` | `PARTIAL` | `N/A` | `N/A` | `N/A` |
| Resume/pause | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` |
| aria-label fallback | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` |
| Retry on failure | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` |
| Stale element recovery | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` |
| Dynamic DOM waits | `PARTIAL` | `PARTIAL` | `FAIL` | `PARTIAL` | `FAIL` | `FAIL` |
| Dialog/popup handling | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` |
| Session persistence | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` |

---

## Detalle por ATS

### Greenhouse

**Riesgo**: MEDIO  
**URL pattern**: `boards.greenhouse.io/[company]/jobs/[id]`

| Capacidad | Estado | Evidencia | Gaps |
|-----------|--------|-----------|------|
| URL detection | `PASS` | unit test con regex | — |
| before_discover: GDPR banner | `PASS` | unit test con mock | click puede fallar si selector cambia |
| EEO section detection | `PASS` | unit test con section_title | no testeado con HTML real |
| normalize_field: label overrides | `PASS` | unit test | solo 3 overrides hardcodeados |
| Multi-step navigation | `PARTIAL` | unit test con mock browser | no testeado con form real |
| CV/file upload | `PARTIAL` | mock ATS básico | no testeado con PDF real |
| Custom questions | `UNTESTED` | código existe | ningún test |
| Submit + confirmation | `PARTIAL` | mock ATS con /confirm endpoint | no testeado en Greenhouse real |
| Confirmation ID (regex) | `PARTIAL` | pattern `application.*id.*([A-Z0-9-]{4,})` | no validado contra respuesta real |

**Veredicto**: Código sólido, pero **cero validación real**. Necesita al menos 10 flows reales antes de declarar soporte.

---

### Lever

**Riesgo**: MEDIO  
**URL pattern**: `jobs.lever.co/[company]/[uuid]`

| Capacidad | Estado | Evidencia | Gaps |
|-----------|--------|-----------|------|
| URL detection | `PASS` | unit test | — |
| before_discover: navigate to /apply | `PASS` | unit test | — |
| iframe detection y switch | `PARTIAL` | unit test con mock | no testeado en iframe real |
| normalize_field: passthrough | `PASS` | unit test | — |
| Validation error scraping | `PARTIAL` | unit test | keywords en inglés solo |
| Custom questions | `PARTIAL` | `custom_question_labels` existe | no hay logic de clasificación diferenciada |
| File upload | `PARTIAL` | code exists | no testeado |
| Submit | `PARTIAL` | mock ATS | no en Lever real |

**Veredicto**: iframe es el riesgo principal. Lever tiene variantes sin iframe que pueden romperse con la lógica actual de `switch_to_frame`.

---

### Workday

**Riesgo**: ALTO ⚠️  
**URL pattern**: `[company].wd1.myworkdayjobs.com` / `workday.com`

| Capacidad | Estado | Evidencia | Gaps |
|-----------|--------|-----------|------|
| URL detection | `PASS` | unit test | — |
| before_discover: Apply button click | `PASS` | unit test | 6 selectores definidos |
| aria_label preference | `PASS` | unit test `normalize_field` | — |
| Multi-step navigation | `PARTIAL` | unit test con mock | sin validación en wizard real |
| Dynamic components (dropdowns) | `FAIL` | no implementado | Workday usa custom dropdowns no-standard |
| Section progression | `PARTIAL` | `section_history` tracked | no validado en flujo real |
| Session persistence | `PARTIAL` | pause/resume genérico | Workday expira sesiones rapidamente |
| Confirmation | `PARTIAL` | regex `WD[-]?(\d{7,})` | no validado contra respuesta real |

**Veredicto**: **Workday debe marcarse PARTIAL** en todos los escenarios de producción hasta evidencia real.  
Los custom dropdowns de Workday (no son `<select>` estándar) son el blocker principal.  
El timeout de sesión de Workday (~20 min) puede romper flows largos.

---

### Ashby

**Riesgo**: BAJO-MEDIO  
**URL pattern**: `jobs.ashbyhq.com/[company]/[uuid]`

| Capacidad | Estado | Evidencia | Gaps |
|-----------|--------|-----------|------|
| URL detection | `PASS` | unit test | — |
| before_discover: navigate to /application | `PASS` | unit test | skip si ya en /application |
| Apply button click | `PASS` | unit test | — |
| normalize_field: passthrough | `PASS` | unit test | — |
| Custom questions | `UNTESTED` | — | Ashby tiene custom Q complejas |
| Submit | `PARTIAL` | hereda generic submit | no testeado en Ashby real |

**Veredicto**: Ashby es más simple que Workday pero sigue sin validación real.

---

### SmartRecruiters

**Riesgo**: BAJO-MEDIO  
**URL pattern**: `careers.smartrecruiters.com/[company]`

| Capacidad | Estado | Evidencia | Gaps |
|-----------|--------|-----------|------|
| URL detection | `PASS` | unit test | — |
| before_discover: cookie banner | `PASS` | unit test (no error si no hay) | — |
| Apply button click | `PARTIAL` | unit test | click puede fallar si button dinámico |
| normalize_field: passthrough | `PASS` | — | — |
| Custom questions | `UNTESTED` | — | SmartRecruiters tiene Q dinámicas |
| Submit | `PARTIAL` | hereda generic | no testeado |

**Veredicto**: Menor complejidad que Workday pero sin validación real.

---

### Generic Forms

**Riesgo**: VARIABLE  

| Capacidad | Estado | Evidencia | Gaps |
|-----------|--------|-----------|------|
| Form discovery: labels | `PASS` | mock ATS — PASS | — |
| Form discovery: aria-label | `PASS` | testeado | — |
| Form discovery: placeholder | `PARTIAL` | código existe | sin test específico |
| select/radio/checkbox | `PARTIAL` | mock ATS básico | no exhaustivo |
| file input | `PARTIAL` | mock ATS | — |
| Dynamic fields | `FAIL` | no implementado | — |
| Conditional fields | `FAIL` | no implementado | — |
| JS redirect post-submit | `UNTESTED` | — | — |
| Stale DOM recovery | `FAIL` | no implementado | — |

---

## Mock ATS Lab — Cobertura actual vs objetivo

El mock ATS lab (`tests/mock_ats/server.py`) cubre actualmente:

| # | Escenario | Cubierto |
|---|-----------|---------|
| 1 | simple (text, email, tel) | ✅ |
| 2 | optional fields | ✅ |
| 3 | required fields | ✅ |
| 4 | select dropdown | ✅ |
| 5 | multi-select | ❌ |
| 6 | radio buttons | ❌ |
| 7 | checkbox | ✅ |
| 8 | textarea | ✅ |
| 9 | number input | ❌ |
| 10 | URL input | ✅ |
| 11 | date input | ❌ |
| 12 | file upload | ✅ (básico) |
| 13 | two-step form | ❌ |
| 14 | five-step form | ❌ |
| 15 | iframe | ❌ |
| 16 | dynamic field | ❌ |
| 17 | conditional field | ❌ |
| 18 | hidden field | ❌ |
| 19 | validation error | ❌ |
| 20 | async-loaded field | ❌ |
| 21 | custom essay | ❌ |
| 22 | salary | ❌ |
| 23 | sponsorship | ❌ |
| 24 | work authorization | ✅ |
| 25 | demographic | ❌ |
| 26 | unknown field | ❌ |
| 27 | JS redirect | ❌ |
| 28 | delayed confirmation | ❌ |
| 29 | failed submission | ❌ |
| 30 | browser crash simulation | ❌ |
| 31 | resume after crash | ❌ |
| 32 | duplicate submit protection | ❌ |
| 33 | expired session | ❌ |
| 34 | stale DOM | ❌ |
| 35 | selector changed mid-flow | ❌ |

**Cobertura actual**: 9/35 (26%)  
**Objetivo para beta**: 25/35 (71%)

---

## Plan de validación real (Sprint PR-3)

Para declarar soporte real, ejecutar contra URLs públicas en modo PRE-SUBMIT:

```
50–100 job flows distribuidos:
  Greenhouse: 15 flows
  Lever: 15 flows
  Workday: 10 flows (HIGH RISK)
  Ashby: 5 flows
  SmartRecruiters: 5 flows
  Generic: 10 flows
```

Registrar por cada flow:
```
ATS | URL | Form discovered? | Fields found | Fields classified
Auto-filled | Human-required | Files uploadable | Validation passed
Submit attempted? | Confirmation detected? | Errors | Duration
```

**Métrica objetivo**:
```
Form discovery >= 95%
Field classification >= 95%
Auto-fill correctness >= 98%
Confirmation detection >= 95%
```

---

*Para el roadmap de hardening: ver `docs/PRODUCTION_HARDENING_ROADMAP.md`*
