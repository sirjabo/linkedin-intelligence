"""Tests for Form Intelligence — field classification and candidate mapping."""
import pytest
from httpx import AsyncClient

from app.services.form_intelligence import (
    FieldSpec,
    classify_field,
    map_candidate_to_form,
)

SAMPLE_JD = """\
Senior Data Engineer — TechCorp
We are looking for a Senior Data Engineer with 5+ years of experience.
Location: Buenos Aires, Argentina (hybrid)
Full-time position. Mandatory: Python, SQL.
"""


# ── Field Classification unit tests ───────────────────────────────────────────

def test_classify_full_name():
    assert classify_field("Full Name") == "full_name"
    assert classify_field("full_name") == "full_name"


def test_classify_first_last_name():
    assert classify_field("First Name") == "first_name"
    assert classify_field("Last Name") == "last_name"
    assert classify_field("Surname") == "last_name"


def test_classify_email():
    assert classify_field("Email Address") == "email"
    assert classify_field("e-mail") == "email"


def test_classify_phone():
    assert classify_field("Phone Number") == "phone"
    assert classify_field("Mobile") == "phone"


def test_classify_linkedin():
    assert classify_field("LinkedIn URL") == "linkedin_url"
    assert classify_field("Your LinkedIn Profile") == "linkedin_url"


def test_classify_location():
    assert classify_field("Location") == "location"
    assert classify_field("Current Location") == "location"


def test_classify_salary():
    assert classify_field("Expected Salary") == "salary_expectation"
    assert classify_field("Compensation Expectations") == "salary_expectation"


def test_classify_work_authorization():
    assert classify_field("Work Authorization") == "work_authorization"
    assert classify_field("Are you authorized to work?") == "work_authorization"
    # "Visa Sponsorship" is now correctly classified as 'sponsorship', not 'work_authorization'
    assert classify_field("Visa Sponsorship Required") == "sponsorship"


def test_classify_cover_letter():
    assert classify_field("Cover Letter") == "cover_letter"


def test_classify_cv_file():
    assert classify_field("Upload Resume") == "cv_file"
    assert classify_field("CV / Resume") == "cv_file"


def test_classify_custom_essay():
    assert classify_field("Why do you want to join this company?") == "custom_essay"
    # Sprint F: "Describe your experience with X" is now experience_essay
    assert classify_field("Describe your experience with distributed systems") == "experience_essay"


def test_classify_unknown():
    assert classify_field("Referral Code") == "unknown"
    assert classify_field("Captcha") == "unknown"


def test_classify_phone_country_code():
    assert classify_field("Country Code") == "phone_country_code"
    assert classify_field("Dialing Code") == "phone_country_code"
    assert classify_field("Phone Code") == "phone_country_code"
    assert classify_field("Calling Code") == "phone_country_code"


def test_classify_notice_period():
    assert classify_field("Notice Period") == "notice_period"
    assert classify_field("How many weeks notice do you need to give?") == "notice_period"
    assert classify_field("Notice Required") == "notice_period"


def test_classify_highest_education():
    assert classify_field("Highest Level of Education") == "highest_education"
    assert classify_field("Level of Qualification") == "highest_education"
    assert classify_field("Bachelor") == "highest_education"
    assert classify_field("Do you have a Master degree?") == "highest_education"
    assert classify_field("PhD required?") == "highest_education"


def test_classify_reference_contact():
    assert classify_field("Reference") == "reference_contact"
    assert classify_field("Referral") == "reference_contact"
    assert classify_field("How did you hear about us?") == "reference_contact"
    assert classify_field("Referred by") == "reference_contact"


def test_new_types_are_human_required():
    from app.services.form_intelligence import _ALWAYS_HUMAN
    assert "phone_country_code" in _ALWAYS_HUMAN
    assert "notice_period" in _ALWAYS_HUMAN
    assert "highest_education" in _ALWAYS_HUMAN
    assert "reference_contact" in _ALWAYS_HUMAN


# ── Candidate Mapping unit tests ───────────────────────────────────────────────

def test_map_full_name_autofill():
    fields = [FieldSpec(label="Full Name")]
    result = map_candidate_to_form(
        fields=fields,
        candidate_name="Alice Smith",
        candidate_email=None,
        candidate_location=None,
        candidate_salary_min=None,
        candidate_work_authorization=None,
        candidate_availability=None,
    )
    assert result[0].auto_fill_value == "Alice Smith"
    assert result[0].human_required is False


def test_map_first_last_name_split():
    fields = [FieldSpec(label="First Name"), FieldSpec(label="Last Name")]
    result = map_candidate_to_form(
        fields=fields,
        candidate_name="Alice Smith",
        candidate_email=None, candidate_location=None,
        candidate_salary_min=None, candidate_work_authorization=None,
        candidate_availability=None,
    )
    assert result[0].auto_fill_value == "Alice"
    assert result[1].auto_fill_value == "Smith"


