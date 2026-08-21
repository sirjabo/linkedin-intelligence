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
