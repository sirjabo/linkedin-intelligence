# LinkedIn Intelligence — Application Agent Architecture

> Versión: 1.0  
> Fecha: 2026-08-14  
> Estado: Design — pendiente de implementation approval  
> Propósito: Diseñar la arquitectura para que el sistema convierta `USER PROFILE + JOB → REAL SUBMITTED APPLICATION`

---

## 1. Principios de diseño

1. **Separación de dominio y browser**: la lógica de negocio (qué llenar, cuándo pedir confirmación, qué es un campo válido) nunca debe acoplarse al DOM. El browser es un `adapter`, no el sistema.
2. **Human-in-the-loop por defecto**: cuando la confianza de auto-fill < threshold, siempre delegar al humano. Nunca inventar.
3. **Evidencia como ciudadana de primera clase**: cada campo llenado debe poder trazar su origen hasta un EvidenceRecord del candidato.
4. **Fail-safe**: si cualquier paso falla (browser crash, timeout, CAPTCHA), el estado se persiste y el flujo puede reanudarse.
5. **No submit sin confirmación humana**: el submit final siempre requiere aprobación explícita del usuario.

---

## 2. Arquitectura de capas

```
┌─────────────────────────────────────────────────────────────────────┐
│  API / Frontend                                                       │
│  POST /applications/{id}/agent/start                                  │
│  GET  /applications/{id}/agent/status                                 │
│  POST /applications/{id}/agent/confirm                               │
│  POST /applications/{id}/agent/submit                                 │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────┐
│  ApplicationAgentOrchestrator                                         │
│  Manages the full lifecycle: discover → map → fill → confirm → submit│
│  Persists state to ApplicationAgentSession                            │
└───┬────────────────────┬─────────────────────┬───────────────────────┘
    │                    │                      │
┌───▼──────────┐  ┌──────▼──────────┐  ┌──────▼──────────────────────┐
│ Form         │  │ Candidate       │  │ BrowserAutomationAdapter     │
│ Intelligence │  │ Knowledge       │  │ (Playwright)                 │
│ Service      │  │ Resolver        │  │                              │
│              │  │                 │  │ .open_url()                  │
│ .classify()  │  │ .resolve()      │  │ .discover_form()             │
│ .map_fields()│  │ .generate()     │  │ .fill_field()                │
│ .score_      │  │ .evidence_for() │  │ .upload_file()               │
│  confidence()│  │                 │  │ .submit()                    │
│              │  │                 │  │ .capture_confirmation()      │
└──────────────┘  └─────────────────┘  └──────────────────────────────┘
                          │
          ┌───────────────▼───────────────────┐
          │  ATSRegistry                       │
          │                                    │
          │  detect_ats(url) → ATSAdapter      │
          │                                    │
          │  GreenhouseAdapter                 │
          │  LeverAdapter                      │
          │  AshbyAdapter                      │
          │  WorkdayAdapter                    │
          │  GenericFormAgent (LLM fallback)   │
          └────────────────────────────────────┘
```

---

## 3. Entidades de dominio nuevas

### ApplicationAgentSession

```python
class ApplicationAgentSession(Base):
    __tablename__ = "application_agent_sessions"

    id: UUID
    application_id: UUID  # FK → applications
    application_url: str
    ats_provider: str | None  # "greenhouse" | "lever" | "ashby" | "workday" | "generic"
    
    # State machine
    status: str  # "initializing" | "discovering" | "mapping" | "awaiting_human" 
                 # | "ready_to_fill" | "filling" | "awaiting_confirm" 
                 # | "submitting" | "submitted" | "failed"
    
    # Discovery results
    raw_form_json: dict | None  # Raw form structure from browser
    sections: list[dict] | None  # Detected sections
    
    # Progress
    fields_total: int
    fields_auto_filled: int
    fields_human_pending: int
    fields_confirmed: int
    
    # Submission evidence
    screenshot_pre_submit: str | None  # path or URL
    screenshot_confirmation: str | None
    confirmation_text: str | None
    confirmation_id: str | None  # extracted from page
    final_url: str | None
    
    error_message: str | None
    retry_count: int
    
    created_at: datetime
    updated_at: datetime
```