def test_map_email_autofill():
    fields = [FieldSpec(label="Email Address")]
    result = map_candidate_to_form(
        fields=fields, candidate_name=None,
        candidate_email="alice@example.com",
        candidate_location=None, candidate_salary_min=None,
        candidate_work_authorization=None, candidate_availability=None,
    )
    assert result[0].auto_fill_value == "alice@example.com"


def test_map_salary_requires_human():
    """Salary fields must never be auto-filled — they require human confirmation."""
    fields = [FieldSpec(label="Expected Salary")]
    result = map_candidate_to_form(
        fields=fields, candidate_name=None, candidate_email=None,
        candidate_location=None, candidate_salary_min=120_000,
        candidate_work_authorization=None, candidate_availability=None,
    )
    assert result[0].human_required is True
    assert result[0].auto_fill_value is None


def test_map_phone_always_human():
    fields = [FieldSpec(label="Phone Number")]
    result = map_candidate_to_form(
        fields=fields, candidate_name="Alice", candidate_email="a@b.com",
        candidate_location=None, candidate_salary_min=None,
        candidate_work_authorization=None, candidate_availability=None,
    )
    assert result[0].human_required is True
    assert result[0].auto_fill_value is None


def test_map_custom_essay_always_human():
    fields = [FieldSpec(label="Why do you want to work here?")]
    result = map_candidate_to_form(
        fields=fields, candidate_name=None, candidate_email=None,
        candidate_location=None, candidate_salary_min=None,
        candidate_work_authorization=None, candidate_availability=None,
    )
    assert result[0].human_required is True
    assert result[0].semantic_type == "custom_essay"


# ── Integration tests ─────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v2/auth/register", json={"email": email, "password": "Secure1234"})
    assert reg.status_code == 201
    return reg.json()["access_token"]


async def _create_application(client: AsyncClient, token: str, mock_job_agent) -> str:
    job_resp = await client.post(
        "/api/v2/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"raw_jd": SAMPLE_JD},
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    app_resp = await client.post(
        "/api/v2/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": job_id},
    )
    assert app_resp.status_code == 201
    return app_resp.json()["id"]


@pytest.mark.asyncio
async def test_register_form_success(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "form1@example.com")
    # Update candidate with name+email for auto-fill
    await client.put(
        "/api/v2/candidates/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Alice Smith", "salary_min_usd": 90000},
    )
    application_id = await _create_application(client, token, mock_job_agent)

    resp = await client.post(
        f"/api/v2/applications/{application_id}/form",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "form_url": "https://apply.techcorp.com/job/123",
            "fields": [
                {"label": "Full Name", "is_required": True},
                {"label": "Email Address", "is_required": True},
                {"label": "Phone Number", "is_required": True},
                {"label": "Expected Salary", "is_required": False},
                {"label": "Why do you want to join us?", "is_required": True},
            ]
        }
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["fields"]) == 5
    # Full Name should be auto-filled
    full_name_field = next(f for f in data["fields"] if f["semantic_type"] == "full_name")
    assert full_name_field["auto_fill_value"] == "Alice Smith"
    assert full_name_field["human_required"] is False
    # Phone should be human_required
    phone_field = next(f for f in data["fields"] if f["semantic_type"] == "phone")
    assert phone_field["human_required"] is True
    # Salary must be human_required (sensitive field, never auto-filled)
    sal_field = next(f for f in data["fields"] if f["semantic_type"] == "salary_expectation")
    assert sal_field["human_required"] is True
    assert sal_field["auto_fill_value"] is None


@pytest.mark.asyncio
async def test_get_form(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "form2@example.com")
    application_id = await _create_application(client, token, mock_job_agent)

    await client.post(
        f"/api/v2/applications/{application_id}/form",
        headers={"Authorization": f"Bearer {token}"},
        json={"fields": [{"label": "Full Name"}, {"label": "Email Address"}]},
    )

    resp = await client.get(
        f"/api/v2/applications/{application_id}/form",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["fields"]) == 2


@pytest.mark.asyncio
async def test_answer_human_field(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "form3@example.com")
    application_id = await _create_application(client, token, mock_job_agent)

    form_resp = await client.post(
        f"/api/v2/applications/{application_id}/form",
        headers={"Authorization": f"Bearer {token}"},
        json={"fields": [{"label": "Why do you want to join us?"}]},
    )
    form_data = form_resp.json()
    field_id = form_data["fields"][0]["id"]
    assert form_data["human_fields_pending"] == 1

    ans_resp = await client.patch(
        f"/api/v2/applications/{application_id}/form/answer",
        headers={"Authorization": f"Bearer {token}"},
        json={"field_id": field_id, "human_answer": "I admire your mission and tech stack."},
    )
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()
    assert ans_data["human_fields_pending"] == 0
    assert ans_data["status"] == "ready"


@pytest.mark.asyncio
async def test_get_form_not_found(client: AsyncClient, mock_job_agent):
    token = await _register_and_login(client, "form4@example.com")
    application_id = await _create_application(client, token, mock_job_agent)

    resp = await client.get(
        f"/api/v2/applications/{application_id}/form",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
