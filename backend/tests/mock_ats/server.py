"""Mock ATS server for E2E browser automation tests.

Simulates a real company application form with all common field types:
text, email, tel, url, select, file, textarea, checkbox — single page + confirmation.

Run standalone: uvicorn tests.mock_ats.server:app --port 8888
Used in tests via the mock_ats_url fixture in conftest_ats.py.
"""
import uuid
from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

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
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    years_experience: Optional[str] = Form(None),
    salary_expectation: Optional[str] = Form(None),
    work_authorization: Optional[str] = Form(None),
    cover_letter_text: Optional[str] = Form(None),
    why_company: Optional[str] = Form(None),
    relocation_willing: Optional[str] = Form(None),
    remote_ok: Optional[str] = Form(None),
    resume: Optional[UploadFile] = File(None),
):
    ref = f"APP-{uuid.uuid4().hex[:8].upper()}"
    return RedirectResponse(f"/confirm?ref={ref}", status_code=303)


@app.get("/confirm", response_class=HTMLResponse)
async def confirm(ref: str = "APP-UNKNOWN"):
    return HTMLResponse(_CONFIRM_HTML.format(ref=ref))


@app.get("/health")
async def health():
    return {"status": "ok"}