### ApplicationFormSection

```python
class ApplicationFormSection(Base):
    __tablename__ = "application_form_sections"
    
    id: UUID
    form_id: UUID  # FK → application_forms
    title: str | None  # "Personal Information", "Experience", "Custom Questions"
    order: int
    step_url: str | None  # URL if multi-step form
    is_completed: bool
```

### CandidateAnswer (Application Knowledge Base)

```python
class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"
    
    id: UUID
    candidate_id: UUID
    
    # Semantic type of the question
    question_type: str  # "salary_expectation" | "work_authorization_text" | 
                        # "relocation_willingness" | "why_interested_general" |
                        # "greatest_strength" | "career_goal" | "star_challenge" | 
                        # "notice_period" | "remote_preference" | "custom"
    
    question_text: str | None  # The actual question if custom
    answer: str  # The candidate's preferred answer
    
    # Usage tracking
    times_used: int
    last_used_at: datetime | None
    
    created_at: datetime
    updated_at: datetime
```

---

## 4. ApplicationAgentOrchestrator

```python
class ApplicationAgentOrchestrator:
    """Coordinates the full application submission pipeline."""
    
    def __init__(
        self,
        form_intelligence: FormIntelligenceService,
        knowledge_resolver: CandidateKnowledgeResolver,
        browser: BrowserAutomationAdapter,
        ats_registry: ATSRegistry,
    ): ...
    
    async def start(
        self, application_id: UUID, application_url: str, candidate_id: UUID
    ) -> ApplicationAgentSession:
        """
        Step 1: Detect ATS provider
        Step 2: Open URL with browser
        Step 3: Discover form structure
        Step 4: Classify and map fields
        Step 5: Identify human-required fields
        Step 6: Return session with status
        """
    
    async def resume(self, session_id: UUID) -> ApplicationAgentSession:
        """Resume after human answered pending fields."""
    
    async def fill_and_preview(self, session_id: UUID) -> FillPreview:
        """
        Fill all auto-fill fields in browser (not submitted yet).
        Return preview for human review.
        """
    
    async def submit(self, session_id: UUID, human_confirmed: bool) -> SubmissionResult:
        """
        Only runs after human_confirmed=True.
        Clicks submit, captures confirmation.
        """
```

---

## 5. FormIntelligenceService (evolución del actual)

```python
class FormIntelligenceService:
    """
    Upgrade from current form_intelligence.py:
    - Current: pure function, regex-based, 18 types
    - V2: stateful service, LLM-enhanced, 30+ types, confidence scoring
    """
    
    async def classify_with_confidence(
        self, field: RawFormField
    ) -> FieldClassification:
        """
        1. Try regex rules (fast, deterministic)
        2. If regex confidence < 0.7, use LLM for classification
        Returns: semantic_type, confidence, reasoning
        """
    
    async def map_section(
        self, section: RawFormSection, candidate: CandidateContext
    ) -> MappedSection:
        """Map all fields in a section."""
    
    def score_auto_fill_confidence(
        self, field: MappedField, value: str | None
    ) -> float:
        """0.0–1.0 confidence that auto_fill_value is correct."""
```

### Semantic types V2 (extensión del actual)

```python
SemanticTypeV2 = Literal[
    # Existing 18 types (preserved)
    "full_name", "first_name", "last_name",
    "email", "phone",
    "linkedin_url", "portfolio_url", "github_url",
    "location", "city", "country",
    "years_experience",
    "salary_expectation",
    "work_authorization",
    "cover_letter",
    "cv_file",
    "start_date", "availability",
    "custom_essay",
    "unknown",
    
    # New types
    "gender",           # EEO questions
    "ethnicity",        # EEO questions
    "disability",       # ADA/EEOC
    "veteran_status",   # VEVRAA
    "education_level",  # degree selector
    "education_major",  # field of study
    "gpa",
    "graduation_year",
    "current_company",
    "current_title",
    "current_salary",
    "desired_title",
    "notice_period",
    "relocation",
    "remote_preference",
    "referral_source",
    "cover_letter_file",  # file upload specifically
    "portfolio_file",
    "captcha",          # always human
]
```

---

## 6. CandidateKnowledgeResolver

