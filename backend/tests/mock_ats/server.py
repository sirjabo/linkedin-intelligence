"""Mock ATS server for E2E browser automation tests.

Simulates a real company application form with all common field types:
text, email, tel, url, select, file, textarea, checkbox — single page + confirmation.

Scenarios covered (current):
  1. /apply         — simple form (text, email, tel, url, select, number, file, textarea, checkbox)
  5. /apply/radio   — radio buttons
  6. /apply/multiselect — multi-select
  9. /apply/number  — number input
 11. /apply/date    — date input
 13. /apply/step1   — two-step form (step 1 of 2)
 19. /apply/validation-error — server-side validation error
 22. /apply/salary  — salary field
 23. /apply/sponsorship — sponsorship select
 24. /apply        — already covers work_authorization (work auth)
 29. /apply/fail   — failed submission (500 response)
 32. /apply/idempotent — duplicate submit protection
 33. /apply/fileupload — file upload with filename echo in JSON response
 34. /apply/iframe  — form embedded in an iframe (Lever-style)
 35. /apply/eeo     — EEO/demographic section + notice period fields
 36. /apply/combobox — React-style aria combobox (custom_select)
 37. /apply/location — location autocomplete simulation
 38. /apply/captcha  — CAPTCHA/anti-bot detection page
 39. /apply/authwall — auth wall / login-required page
 40. /apply/wizard1  — three-step wizard page 1 (Workday-style)

Run standalone: uvicorn tests.mock_ats.server:app --port 8888
Used in tests via the mock_ats_url fixture in conftest_ats.py.
"""
import uuid

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# In-memory idempotency store for scenario 32
_submitted_idempotency_keys: set[str] = set()

app = FastAPI(title="Mock ATS")

# ── HTML Templates ─────────────────────────────────────────────────────────────

_FORM_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Apply — Mock Company</title>
</head>
<body>
  <h1>Apply for Senior Data Engineer</h1>
  <p>Mock Company · Buenos Aires (Hybrid)</p>

  <form method="POST" action="/submit" enctype="multipart/form-data">

    <fieldset>
      <legend>Personal Information</legend>

      <label for="first_name">First Name *</label>
      <input type="text" id="first_name" name="first_name" required placeholder="John">

      <label for="last_name">Last Name *</label>
      <input type="text" id="last_name" name="last_name" required placeholder="Doe">

      <label for="email">Email Address *</label>
      <input type="email" id="email" name="email" required placeholder="john@example.com">

      <label for="phone">Phone Number *</label>
      <input type="tel" id="phone" name="phone" required placeholder="+1 (555) 123-4567">

      <label for="location">Current Location</label>
      <input type="text" id="location" name="location" placeholder="City, Country">

      <label for="linkedin_url">LinkedIn Profile URL</label>
      <input type="url" id="linkedin_url" name="linkedin_url" placeholder="https://linkedin.com/in/...">
    </fieldset>

    <fieldset>
      <legend>Professional Details</legend>

      <label for="years_experience">Years of Experience *</label>
      <select id="years_experience" name="years_experience" required>
        <option value="">-- Select --</option>
        <option value="0-2">0–2 years</option>
        <option value="3-5">3–5 years</option>
        <option value="6-10">6–10 years</option>
        <option value="10+">10+ years</option>
      </select>

      <label for="salary_expectation">Expected Salary (USD / year)</label>
      <input type="number" id="salary_expectation" name="salary_expectation" placeholder="120000">

      <label for="work_authorization">Work Authorization *</label>
      <select id="work_authorization" name="work_authorization" required>
        <option value="">-- Select --</option>
        <option value="citizen">US Citizen</option>
        <option value="permanent_resident">Permanent Resident</option>
        <option value="visa_required">Require Sponsorship</option>
      </select>

      <label for="resume">Resume / CV (PDF) *</label>
      <input type="file" id="resume" name="resume" accept=".pdf,.doc,.docx" required>

      <label for="cover_letter_text">Cover Letter</label>
      <textarea id="cover_letter_text" name="cover_letter_text" rows="6"
        placeholder="Tell us about yourself..."></textarea>
    </fieldset>

    <fieldset>
      <legend>Additional Questions</legend>

      <label for="why_company">Why do you want to work here? *</label>
      <textarea id="why_company" name="why_company" rows="5" required
        placeholder="Tell us why you are interested in this role..."></textarea>

      <label>
        <input type="checkbox" id="relocation_willing" name="relocation_willing" value="yes">
        I am willing to relocate if required
      </label>

      <label>
        <input type="checkbox" id="remote_ok" name="remote_ok" value="yes" checked>
        I am open to remote work
      </label>
    </fieldset>

    <button type="submit">Submit Application</button>
  </form>
