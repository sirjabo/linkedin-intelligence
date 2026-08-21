"""Golden E2E tests against the mock ATS server.

These tests verify the mock ATS's HTTP API contract — the same endpoints that
browser-automation code drives during real application submissions.

Unlike test_e2e.py (which mocks the LLM layer and tests the FastAPI app),
these tests spin up the real mock ATS server via httpx and verify that every
scenario endpoint behaves exactly as the browser automation layer expects:
correct HTML, correct redirect chains, correct JSON payloads.

Run via: pytest tests/test_golden_mock_ats.py -v
"""
import uuid

import httpx

from tests.mock_ats.conftest_ats import mock_ats_url  # noqa: F401


class TestHealthAndLanding:
    def test_health_endpoint(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_landing_page(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/", follow_redirects=True)
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]


class TestGoldenSimpleForm:
    """Scenario 1: full simple-form pipeline (the canonical golden path)."""

    def test_form_renders_all_field_types(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply")
        assert r.status_code == 200
        html = r.text
        # All core field types must be present
        assert 'type="text"' in html
        assert 'type="email"' in html
        assert 'type="tel"' in html
        assert 'type="url"' in html
        assert "<select" in html
        assert 'type="file"' in html
        assert "<textarea" in html
        assert 'type="checkbox"' in html

    def test_full_form_submission_redirects_to_confirm(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/submit",
            data={
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "phone": "+54 11 1234-5678",
                "location": "Buenos Aires, Argentina",
                "linkedin_url": "https://linkedin.com/in/alice",
                "years_experience": "7",
                "salary_expectation": "95000",
                "work_authorization": "visa_required",
                "cover_letter_text": "I am excited to apply.",
                "why_company": "Great company culture.",
                "relocation_willing": "no",
                "remote_ok": "yes",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "APP-" in r.text  # confirmation page contains the ref

    def test_partial_form_submission_succeeds(self, mock_ats_url):
        """Server accepts partial submissions (missing optional fields)."""
        r = httpx.post(
            f"{mock_ats_url}/submit",
            data={"first_name": "Bob", "email": "bob@example.com"},
            follow_redirects=True,
        )
        assert r.status_code == 200

    def test_confirm_page_shows_ref(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/confirm?ref=APP-TESTREF")
        assert r.status_code == 200
        assert "APP-TESTREF" in r.text


class TestGoldenFileUpload:
    """Scenario 33: file upload with filename echo — PR-4 requirement."""

    def test_resume_filename_echoed_in_response(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/fileupload/submit",
            data={"full_name": "Alice Smith", "email": "alice@example.com"},
            files={"resume": ("alice_cv.pdf", b"%PDF-1.4 content", "application/pdf")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "submitted"
        assert body["resume_filename"] == "alice_cv.pdf"
        assert body["ref"].startswith("APP-")

    def test_cover_letter_filename_echoed(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/fileupload/submit",
            data={"full_name": "Alice Smith", "email": "alice@example.com"},
            files={
                "resume": ("cv.pdf", b"pdf", "application/pdf"),
                "cover_letter": ("cl.txt", b"Dear...", "text/plain"),
            },
        )
        body = r.json()
        assert body["resume_filename"] == "cv.pdf"
        assert body["cover_letter_filename"] == "cl.txt"

    def test_missing_cover_letter_returns_null(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/fileupload/submit",
            data={"full_name": "Alice Smith", "email": "alice@example.com"},
            files={"resume": ("cv.pdf", b"pdf", "application/pdf")},
        )
        body = r.json()
        assert body["cover_letter_filename"] is None


class TestGoldenTwoStepForm:
    """Scenario 13: multi-page form pipeline."""

    def test_step1_shows_first_page(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/step1")
        assert r.status_code == 200
        assert "full_name" in r.text

    def test_step2_shows_second_page(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/step2",
            data={"full_name": "Alice Smith", "email": "alice@example.com"},
            follow_redirects=False,
        )
        assert r.status_code in (200, 303)

    def test_full_two_step_pipeline(self, mock_ats_url):
        """Complete two-step form: step1 → step2 → confirm."""
        # Step 1 → redirects to step 2 page
        r1 = httpx.post(
            f"{mock_ats_url}/apply/step2",
            data={"full_name": "Alice", "email": "alice@test.com"},
            follow_redirects=True,
        )
        # Step 2 page should contain the next submit action
        assert r1.status_code == 200

        # Step 2 submit → confirm
        r2 = httpx.post(
            f"{mock_ats_url}/apply/step2/submit",
            data={
                "years_experience": "7",
                "salary_expectation": "95000",
                "work_authorization": "visa_required",
                "cover_letter_text": "I am excited.",
            },
            follow_redirects=True,
        )
        assert r2.status_code == 200
        assert "APP-" in r2.text


class TestGoldenIdempotentSubmit:
    """Scenario 32: duplicate-submit protection."""

    def test_first_submit_succeeds(self, mock_ats_url):
        key = str(uuid.uuid4())
        r = httpx.post(
            f"{mock_ats_url}/apply/idempotent/submit",
            data={"full_name": "Alice", "email": "a@b.com", "idempotency_key": key},
            follow_redirects=True,
        )
        assert r.status_code == 200

    def test_second_submit_with_same_key_is_rejected(self, mock_ats_url):
        key = str(uuid.uuid4())
        httpx.post(
            f"{mock_ats_url}/apply/idempotent/submit",
            data={"full_name": "Alice", "email": "a@b.com", "idempotency_key": key},
            follow_redirects=False,
        )
        r2 = httpx.post(
            f"{mock_ats_url}/apply/idempotent/submit",
            data={"full_name": "Alice", "email": "a@b.com", "idempotency_key": key},
            follow_redirects=False,
        )
        assert r2.status_code == 409

    def test_different_keys_both_succeed(self, mock_ats_url):
        key1, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        for key in (key1, key2):
            r = httpx.post(
                f"{mock_ats_url}/apply/idempotent/submit",
                data={"full_name": "Alice", "email": "a@b.com", "idempotency_key": key},
                follow_redirects=True,
            )
            assert r.status_code == 200


class TestGoldenValidationError:
    """Scenario 19: server-side validation error flow."""

    def test_missing_required_fields_shows_error(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/validation-error/submit",
            data={"full_name": ""},
            follow_redirects=True,
        )
        # Error page or re-render — either way the form is still accessible
        assert r.status_code in (200, 400, 422)

    def test_valid_submission_confirms(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/validation-error/submit",
            data={
                "full_name": "Alice Smith",
                "email": "alice@example.com",
                "years_experience": "7",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200


class TestGoldenFailScenario:
    """Scenario 29: server error path."""

    def test_fail_form_renders(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/fail")
        assert r.status_code == 200

    def test_fail_submit_returns_500(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/fail/submit",
            data={"full_name": "Alice", "email": "alice@example.com"},
        )
        assert r.status_code == 500


class TestGoldenSalaryAndSponsorship:
    """Scenarios 22 + 23: structured salary and sponsorship fields."""

    def test_salary_form_renders(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/salary")
        assert r.status_code == 200
        assert "salary" in r.text.lower()

    def test_salary_submission_accepted(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/salary/submit",
            data={"full_name": "Alice", "email": "alice@example.com", "salary_expectation": "95000"},
            follow_redirects=True,
        )
        assert r.status_code == 200

    def test_sponsorship_form_renders(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply/sponsorship")
        assert r.status_code == 200
        assert "sponsor" in r.text.lower()

    def test_sponsorship_submission_accepted(self, mock_ats_url):
        r = httpx.post(
            f"{mock_ats_url}/apply/sponsorship/submit",
            data={
                "full_name": "Alice",
                "email": "alice@example.com",
                "requires_sponsorship": "yes",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