```python
class CandidateKnowledgeResolver:
    """
    Maps form field semantic types to candidate data.
    Replaces the simple _CANDIDATE_FIELD_MAP dict with a full resolver.
    """
    
    def resolve(
        self, 
        semantic_type: SemanticTypeV2,
        field_label: str,
        candidate: CandidateContext,
        job: JobContext,
    ) -> ResolvedValue:
        """
        Returns:
        - value: str | None (the value to fill)
        - source: ResolveSource (DIRECT | COMPUTED | GENERATED | HUMAN_REQUIRED | CANDIDATE_ANSWER)
        - evidence: EvidenceRef | None
        - confidence: float
        - human_suggestion: str | None (pre-filled suggestion for human-required fields)
        """
    
    async def _resolve_years_experience(
        self, skill: str, experiences: list[Experience]
    ) -> ResolvedValue:
        """Sum experience years where skill appears in description."""
    
    async def _resolve_education_level(
        self, education: list[Education]
    ) -> ResolvedValue:
        """Extract highest degree from education records."""
    
    async def _generate_answer(
        self, field_label: str, candidate: CandidateContext, job: JobContext
    ) -> ResolvedValue:
        """Use LLM to generate answer for custom fields (custom_essay)."""
    
    async def _lookup_candidate_answer(
        self, question_type: str, candidate_id: UUID
    ) -> ResolvedValue:
        """Check CandidateAnswer KB before generating."""
```

### ResolveSource types

```python
class ResolveSource(Enum):
    DIRECT = "direct"              # candidate.email, candidate.name
    COMPUTED = "computed"          # years_experience calculated from history
    FROM_KB = "from_kb"            # from CandidateAnswer pre-stored
    GENERATED = "generated"        # LLM-generated, needs human review
    EEO_DEFAULT = "eeo_default"    # "Prefer not to say" for EEO questions
    HUMAN_REQUIRED = "human_required"  # No auto source, needs human
```

---

## 7. BrowserAutomationAdapter

```python
class BrowserAutomationAdapter(Protocol):
    """
    Thin interface over Playwright.
    All DOM interaction is encapsulated here — domain logic never sees selectors.
    """
    
    async def open_url(self, url: str) -> PageState: ...
    
    async def discover_form(self) -> RawForm:
        """
        Extract all form elements from current page.
        Returns structured RawForm with sections, fields, options.
        """
    
    async def fill_text(self, field_id: str, value: str) -> bool: ...
    async def select_option(self, field_id: str, value: str) -> bool: ...
    async def upload_file(self, field_id: str, file_path: str) -> bool: ...
    async def check_checkbox(self, field_id: str, checked: bool) -> bool: ...
    async def click_next(self) -> PageState: ...  # multi-step forms
    async def click_submit(self) -> PageState: ...
    async def capture_screenshot(self) -> bytes: ...
    async def get_page_text(self) -> str: ...
    async def is_confirmation_page(self) -> bool: ...
    async def extract_confirmation_id(self) -> str | None: ...


class PlaywrightAdapter(BrowserAutomationAdapter):
    """Concrete Playwright implementation."""
    
    def __init__(self, executable_path: str = "/opt/pw-browsers/chromium"):
        self._exec_path = executable_path
    
    async def discover_form(self) -> RawForm:
        """
        Uses page.evaluate() to extract:
        - All form elements (input, select, textarea)
        - Their labels (label[for], aria-label, placeholder)
        - Their types (type attribute)
        - Their required status (required attribute)
        - Their options (option elements)
        - Their section context (fieldset, section heading)
        """
```

---

## 8. ATSRegistry y adapters

