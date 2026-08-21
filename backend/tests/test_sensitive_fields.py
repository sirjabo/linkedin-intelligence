"""B6: Verify sensitive form fields are classified as HUMAN_REQUIRED.

All legally/ethically sensitive semantic types must:
1. Be recognized from common label text
2. Have human_required=True (never auto-filled)

PreSubmitValidator enforces this at submit time; this test validates the
classification layer so sensitive fields never slip through as auto-filled.
"""
import pytest

from app.services.form_intelligence import (
    _ALWAYS_HUMAN,
    FieldSpec,
    classify_field,
    map_candidate_to_form,
)


class TestSensitiveFieldsAlwaysHumanRequired:
    """Each sensitive semantic type must appear in _ALWAYS_HUMAN."""

    def test_salary_expectation_in_always_human(self):
        assert "salary_expectation" in _ALWAYS_HUMAN

    def test_work_authorization_in_always_human(self):
        assert "work_authorization" in _ALWAYS_HUMAN

    def test_sponsorship_in_always_human(self):
        assert "sponsorship" in _ALWAYS_HUMAN

    def test_relocation_in_always_human(self):
        assert "relocation" in _ALWAYS_HUMAN

    def test_demographic_in_always_human(self):
        assert "demographic" in _ALWAYS_HUMAN

    def test_race_in_always_human(self):
        assert "race" in _ALWAYS_HUMAN

    def test_ethnicity_in_always_human(self):
        assert "ethnicity" in _ALWAYS_HUMAN

    def test_gender_in_always_human(self):
        assert "gender" in _ALWAYS_HUMAN

    def test_disability_in_always_human(self):
        assert "disability" in _ALWAYS_HUMAN

    def test_veteran_status_in_always_human(self):
        assert "veteran_status" in _ALWAYS_HUMAN


class TestSensitiveFieldLabelRecognition:
    """Common label phrasings must classify to the correct sensitive semantic type."""

    @pytest.mark.parametrize("label,expected_type", [
        # Salary
        ("Expected Salary (USD)", "salary_expectation"),
        ("Salary Expectation", "salary_expectation"),
        ("Compensation Expected", "salary_expectation"),
        # Work auth
        ("Work Authorization", "work_authorization"),
        ("Are you authorized to work in the US?", "work_authorization"),
        # Sponsorship
        ("Do you require visa sponsorship?", "sponsorship"),
        ("Require Sponsorship", "sponsorship"),
        # Relocation
        ("Are you willing to relocate?", "relocation"),
        ("Relocation preference", "relocation"),
        # EEO / Demographic
        ("Race / Ethnicity", "race"),
        ("Ethnic Background", "ethnicity"),
        ("Gender Identity", "gender"),
        ("Disability Status", "disability"),
        ("Veteran Status", "veteran_status"),
        ("Military Status", "veteran_status"),
        ("EEO / Demographic Information", "demographic"),
        ("Equal Opportunity Questionnaire", "demographic"),
    ])
    def test_label_classifies_to_sensitive_type(self, label, expected_type):
        result = classify_field(label)
        assert result == expected_type, (
            f"Label '{label}' classified as '{result}', expected '{expected_type}'"
        )

    @pytest.mark.parametrize("label", [
        "Expected Salary (USD)",
        "Work Authorization",
        "Do you require visa sponsorship?",
        "Are you willing to relocate?",
        "Race / Ethnicity",
        "Ethnic Background",
        "Gender Identity",
        "Disability Status",
        "Veteran Status",
        "EEO / Demographic Information",
    ])
    def test_sensitive_label_yields_human_required_in_mapping(self, label):
        """map_candidate_to_form must mark sensitive fields as human_required with no auto_fill."""
        fields = [FieldSpec(label=label, field_type="select", is_required=False)]
        mapped = map_candidate_to_form(
            fields=fields,
            candidate_name=None,
            candidate_email=None,
            candidate_location=None,
            candidate_salary_min=None,
            candidate_work_authorization=None,
            candidate_availability=None,
        )
        assert len(mapped) == 1
        assert mapped[0].human_required, (
            f"Label '{label}' (type={mapped[0].semantic_type}) was not marked human_required"
        )
        assert mapped[0].auto_fill_value is None, (
            f"Label '{label}' (type={mapped[0].semantic_type}) was auto-filled "
            f"(value={mapped[0].auto_fill_value!r}), "
            f"expected None — sensitive fields must never be auto-filled"
        )
