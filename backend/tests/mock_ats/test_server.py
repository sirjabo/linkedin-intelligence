"""AC-01: Mock ATS server serves the application form and processes submissions.

Acceptance criteria (from ACCEPTANCE_CRITERIA_REAL_AGENT.md):
  AC-01: GET /apply returns 200 with all expected fields; POST /submit
         redirects to /confirm with an APP-XXXXXXXX reference in the body.
"""
import re

import httpx

from tests.mock_ats.conftest_ats import mock_ats_url  # noqa: F401 — re-exported fixture

# ── helpers ───────────────────────────────────────────────────────────────────

EXPECTED_FIELD_NAMES = [
    "first_name",
    "last_name",
    "email",
    "phone",
    "location",
    "linkedin_url",
    "years_experience",
    "salary_expectation",
    "work_authorization",
    "resume",
    "cover_letter_text",
    "why_company",
    "relocation_willing",
    "remote_ok",
]

REQUIRED_FIELD_NAMES = {
    "first_name",
    "last_name",
    "email",
    "phone",
    "years_experience",
    "work_authorization",
    "resume",
    "why_company",
}


# ── AC-01-a: form is served with all expected fields ──────────────────────────

class TestMockATSForm:
    def test_health(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_root_redirects_to_apply(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/", follow_redirects=False)
        assert r.status_code in (301, 302, 307, 308)
        assert "/apply" in r.headers["location"]

    def test_apply_returns_html_form(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        body = r.text
        assert "<form" in body
        assert 'method="post"' in body.lower() or "method='post'" in body.lower()

    def test_apply_contains_all_fields(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply")
        body = r.text
        for name in EXPECTED_FIELD_NAMES:
            assert f'name="{name}"' in body, f"Field '{name}' not found in form HTML"

    def test_apply_required_fields_have_required_attr(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply")
        body = r.text
        for name in REQUIRED_FIELD_NAMES:
            # The tag that contains name="..." should also have required
            # Simple heuristic: find the line with that name and check required
            matches = [
                line for line in body.splitlines()
                if f'name="{name}"' in line
            ]
            assert matches, f"Field '{name}' not found in form"
            assert any("required" in line for line in matches), (
                f"Field '{name}' should be required"
            )

    def test_apply_has_file_upload_for_resume(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply")
        body = r.text
        assert 'type="file"' in body
        assert 'name="resume"' in body

    def test_apply_has_select_for_years_experience(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply")
        body = r.text
        assert '<select' in body
        assert 'name="years_experience"' in body
        assert '0-2' in body or '0–2' in body

    def test_apply_has_checkboxes(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply")
        body = r.text
        assert 'name="relocation_willing"' in body
        assert 'name="remote_ok"' in body
        assert 'type="checkbox"' in body

    def test_apply_has_textarea(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/apply")
        body = r.text
        assert '<textarea' in body
        assert 'name="why_company"' in body


# ── AC-01-b: submission generates APP- reference and redirects ────────────────

class TestMockATSSubmission:
    def _submit(self, base_url: str) -> httpx.Response:
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "phone": "+1-555-000-0001",
            "location": "Buenos Aires",
            "linkedin_url": "https://linkedin.com/in/janedoe",
            "years_experience": "3-5",
            "salary_expectation": "95000",
            "work_authorization": "visa_required",
            "cover_letter_text": "I am excited about this role.",
            "why_company": "I love data engineering challenges.",
        }
        return httpx.post(
            f"{base_url}/submit",
            data=data,
            follow_redirects=True,
        )

    def test_submit_redirects_to_confirm(self, mock_ats_url):
        r = self._submit(mock_ats_url)
        assert r.status_code == 200
        assert "/confirm" in str(r.url)

    def test_confirm_page_contains_app_reference(self, mock_ats_url):
        r = self._submit(mock_ats_url)
        body = r.text
        assert "Application Submitted" in body
        matches = re.findall(r"APP-[A-F0-9]{8}", body)
        assert matches, f"No APP-XXXXXXXX reference found in confirm page body:\n{body[:500]}"

    def test_confirm_reference_is_in_tagged_element(self, mock_ats_url):
        r = self._submit(mock_ats_url)
        body = r.text
        assert 'id="confirmation-id"' in body

    def test_each_submission_gets_unique_reference(self, mock_ats_url):
        refs = set()
        for _ in range(5):
            r = self._submit(mock_ats_url)
            matches = re.findall(r"APP-[A-F0-9]{8}", r.text)
            assert matches
            refs.add(matches[0])
        assert len(refs) == 5, "Duplicate confirmation references generated"

    def test_confirm_endpoint_directly(self, mock_ats_url):
        r = httpx.get(f"{mock_ats_url}/confirm?ref=APP-TESTREF1")
        assert r.status_code == 200
        assert "APP-TESTREF1" in r.text