</body>
</html>
"""

_CONFIRM_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Application Submitted — Mock Company</title>
</head>
<body>
  <h1>Application Submitted</h1>
  <p>Thank you for applying to Mock Company!</p>
  <p>Your application has been received and is under review.</p>
  <p>Application reference: <strong id="confirmation-id">{ref}</strong></p>
  <p>We will contact you at the email address you provided.</p>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/apply")


@app.get("/apply", response_class=HTMLResponse)
async def get_form():
    return HTMLResponse(_FORM_HTML)


@app.post("/submit")
async def submit_form(
    first_name: str | None = Form(None),
    last_name: str | None = Form(None),
    email: str | None = Form(None),
    phone: str | None = Form(None),
    location: str | None = Form(None),
    linkedin_url: str | None = Form(None),
    years_experience: str | None = Form(None),
    salary_expectation: str | None = Form(None),
    work_authorization: str | None = Form(None),
    cover_letter_text: str | None = Form(None),
    why_company: str | None = Form(None),
    relocation_willing: str | None = Form(None),
    remote_ok: str | None = Form(None),
    resume: UploadFile | None = File(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


@app.get("/confirm", response_class=HTMLResponse)
async def confirm(ref: str = "APP-UNKNOWN"):
    return HTMLResponse(_CONFIRM_HTML.format(ref=ref))


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Scenario 5: Radio buttons ─────────────────────────────────────────────────

_RADIO_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Radio Test</title></head><body>
<h1>Apply — Radio Buttons</h1>
<form method="POST" action="/apply/radio/submit">
  <label>Employment Type *</label><br>
  <label><input type="radio" name="employment_type" value="full_time" required> Full-time</label><br>
  <label><input type="radio" name="employment_type" value="part_time"> Part-time</label><br>
  <label><input type="radio" name="employment_type" value="contract"> Contract</label><br>
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <button type="submit">Submit</button>
</form></body></html>"""


@app.get("/apply/radio", response_class=HTMLResponse)
async def get_radio_form():
    return HTMLResponse(_RADIO_HTML)