```python
class ATSAdapter(Protocol):
    """Specialized knowledge for a specific ATS platform."""
    
    ats_name: str
    url_patterns: list[re.Pattern]  # used by registry for detection
    
    async def handle_login_wall(self, browser: BrowserAutomationAdapter) -> bool:
        """Handle any login/auth wall before the form."""
    
    async def discover_sections(self, browser: BrowserAutomationAdapter) -> list[RawFormSection]:
        """ATS-specific section extraction."""
    
    def normalize_field(self, raw_field: RawFormField) -> RawFormField:
        """ATS-specific label normalization."""
    
    async def submit(self, browser: BrowserAutomationAdapter) -> SubmissionResult:
        """ATS-specific submit flow."""


class ATSRegistry:
    _adapters: list[ATSAdapter] = [
        GreenhouseAdapter(),
        LeverAdapter(),
        AshbyAdapter(),
        WorkdayAdapter(),
        SmartRecruitersAdapter(),
        # ... more
        GenericFormAgent(),  # fallback
    ]
    
    def detect(self, url: str) -> ATSAdapter:
        for adapter in self._adapters:
            for pattern in adapter.url_patterns:
                if pattern.search(url):
                    return adapter
        return GenericFormAgent()


class GreenhouseAdapter(ATSAdapter):
    ats_name = "greenhouse"
    url_patterns = [re.compile(r"boards\.greenhouse\.io")]
    
    # Greenhouse-specific: uses GDPR consent checkbox first,
    # has structured sections: Basic Info, Work Experience, Demographics


class LeverAdapter(ATSAdapter):
    ats_name = "lever"
    url_patterns = [re.compile(r"jobs\.lever\.co")]


class GenericFormAgent(ATSAdapter):
    """
    LLM-powered fallback for unknown ATS.
    Takes screenshot + HTML, asks Claude to identify fields.
    Less reliable than specific adapters, requires higher human review rate.
    """
    ats_name = "generic"
    url_patterns = []  # never matched by pattern, used as default
```

---

## 9. Mock ATS para testing (local)

Para el Golden E2E test, se necesita un servidor web local que simule un ATS completo.

### Implementación propuesta

```
backend/tests/mock_ats/
├── server.py          # FastAPI server con formulario HTML completo
├── templates/
│   ├── form.html      # Formulario multi-sección con todos los tipos de campos
│   ├── step2.html     # Segunda página (multi-step)
│   └── confirm.html   # Página de confirmación con confirmation_id
└── conftest_ats.py    # pytest fixtures para levantar el server en test
```

### Estructura del formulario mock

```html
<!-- Sección 1: Personal Information -->
<input type="text" id="first_name" name="first_name" required label="First Name">
<input type="text" id="last_name" name="last_name" required label="Last Name">
<input type="email" id="email" name="email" required label="Email Address">
<input type="tel" id="phone" name="phone" required label="Phone Number">
<input type="text" id="location" name="location" label="Current Location">
<input type="url" id="linkedin" name="linkedin" label="LinkedIn Profile URL">

<!-- Sección 2: Professional -->
<select id="years_exp" name="years_exp" required label="Years of Experience">
  <option>0-2</option><option>3-5</option><option>6-10</option><option>10+</option>
</select>
<input type="number" id="salary" name="salary" label="Expected Salary (USD)">
<select id="work_auth" name="work_auth" required label="Work Authorization">
  <option>US Citizen</option><option>Permanent Resident</option>
  <option>Require Sponsorship</option>
</select>
<input type="file" id="resume" name="resume" required label="Resume/CV">
<textarea id="cover_letter" name="cover_letter" label="Cover Letter"></textarea>

<!-- Sección 3: Custom Questions -->
<textarea id="why_company" name="why_company" required 
  label="Why do you want to work here?"></textarea>
<input type="checkbox" id="relocation" name="relocation" 
  label="Are you willing to relocate?">

<!-- Confirmación después de submit -->
<!-- confirm.html -->
<h1>Application Submitted</h1>
<p>Your application reference: <strong>APP-TEST-{{uuid}}</strong></p>
```

### Acceptance criteria del E2E con mock ATS

```
GIVEN: candidato con perfil completo
AND: job con URL apuntando al mock ATS local
WHEN: se inicia el Application Agent
THEN:
  - El agente abre la URL en el browser
  - Detecta 10 campos en el formulario
  - Auto-llena: first_name, last_name, email, location, linkedin, years_exp, work_auth
  - Marca como human_required: phone, resume (file), why_company (custom essay)
  - Retorna status: "awaiting_human" con 3 campos pendientes
  
WHEN: el usuario provee phone, sube PDF, escribe "why_company"
AND: el usuario confirma "Enviar"
THEN:
  - El agente llena los campos restantes
  - Sube el CV PDF
  - Click submit
  - Detecta la confirmation page
  - Extrae confirmation_id "APP-TEST-..."
  - Actualiza application.status = "applied"
  - Guarda ApplicationSubmission con el confirmation_id
```

