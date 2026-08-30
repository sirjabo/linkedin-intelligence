"""Tests for mock ATS expanded scenario coverage (scenarios 5–32).

Validates that each new endpoint serves the correct HTML form and accepts
a valid POST submission, returning the expected response.
"""
import httpx

from tests.mock_ats.conftest_ats import mock_ats_url  # noqa: F401

# ── Scenario 5: Radio buttons ──────────────────────────────────────────────────

class TestScenarioRadio:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/radio")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "employment_type" in r.text
        assert 'type="radio"' in r.text

    def test_submit_valid(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/radio/submit",
            data={"first_name": "Jane", "employment_type": "full_time"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "full_time" in r.text or "Confirmed" in r.text or "Submitted" in r.text

    def test_submit_missing_required_accepts_gracefully(self, mock_ats_url):
        """Radio server accepts any submission (no server-side required validation)."""
        r = httpx.post(
            f"{mock_ats_url}/apply/radio/submit",
            data={"first_name": "Jane"},  # missing employment_type
            follow_redirects=True,
        )
        assert r.status_code == 200


# ── Scenario 6: Multi-select ──────────────────────────────────────────────────

class TestScenarioMultiselect:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/multiselect")
        assert r.status_code == 200
        assert "skills" in r.text
        # multi-select is a <select multiple> element
        assert "multiple" in r.text

    def test_submit_with_multiple_skills(self, mock_ats_url):
        import urllib.parse
        body = urllib.parse.urlencode(
            [("full_name", "Jane"), ("skills", "python"), ("skills", "sql")]
        )
        r = httpx.post(
            f"{mock_ats_url}/apply/multiselect/submit",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=True,
        )
        assert r.status_code == 200

    def test_submit_no_skills_succeeds(self, mock_ats_url):
        """Multi-select fields may be optional."""
        r = httpx.post(
            f"{mock_ats_url}/apply/multiselect/submit",
            data={"first_name": "Jane"},
            follow_redirects=True,
        )
        assert r.status_code == 200


# ── Scenario 9: Number inputs ─────────────────────────────────────────────────

class TestScenarioNumber:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/number")
        assert r.status_code == 200
        assert 'type="number"' in r.text

    def test_submit_valid(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/number/submit",
            data={"first_name": "Jane", "years_python": "5", "expected_salary": "90000"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "5" in r.text or "Submitted" in r.text or "Confirmed" in r.text


# ── Scenario 11: Date input ───────────────────────────────────────────────────

class TestScenarioDate:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/date")
        assert r.status_code == 200
        assert 'type="date"' in r.text
        assert "start_date" in r.text

    def test_submit_valid(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/date/submit",
            data={"first_name": "Jane", "start_date": "2026-03-01"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "2026-03-01" in r.text or "Submitted" in r.text or "Confirmed" in r.text

    def test_submit_missing_date_accepted(self, mock_ats_url):
        """Date server accepts any submission (validation is client-side only)."""
        r = httpx.post(
            f"{mock_ats_url}/apply/date/submit",
            data={"first_name": "Jane"},
            follow_redirects=True,
        )
        assert r.status_code == 200


# ── Scenario 13: Two-step form ────────────────────────────────────────────────

class TestScenarioTwoStep:
    def test_step1_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/step1")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "full_name" in r.text
        # Step 1 posts to step2
        assert "step2" in r.text

    def test_step2_post_renders_second_form(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/step2",
            data={"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com"},
            follow_redirects=False,
        )
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        # Step 2 should show more fields
        assert "<form" in r.text

    def test_step2_submit_completes_flow(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/step2/submit",
            data={
                "first_name": "Jane", "last_name": "Doe", "email": "jane@example.com",
                "cover_letter": "I am excited about this role.",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Submitted" in r.text or "Confirmed" in r.text or "APP-" in r.text


# ── Scenario 19: Server-side validation error ─────────────────────────────────

class TestScenarioValidationError:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/validation-error")
        assert r.status_code == 200
        assert "<form" in r.text

    def test_submit_without_required_field_returns_error_html(self, mock_ats_url):
        """Server-side validation: missing required field should yield an error page."""
        r = httpx.post(
            f"{mock_ats_url}/apply/validation-error/submit",
            data={"first_name": "Jane"},  # missing required email
            follow_redirects=True,
        )
        assert r.status_code in (200, 400, 422)
        body = r.text
        assert "error" in body.lower() or "required" in body.lower() or "missing" in body.lower()

    def test_submit_with_all_required_fields_succeeds(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/validation-error/submit",
            data={"full_name": "Jane", "email": "jane@example.com"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        # Should reach confirm page (no error class)
        assert "class=\"error\"" not in r.text


# ── Scenario 22: Salary field ─────────────────────────────────────────────────

class TestScenarioSalary:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/salary")
        assert r.status_code == 200
        assert "salary" in r.text.lower()

    def test_form_has_salary_range_select(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/salary")
        body = r.text
        assert "salary_range" in body or "salary" in body

    def test_submit_valid(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/salary/submit",
            data={"first_name": "Jane", "salary": "90000", "salary_range": "80k-100k"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Submitted" in r.text or "Confirmed" in r.text or "90000" in r.text


# ── Scenario 23: Sponsorship select ──────────────────────────────────────────

class TestScenarioSponsorship:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/sponsorship")
        assert r.status_code == 200
        assert "sponsorship" in r.text.lower() or "sponsor" in r.text.lower()
        assert "<select" in r.text

    def test_form_has_sponsorship_options(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/sponsorship")
        body = r.text
        # Should have yes/no or specific sponsorship options
        assert "yes" in body.lower() or "no" in body.lower() or "sponsor" in body.lower()

    def test_submit_no_sponsorship(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/sponsorship/submit",
            data={"first_name": "Jane", "sponsorship_required": "no"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Submitted" in r.text or "Confirmed" in r.text or "no" in r.text


# ── Scenario 29: Failed submission (500 error) ────────────────────────────────

class TestScenarioFail:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/fail")
        assert r.status_code == 200
        assert "<form" in r.text

    def test_submit_returns_server_error(self, mock_ats_url):
        """This endpoint always fails — simulates ATS server error."""
        r = httpx.post(
            f"{mock_ats_url}/apply/fail/submit",
            data={"first_name": "Jane"},
            follow_redirects=False,
        )
        assert r.status_code >= 400


# ── Scenario 32: Idempotent submit ────────────────────────────────────────────

class TestScenarioIdempotent:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/idempotent")
        assert r.status_code == 200
        assert "idempotency_key" in r.text or "<form" in r.text

    def test_first_submit_succeeds(self, mock_ats_url):
        import uuid
        key = str(uuid.uuid4())
        r = httpx.post(
            f"{mock_ats_url}/apply/idempotent/submit",
            data={"first_name": "Jane", "idempotency_key": key},
            follow_redirects=True,
        )
        assert r.status_code == 200

    def test_duplicate_submit_rejected(self, mock_ats_url):
        """Same idempotency key twice → second request should get 409."""
        import uuid
        key = str(uuid.uuid4())
        httpx.post(
            f"{mock_ats_url}/apply/idempotent/submit",
            data={"first_name": "Jane", "idempotency_key": key},
            follow_redirects=False,
        )
        r2 = httpx.post(
            f"{mock_ats_url}/apply/idempotent/submit",
            data={"first_name": "Jane", "idempotency_key": key},
            follow_redirects=False,
        )
        assert r2.status_code == 409


# ── Scenario 33: File upload ───────────────────────────────────────────────────

class TestScenarioFileUpload:
    def test_get_returns_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/fileupload")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert 'type="file"' in r.text
        assert "resume" in r.text

    def test_submit_with_resume_echoes_filename(self, mock_ats_url):
        resume_bytes = b"%PDF-1.4 fake resume content"
        r = httpx.post(
            f"{mock_ats_url}/apply/fileupload/submit",
            data={"full_name": "Jane Doe", "email": "jane@example.com"},
            files={"resume": ("my_resume.pdf", resume_bytes, "application/pdf")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "submitted"
        assert body["resume_filename"] == "my_resume.pdf"
        assert body["ref"].startswith("APP-")

    def test_submit_with_resume_and_cover_letter(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/fileupload/submit",
            data={"full_name": "Jane Doe", "email": "jane@example.com"},
            files={
                "resume": ("resume.pdf", b"pdf content", "application/pdf"),
                "cover_letter": ("cover.txt", b"Dear Hiring Manager...", "text/plain"),
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["resume_filename"] == "resume.pdf"
        assert body["cover_letter_filename"] == "cover.txt"

    def test_submit_without_file_returns_200(self, mock_ats_url):
        """Server is lenient — missing optional cover_letter is fine."""
        r = httpx.post(
            f"{mock_ats_url}/apply/fileupload/submit",
            data={"full_name": "Jane Doe", "email": "jane@example.com"},
            files={"resume": ("r.pdf", b"data", "application/pdf")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["cover_letter_filename"] is None


# ── Scenario 34: iframe-embedded form ─────────────────────────────────────────

class TestScenarioIframe:
    def test_outer_page_has_iframe(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/iframe")
        assert r.status_code == 200
        assert "<iframe" in r.text
        assert "/apply/iframe/inner" in r.text

    def test_inner_page_has_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/iframe/inner")
        assert r.status_code == 200
        assert "<form" in r.text
        assert 'name="full_name"' in r.text
        assert 'name="email"' in r.text

    def test_submit_returns_ref(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/iframe/submit",
            data={"full_name": "Alice", "email": "alice@example.com"},
            files={"resume": ("cv.pdf", b"content", "application/pdf")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "submitted"
        assert body["ref"].startswith("APP-")


# ── Scenario 35: EEO fields + notice period ───────────────────────────────────

class TestScenarioEEO:
    def test_get_returns_eeo_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/eeo")
        assert r.status_code == 200
        assert "notice_period" in r.text
        assert "highest_education" in r.text
        assert "gender" in r.text
        assert "race" in r.text
        assert "veteran_status" in r.text
        assert "disability" in r.text

    def test_submit_with_eeo_data(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/eeo/submit",
            data={
                "full_name": "Bob", "email": "bob@example.com",
                "notice_period": "4", "highest_education": "bachelor",
                "gender": "male", "race": "white",
                "veteran_status": "not_veteran", "disability": "no",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["notice_period"] == "4"
        assert body["highest_education"] == "bachelor"

    def test_submit_minimal_required_only(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/eeo/submit",
            data={"full_name": "Min", "email": "min@example.com", "notice_period": "0"},
        )
        assert r.status_code == 200


# ── Scenario 36: Custom combobox ──────────────────────────────────────────────

class TestScenarioCombobox:
    def test_get_returns_combobox_page(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/combobox")
        assert r.status_code == 200
        assert 'role="combobox"' in r.text
        assert 'role="listbox"' in r.text
        assert 'role="option"' in r.text

    def test_page_has_hidden_value_input(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/combobox")
        assert 'name="department"' in r.text

    def test_submit_department_value(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/combobox/submit",
            data={"full_name": "Carol", "email": "carol@example.com", "department": "engineering"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["department"] == "engineering"


# ── Scenario 37: Location autocomplete ───────────────────────────────────────

class TestScenarioLocation:
    def test_get_returns_location_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/location")
        assert r.status_code == 200
        assert 'name="location"' in r.text
        assert "autocomplete" in r.text.lower() or "oninput" in r.text

    def test_submit_with_location(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/location/submit",
            data={"full_name": "Dave", "email": "dave@example.com", "location": "San Francisco, CA"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["location"] == "San Francisco, CA"


# ── Scenario 38: CAPTCHA detection ───────────────────────────────────────────

class TestScenarioCaptcha:
    def test_get_shows_captcha_challenge(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/captcha")
        assert r.status_code == 200
        text = r.text.lower()
        assert "captcha" in text or "robot" in text or "verify" in text


# ── Scenario 39: Auth wall ───────────────────────────────────────────────────

class TestScenarioAuthWall:
    def test_get_shows_sign_in_prompt(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/authwall")
        assert r.status_code == 200
        text = r.text.lower()
        assert "sign in" in text or "login" in text or "log in" in text

    def test_page_has_email_and_password(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/authwall")
        assert 'type="email"' in r.text
        assert 'type="password"' in r.text


# ── Scenario 40: Three-step wizard ───────────────────────────────────────────

class TestScenarioWizard:
    def test_step1_shows_personal_info(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/wizard1")
        assert r.status_code == 200
        assert "Step 1" in r.text
        assert 'name="full_name"' in r.text
        assert 'name="email"' in r.text

    def test_step1_to_step2_transition(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/wizard/step2",
            data={"full_name": "Eve", "email": "eve@example.com"},
        )
        assert r.status_code == 200
        assert "Step 2" in r.text
        assert "years_experience" in r.text
        assert "notice_period" in r.text

    def test_step2_to_step3_transition(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/wizard/step3",
            data={
                "full_name": "Eve", "email": "eve@example.com",
                "years_experience": "5", "current_title": "Engineer",
                "notice_period": "2",
            },
        )
        assert r.status_code == 200
        assert "Step 3" in r.text or "Review" in r.text

    def test_final_submit_returns_ref(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/wizard/submit",
            data={
                "full_name": "Eve", "email": "eve@example.com",
                "years_experience": "5", "current_title": "Engineer",
                "notice_period": "2",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "submitted"
        assert body["ref"].startswith("APP-")
        assert body["years_experience"] == "5"