@app.post("/apply/radio/submit")
async def submit_radio(
    full_name: str | None = Form(None),
    employment_type: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 6: Multi-select ──────────────────────────────────────────────────

_MULTISELECT_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Multi-select Test</title></head><body>
<h1>Apply — Multi-select</h1>
<form method="POST" action="/apply/multiselect/submit">
  <label for="skills">Skills (select all that apply) *</label>
  <select id="skills" name="skills" multiple required size="5">
    <option value="python">Python</option>
    <option value="java">Java</option>
    <option value="sql">SQL</option>
    <option value="spark">Apache Spark</option>
    <option value="kafka">Kafka</option>
  </select>
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <button type="submit">Submit</button>
</form></body></html>"""


@app.get("/apply/multiselect", response_class=HTMLResponse)
async def get_multiselect_form():
    return HTMLResponse(_MULTISELECT_HTML)


@app.post("/apply/multiselect/submit")
async def submit_multiselect(request: Request):
    await request.form()
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 9: Number input ──────────────────────────────────────────────────

_NUMBER_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Number Input</title></head><body>
<h1>Apply — Number Input</h1>
<form method="POST" action="/apply/number/submit">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <label for="years_python">Years of Python experience *</label>
  <input type="number" id="years_python" name="years_python" min="0" max="30" required>
  <label for="salary">Expected Salary (USD)</label>
  <input type="number" id="salary" name="salary" min="0" step="1000" placeholder="90000">
  <button type="submit">Submit</button>
</form></body></html>"""


@app.get("/apply/number", response_class=HTMLResponse)
async def get_number_form():
    return HTMLResponse(_NUMBER_HTML)


@app.post("/apply/number/submit")
async def submit_number(
    full_name: str | None = Form(None),
    years_python: str | None = Form(None),
    salary: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 11: Date input ───────────────────────────────────────────────────

_DATE_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Date Input</title></head><body>
<h1>Apply — Date Input</h1>
<form method="POST" action="/apply/date/submit">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <label for="start_date">Earliest Start Date *</label>
  <input type="date" id="start_date" name="start_date" required>
  <button type="submit">Submit</button>
</form></body></html>"""


@app.get("/apply/date", response_class=HTMLResponse)
async def get_date_form():
    return HTMLResponse(_DATE_HTML)


@app.post("/apply/date/submit")
async def submit_date(
    full_name: str | None = Form(None),
    start_date: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 13: Two-step form ────────────────────────────────────────────────

_STEP1_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Step 1 of 2</title></head><body>
<h1>Step 1 of 2: Personal Information</h1>
<form method="POST" action="/apply/step2">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required>
  <label for="phone">Phone *</label>
  <input type="tel" id="phone" name="phone" required>
  <button type="submit">Next →</button>
</form></body></html>"""

_STEP2_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Step 2 of 2</title></head><body>
<h1>Step 2 of 2: Professional Details</h1>
<form method="POST" action="/apply/step2/submit">
  <input type="hidden" name="full_name" value="{full_name}">
  <input type="hidden" name="email" value="{email}">
  <input type="hidden" name="phone" value="{phone}">
  <label for="resume">Resume / CV (PDF) *</label>
  <input type="file" id="resume" name="resume" accept=".pdf,.doc,.docx" required>
  <label for="why_company">Why do you want to join us? *</label>
  <textarea id="why_company" name="why_company" rows="5" required></textarea>
  <button type="submit">Submit Application</button>
</form></body></html>"""


@app.get("/apply/step1", response_class=HTMLResponse)
async def get_step1():
    return HTMLResponse(_STEP1_HTML)


@app.post("/apply/step2", response_class=HTMLResponse)
async def post_step2(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    phone: str | None = Form(None),
):
    return HTMLResponse(_STEP2_HTML.format(
        full_name=full_name or "", email=email or "", phone=phone or ""
    ))


@app.post("/apply/step2/submit")
async def submit_step2(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    phone: str | None = Form(None),
    why_company: str | None = Form(None),
    resume: UploadFile | None = File(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 19: Validation error ────────────────────────────────────────────

_VALIDATION_ERROR_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Validation Error Form</title></head><body>
<h1>Apply — Validation Error</h1>
<form method="POST" action="/apply/validation-error/submit">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required>
  <button type="submit">Submit</button>
</form></body></html>"""

_VALIDATION_ERROR_RESULT_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Validation Error</title></head><body>
<h1>Error: Missing required fields</h1>
<p class="error">The following fields are required: {fields}</p>
<a href="/apply/validation-error">Go back</a>
</body></html>"""


@app.get("/apply/validation-error", response_class=HTMLResponse)
async def get_validation_error_form():
    return HTMLResponse(_VALIDATION_ERROR_HTML)


@app.post("/apply/validation-error/submit", response_class=HTMLResponse)
async def submit_validation_error(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
):
    missing = []
    if not full_name:
        missing.append("Full Name")
    if not email:
        missing.append("Email")
    if missing:
        return HTMLResponse(
            _VALIDATION_ERROR_RESULT_HTML.format(fields=", ".join(missing)),
            status_code=422,
        )
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 22: Salary field ─────────────────────────────────────────────────

_SALARY_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Salary</title></head><body>
<h1>Apply — Salary Expectation</h1>
<form method="POST" action="/apply/salary/submit">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <label for="salary">Expected Salary (USD / year) *</label>
  <input type="number" id="salary" name="salary" required min="30000" step="1000">
  <label for="salary_range">Salary Range</label>
  <select id="salary_range" name="salary_range">
    <option value="">-- Select --</option>
    <option value="under_80k">Under $80,000</option>
    <option value="80_100k">$80,000 – $100,000</option>
    <option value="100_130k">$100,000 – $130,000</option>
    <option value="over_130k">Over $130,000</option>
  </select>
  <button type="submit">Submit</button>
</form></body></html>"""


@app.get("/apply/salary", response_class=HTMLResponse)
async def get_salary_form():
    return HTMLResponse(_SALARY_HTML)


@app.post("/apply/salary/submit")
async def submit_salary(
    full_name: str | None = Form(None),
    salary: str | None = Form(None),
    salary_range: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 23: Sponsorship select ──────────────────────────────────────────

_SPONSORSHIP_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Sponsorship</title></head><body>
<h1>Apply — Work Authorization / Sponsorship</h1>
<form method="POST" action="/apply/sponsorship/submit">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <label for="sponsorship">Do you require visa sponsorship? *</label>
  <select id="sponsorship" name="sponsorship" required>
    <option value="">-- Select --</option>
    <option value="no">No — I am authorized to work</option>
    <option value="yes">Yes — I require sponsorship</option>
    <option value="future">Not now, but may need in future</option>
  </select>
  <button type="submit">Submit</button>
</form></body></html>"""


@app.get("/apply/sponsorship", response_class=HTMLResponse)
async def get_sponsorship_form():
    return HTMLResponse(_SPONSORSHIP_HTML)


@app.post("/apply/sponsorship/submit")
async def submit_sponsorship(
    full_name: str | None = Form(None),
    sponsorship: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 29: Failed submission ───────────────────────────────────────────

_FAIL_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Fail Scenario</title></head><body>
<h1>Apply — Fail Scenario</h1>
<form method="POST" action="/apply/fail/submit">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required>
  <button type="submit">Submit</button>
</form></body></html>"""


@app.get("/apply/fail", response_class=HTMLResponse)
async def get_fail_form():
    return HTMLResponse(_FAIL_HTML)


@app.post("/apply/fail/submit")
async def submit_fail():
    return JSONResponse({"error": "Internal server error", "code": "SUBMISSION_FAILED"}, status_code=500)


# ── Scenario 32: Duplicate submit protection ──────────────────────────────────

_IDEMPOTENT_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Idempotent Submission</title></head><body>
<h1>Apply — Duplicate Submit Protection</h1>
<form method="POST" action="/apply/idempotent/submit">
  <input type="hidden" name="idempotency_key" value="{key}">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required>
  <button type="submit">Submit</button>
</form></body></html>"""

_DUPLICATE_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Already Submitted</title></head><body>
<h1>Already Submitted</h1>
<p>This application has already been submitted. Please do not submit again.</p>
</body></html>"""


@app.get("/apply/idempotent", response_class=HTMLResponse)
async def get_idempotent_form():
    key = uuid.uuid4().hex
    return HTMLResponse(_IDEMPOTENT_HTML.format(key=key))


@app.post("/apply/idempotent/submit", response_class=HTMLResponse)
async def submit_idempotent(
    idempotency_key: str | None = Form(None),
    full_name: str | None = Form(None),
    email: str | None = Form(None),
):
    if idempotency_key in _submitted_idempotency_keys:
        return HTMLResponse(_DUPLICATE_HTML, status_code=409)
    if idempotency_key:
        _submitted_idempotency_keys.add(idempotency_key)
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


# ── Scenario 33: File upload with filename echo ───────────────────────────────

_FILEUPLOAD_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — File Upload</title></head><body>
<h1>Apply — Resume Upload</h1>
<form method="POST" action="/apply/fileupload/submit" enctype="multipart/form-data">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required><br>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required><br>
  <label for="resume">Resume (PDF, DOCX) *</label>
  <input type="file" id="resume" name="resume" accept=".pdf,.docx" required><br>
  <label for="cover_letter">Cover Letter (optional)</label>
  <input type="file" id="cover_letter" name="cover_letter" accept=".pdf,.txt"><br>
  <button type="submit">Submit Application</button>
</form></body></html>"""


@app.get("/apply/fileupload", response_class=HTMLResponse)
async def get_fileupload_form():
    return HTMLResponse(_FILEUPLOAD_HTML)


@app.post("/apply/fileupload/submit")
async def submit_fileupload(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    resume: UploadFile | None = File(None),
    cover_letter: UploadFile | None = File(None),
):
    resume_name = resume.filename if resume else None
    cover_letter_name = cover_letter.filename if cover_letter else None
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    # Return JSON so tests can assert on uploaded filenames
    return JSONResponse({
        "status": "submitted",
        "ref": ref,
        "resume_filename": resume_name,
        "cover_letter_filename": cover_letter_name,
    })


# ── Scenario 34: iframe-embedded form (Lever-style) ───────────────────────────

_IFRAME_OUTER_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Lever Job Board</title></head><body>
<h1>Senior Software Engineer</h1>
<p>Lever-style embed: the actual form lives in an iframe.</p>
<iframe src="/apply/iframe/inner" width="100%" height="600"
        title="Application form" id="lever-form-iframe"></iframe>
</body></html>"""

_IFRAME_INNER_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Application Form (inner)</title></head><body>
<form method="POST" action="/apply/iframe/submit">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required><br>
  <label for="email">Email Address *</label>
  <input type="email" id="email" name="email" required><br>
  <label for="phone">Phone</label>
  <input type="tel" id="phone" name="phone"><br>
  <label for="resume">Resume *</label>
  <input type="file" id="resume" name="resume" accept=".pdf,.docx" required><br>
  <label for="linkedin">LinkedIn URL</label>
  <input type="url" id="linkedin" name="linkedin"><br>
  <button type="submit">Submit Application</button>
</form></body></html>"""


@app.get("/apply/iframe", response_class=HTMLResponse)
async def get_iframe_outer():
    return HTMLResponse(_IFRAME_OUTER_HTML)


@app.get("/apply/iframe/inner", response_class=HTMLResponse)
async def get_iframe_inner():
    return HTMLResponse(_IFRAME_INNER_HTML)


@app.post("/apply/iframe/submit")
async def submit_iframe(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    phone: str | None = Form(None),
    linkedin: str | None = Form(None),
    resume: UploadFile | None = File(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return JSONResponse({"status": "submitted", "ref": ref, "name": full_name, "email": email})


# ── Scenario 35: EEO section + notice period + dependent fields ───────────────

_EEO_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — EEO & Notice Period</title></head><body>
<h1>Application — Demographic & Availability</h1>
<form method="POST" action="/apply/eeo/submit">
  <h2>Basic Info</h2>
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required><br>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required><br>

  <h2>Availability</h2>
  <label for="notice_period">How many weeks notice do you need to give? *</label>
  <select id="notice_period" name="notice_period" required>
    <option value="">Select...</option>
    <option value="0">0 weeks — available immediately</option>
    <option value="2">2 weeks</option>
    <option value="4">4 weeks</option>
    <option value="8">8 weeks</option>
    <option value="12">12 weeks or more</option>
  </select><br>

  <label for="highest_education">Highest level of education *</label>
  <select id="highest_education" name="highest_education" required>
    <option value="">Select...</option>
    <option value="high_school">High school diploma / GED</option>
    <option value="associate">Associate degree</option>
    <option value="bachelor">Bachelor's degree</option>
    <option value="master">Master's degree</option>
    <option value="phd">PhD / Doctorate</option>
  </select><br>

  <h2>Equal Opportunity (Voluntary)</h2>
  <p>The following questions are voluntary and will not affect your application.</p>

  <label for="gender">Gender</label>
  <select id="gender" name="gender">
    <option value="">Prefer not to say</option>
    <option value="male">Male</option>
    <option value="female">Female</option>
    <option value="nonbinary">Non-binary</option>
  </select><br>

  <label for="race">Race / Ethnicity</label>
  <select id="race" name="race">
    <option value="">Prefer not to say</option>
    <option value="asian">Asian</option>
    <option value="black">Black or African American</option>
    <option value="hispanic">Hispanic or Latino</option>
    <option value="white">White</option>
    <option value="two_or_more">Two or more races</option>
  </select><br>

  <label for="veteran_status">Veteran Status</label>
  <select id="veteran_status" name="veteran_status">
    <option value="">Prefer not to say</option>
    <option value="not_veteran">I am not a protected veteran</option>
    <option value="veteran">I am a protected veteran</option>
  </select><br>

  <label for="disability">Disability Status</label>
  <select id="disability" name="disability">
    <option value="">Prefer not to say</option>
    <option value="yes">Yes, I have a disability</option>
    <option value="no">No, I don't have a disability</option>
  </select><br>

  <button type="submit">Submit Application</button>
</form></body></html>"""


@app.get("/apply/eeo", response_class=HTMLResponse)
async def get_eeo_form():
    return HTMLResponse(_EEO_HTML)


@app.post("/apply/eeo/submit")
async def submit_eeo(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    notice_period: str | None = Form(None),
    highest_education: str | None = Form(None),
    gender: str | None = Form(None),
    race: str | None = Form(None),
    veteran_status: str | None = Form(None),
    disability: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return JSONResponse({
        "status": "submitted",
        "ref": ref,
        "notice_period": notice_period,
        "highest_education": highest_education,
    })


# ── Scenario 36: React-style aria combobox (custom_select) ────────────────────

_COMBOBOX_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Custom Combobox</title>
<style>
  .combobox-wrapper { position:relative; display:inline-block; }
  .combobox-options { position:absolute; background:#fff; border:1px solid #ccc;
                      list-style:none; margin:0; padding:0; z-index:100; min-width:200px; }
  .combobox-options li { padding:6px 12px; cursor:pointer; }
  .combobox-options li:hover { background:#f0f0f0; }
  .hidden { display:none; }
</style></head><body>
<h1>Application — Department Selection</h1>
<form method="POST" action="/apply/combobox/submit" id="main-form">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required><br>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required><br>

  <label id="dept-label">Department *</label><br>
  <div class="combobox-wrapper">
    <div role="combobox" aria-expanded="false" aria-haspopup="listbox"
         aria-labelledby="dept-label" aria-owns="dept-listbox"
         id="dept-combobox" tabindex="0"
         style="border:1px solid #ccc;padding:6px 12px;cursor:pointer;min-width:200px;"
         onclick="toggleDeptList()">
      Select department...
    </div>
    <ul role="listbox" id="dept-listbox" class="combobox-options hidden"
        aria-label="Department options">
      <li role="option" data-value="engineering">Engineering</li>
      <li role="option" data-value="product">Product</li>
      <li role="option" data-value="design">Design</li>
      <li role="option" data-value="data">Data &amp; Analytics</li>
      <li role="option" data-value="infra">Infrastructure</li>
    </ul>
  </div>
  <input type="hidden" id="dept-value" name="department" value="">
  <br><br>

  <button type="submit">Submit</button>
</form>
<script>
function toggleDeptList() {
  var lb = document.getElementById('dept-listbox');
  var cb = document.getElementById('dept-combobox');
  var isOpen = cb.getAttribute('aria-expanded') === 'true';
  if (isOpen) {
    lb.classList.add('hidden');
    cb.setAttribute('aria-expanded', 'false');
  } else {
    lb.classList.remove('hidden');
    cb.setAttribute('aria-expanded', 'true');
  }
}
document.querySelectorAll('#dept-listbox [role="option"]').forEach(function(opt) {
  opt.addEventListener('click', function() {
    document.getElementById('dept-combobox').textContent = this.textContent;
    document.getElementById('dept-value').value = this.getAttribute('data-value');
    document.getElementById('dept-listbox').classList.add('hidden');
    document.getElementById('dept-combobox').setAttribute('aria-expanded', 'false');
  });
});
</script></body></html>"""


@app.get("/apply/combobox", response_class=HTMLResponse)
async def get_combobox_form():
    return HTMLResponse(_COMBOBOX_HTML)


@app.post("/apply/combobox/submit")
async def submit_combobox(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    department: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return JSONResponse({"status": "submitted", "ref": ref, "department": department})


# ── Scenario 37: Location autocomplete simulation ─────────────────────────────

_LOCATION_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Location Autocomplete</title>
<style>
  #location-suggestions { position:absolute; background:#fff; border:1px solid #ccc;
    list-style:none; margin:0; padding:0; z-index:100; min-width:300px; }
  #location-suggestions li { padding:6px 12px; cursor:pointer; }
  #location-suggestions li:hover { background:#f0f0f0; }
  .hidden { display:none; }
</style></head><body>
<h1>Application — Location</h1>
<form method="POST" action="/apply/location/submit" id="main-form">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required><br>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required><br>

  <label for="location">Location / City *</label><br>
  <div style="position:relative;display:inline-block;">
    <input type="text" id="location" name="location" required
           placeholder="Start typing a city..." autocomplete="off"
           style="min-width:300px;" oninput="showSuggestions(this.value)">
    <ul id="location-suggestions" class="hidden"></ul>
  </div><br><br>

  <button type="submit">Submit</button>
</form>
<script>
var cities = [
  "San Francisco, CA", "New York, NY", "Austin, TX", "Seattle, WA",
  "London, UK", "Berlin, Germany", "Toronto, Canada", "Amsterdam, Netherlands"
];
function showSuggestions(val) {
  var ul = document.getElementById('location-suggestions');
  ul.innerHTML = '';
  if (val.length < 2) { ul.classList.add('hidden'); return; }
  var matches = cities.filter(function(c) {
    return c.toLowerCase().indexOf(val.toLowerCase()) !== -1;
  });
  if (matches.length === 0) { ul.classList.add('hidden'); return; }
  matches.forEach(function(city) {
    var li = document.createElement('li');
    li.textContent = city;
    li.onclick = function() {
      document.getElementById('location').value = city;
      ul.classList.add('hidden');
    };
    ul.appendChild(li);
  });
  ul.classList.remove('hidden');
}
</script></body></html>"""


@app.get("/apply/location", response_class=HTMLResponse)
async def get_location_form():
    return HTMLResponse(_LOCATION_HTML)


@app.post("/apply/location/submit")
async def submit_location(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    location: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return JSONResponse({"status": "submitted", "ref": ref, "location": location})


# ── Scenario 38: CAPTCHA / anti-bot detection page ───────────────────────────

_CAPTCHA_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Security Check</title></head><body>
<h1>Please verify you are not a robot</h1>
<p>We need to confirm that you are a human before proceeding to the application form.</p>
<div class="g-recaptcha" data-sitekey="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI">
</div>
<p>If you are having trouble, please complete the CAPTCHA below.</p>
<div id="captcha-challenge">
  <img src="/static/captcha.png" alt="CAPTCHA challenge image">
  <input type="text" name="captcha_response" placeholder="Enter the characters above">
  <button>Verify</button>
</div>
</body></html>"""


@app.get("/apply/captcha", response_class=HTMLResponse)
async def get_captcha_page():
    return HTMLResponse(_CAPTCHA_HTML)


# ── Scenario 39: Auth wall / login required page ─────────────────────────────

_AUTHWALL_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Sign In to Apply</title></head><body>
<h1>Sign in to continue</h1>
<p>You must be signed in to apply for this position.</p>
<p>Please <a href="/login">sign in</a> or <a href="/register">create an account</a> to proceed.</p>
<form method="POST" action="/login">
  <label for="login_email">Email</label>
  <input type="email" id="login_email" name="email" required><br>
  <label for="login_password">Password</label>
  <input type="password" id="login_password" name="password" required><br>
  <button type="submit">Sign In</button>
</form>
<p><a href="/apply/authwall/guest">Continue as guest</a></p>
</body></html>"""


@app.get("/apply/authwall", response_class=HTMLResponse)
async def get_authwall_page():
    return HTMLResponse(_AUTHWALL_HTML)


# ── Scenario 40: Three-step wizard — page 1 (Workday-style) ──────────────────

_WIZARD1_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Step 1 of 3: Personal Info</title></head><body>
<h1>Application Wizard — Step 1 of 3</h1>
<p><strong>Personal Information</strong> | Work History | Review &amp; Submit</p>
<form method="POST" action="/apply/wizard/step2">
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required><br>
  <label for="email">Email *</label>
  <input type="email" id="email" name="email" required><br>
  <label for="phone">Phone</label>
  <input type="tel" id="phone" name="phone"><br>
  <label for="location">Location</label>
  <input type="text" id="location" name="location"><br>
  <label for="linkedin">LinkedIn URL</label>
  <input type="url" id="linkedin" name="linkedin"><br>
  <button type="submit" name="action" value="next">Next →</button>
</form></body></html>"""

_WIZARD2_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Step 2 of 3: Work History</title></head><body>
<h1>Application Wizard — Step 2 of 3</h1>
<p>Personal Information | <strong>Work History</strong> | Review &amp; Submit</p>
<form method="POST" action="/apply/wizard/step3">
  <input type="hidden" name="full_name" value="{full_name}">
  <input type="hidden" name="email" value="{email}">
  <label for="years_experience">Years of professional experience *</label>
  <input type="number" id="years_experience" name="years_experience" min="0" max="50" required><br>
  <label for="current_title">Current job title</label>
  <input type="text" id="current_title" name="current_title"><br>
  <label for="notice_period">Notice period</label>
  <select id="notice_period" name="notice_period">
    <option value="">Select...</option>
    <option value="0">Available immediately</option>
    <option value="2">2 weeks</option>
    <option value="4">4 weeks</option>
    <option value="8">8+ weeks</option>
  </select><br>
  <label for="cover_letter">Cover Letter</label>
  <textarea id="cover_letter" name="cover_letter" rows="5"
            placeholder="Tell us why you're a great fit..."></textarea><br>
  <button type="submit" name="action" value="next">Next →</button>
</form></body></html>"""

_WIZARD3_HTML = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Apply — Step 3 of 3: Review</title></head><body>
<h1>Application Wizard — Step 3 of 3</h1>
<p>Personal Information | Work History | <strong>Review &amp; Submit</strong></p>
<p>Please review your application below before submitting.</p>
<form method="POST" action="/apply/wizard/submit">
  <input type="hidden" name="full_name" value="{full_name}">
  <input type="hidden" name="email" value="{email}">
  <input type="hidden" name="years_experience" value="{years_experience}">
  <input type="hidden" name="current_title" value="{current_title}">
  <input type="hidden" name="notice_period" value="{notice_period}">
  <table>
    <tr><th>Name</th><td>{full_name}</td></tr>
    <tr><th>Email</th><td>{email}</td></tr>
    <tr><th>Years exp.</th><td>{years_experience}</td></tr>
    <tr><th>Title</th><td>{current_title}</td></tr>
  </table>
  <br>
  <button type="submit">Submit Application</button>
</form></body></html>"""


@app.get("/apply/wizard1", response_class=HTMLResponse)
async def get_wizard1():
    return HTMLResponse(_WIZARD1_HTML)


@app.post("/apply/wizard/step2", response_class=HTMLResponse)
async def wizard_step2(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    phone: str | None = Form(None),
    location: str | None = Form(None),
    linkedin: str | None = Form(None),
):
    return HTMLResponse(_WIZARD2_HTML.format(
        full_name=full_name or "",
        email=email or "",
    ))


@app.post("/apply/wizard/step3", response_class=HTMLResponse)
async def wizard_step3(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    years_experience: str | None = Form(None),
    current_title: str | None = Form(None),
    notice_period: str | None = Form(None),
    cover_letter: str | None = Form(None),
):
    return HTMLResponse(_WIZARD3_HTML.format(
        full_name=full_name or "",
        email=email or "",
        years_experience=years_experience or "",
        current_title=current_title or "",
        notice_period=notice_period or "",
    ))


@app.post("/apply/wizard/submit")
async def submit_wizard(
    full_name: str | None = Form(None),
    email: str | None = Form(None),
    years_experience: str | None = Form(None),
    current_title: str | None = Form(None),
    notice_period: str | None = Form(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return JSONResponse({
        "status": "submitted",
        "ref": ref,
        "name": full_name,
        "email": email,
        "years_experience": years_experience,
    })