---

## 10. API endpoints nuevos

```
# Agent lifecycle
POST /applications/{id}/agent/start
  body: { application_url: str }
  → ApplicationAgentSession (status: "discovering")

GET  /applications/{id}/agent/status
  → ApplicationAgentSession (current state + pending fields)

POST /applications/{id}/agent/answer/{field_id}
  body: { value: str }
  → ApplicationFormField (updated)

POST /applications/{id}/agent/preview
  → FillPreview (all fields with values, screenshot URL)

POST /applications/{id}/agent/confirm-and-submit
  body: { confirmed: bool }
  → SubmissionResult (confirmation_id, screenshot_url)

# ATS detection
GET  /applications/{id}/ats-detect?url=...
  → { ats_provider: str, confidence: float }
```

---

## 11. State machine del ApplicationAgentSession

```
initializing
    ↓
discovering          (browser opens URL, extracts form)
    ↓
mapping              (FormIntelligenceService classifies fields)
    ↓
awaiting_human  ←──── (si hay campos human_required)
    ↓
ready_to_fill        (todos los campos tienen valor)
    ↓
awaiting_confirm     (muestra preview al usuario)
    ↓  (usuario confirma)
submitting           (browser fills + clicks submit)
    ↓
submitted            (confirmation captured)

[En cualquier paso]
    ↓
failed               (browser error, timeout, CAPTCHA, ATS error)
    ↓
retrying             (hasta MAX_RETRIES)
```

---

## 12. Seguridad y compliance

| Riesgo | Mitigación |
|--------|-----------|
| El agente envía datos a un sitio equivocado | Confirm URL en UI antes de iniciar. Mostrar company name y dominio al usuario. |
| Submit sin confianza suficiente | `human_confirmed: bool` requerido en endpoint de submit. |
| Screenshot con datos sensibles | Screenshots almacenados con acceso restringido por candidate_id. TTL de 30 días. |
| ATS detecta automatización | Playwright en modo stealth. Delays humanizados entre acciones. |
| Sitio malicioso vía application_url | SSRF protection: validate_url_not_private. Allowlist de dominios conocidos de ATS. |
| Inventar datos en campos | Todos los valores traced a CandidateContext. human_required cuando no hay fuente. |

---

## 13. Dependencias de infraestructura nuevas

| Componente | Tecnología | Justificación |
|-----------|-----------|--------------|
| Browser automation | Playwright (ya instalado) | Soporte para JS-rendered forms |
| File storage | S3 o local volume | PDFs generados, screenshots |
| Task queue | Celery + Redis | Browser sessions pueden tardar 2-5 min |
| Browser pool | 1-3 instancias Chromium | Paralelismo limitado en MVP |

---

## 14. Fases de implementación

### P0 — Infrastructure (≈3 días)
- `BrowserAutomationAdapter` con PlaywrightAdapter
- `ATSRegistry` + `GenericFormAgent`
- `ApplicationAgentSession` entity + migration 013
- Mock ATS server para tests

### P1 — Core Flow (≈5 días)
- `ApplicationAgentOrchestrator`: discover → map → await_human → fill → confirm → submit
- `CandidateKnowledgeResolver` con resolvers para los 15 tipos más comunes
- API endpoints del agent lifecycle
- Frontend: Application Agent UI en workspace

### P2 — ATS Adapters (≈5 días)
- `GreenhouseAdapter`
- `LeverAdapter`
- `AshbyAdapter`
- Smoke tests con sandbox accounts de cada ATS (no aplicaciones reales)

### P3 — Knowledge Base (≈3 días)
- `CandidateAnswer` entity + migration 014
- Endpoints CRUD para answers
- Integración en CandidateKnowledgeResolver
- Frontend: gestión de respuestas guardadas

### P4 — Evidence & Quality (≈3 días)
- `FormIntelligenceService` V2 con confidence scoring y LLM fallback
- Evidence graph: campo → evidence record
- Real AI evaluation de quality del form fill
