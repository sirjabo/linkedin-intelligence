"""Tests for PreSubmitValidator and structured pre-submit validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.services.pre_submit_validator import (
    PreSubmitReport,
    PreSubmitValidationError,
    PreSubmitValidator,
)


@dataclass
class _FakeField:
    """Minimal stand-in for ApplicationFormField."""
    label: str
    semantic_type: str = ""
    is_required: bool = False
    human_required: bool = False
    auto_fill_value: str | None = None
    human_answer: str | None = None


class TestPreSubmitValidator:
    def _v(self) -> PreSubmitValidator:
        return PreSubmitValidator()

    # ── Happy-path ─────────────────────────────────────────────────────────────

    def test_all_required_fields_filled_passes(self):
        fields = [
            _FakeField("Name", is_required=True, auto_fill_value="Jane Doe"),
            _FakeField("Email", is_required=True, auto_fill_value="jane@example.com"),
        ]
        report = self._v().validate(fields)
        assert report.passed
        assert report.errors == []

    def test_empty_fields_list_passes(self):
        report = self._v().validate([])
        assert report.passed

    def test_optional_unfilled_field_passes(self):
        fields = [_FakeField("Cover letter note", is_required=False)]
        report = self._v().validate(fields)
        assert report.passed

    def test_human_answer_satisfies_sensitive_type(self):
        fields = [
            _FakeField(
                "Salary expectation",
                semantic_type="salary",
                human_answer="90000",
            )
        ]
        report = self._v().validate(fields)
        assert report.passed

    # ── Required-field errors ───────────────────────────────────────────────────

    def test_required_field_with_no_value_is_error(self):
        fields = [_FakeField("Phone", is_required=True)]
        report = self._v().validate(fields)
        assert not report.passed
        assert len(report.errors) == 1
        assert "required field has no value" in report.errors[0].issue

    def test_multiple_missing_required_fields(self):
        fields = [
            _FakeField("Name", is_required=True),
            _FakeField("Email", is_required=True),
        ]
        report = self._v().validate(fields)
        assert len(report.errors) == 2

    # ── Sensitive-type protection ───────────────────────────────────────────────

    def test_salary_auto_filled_is_error(self):
        fields = [
            _FakeField("Salary", semantic_type="salary", auto_fill_value="80000")
        ]
        report = self._v().validate(fields)
        assert not report.passed
        assert any("sensitive field" in e.issue for e in report.errors)

    def test_sponsorship_auto_filled_is_error(self):
        fields = [
            _FakeField("Work auth", semantic_type="sponsorship", auto_fill_value="yes")
        ]
        report = self._v().validate(fields)
        assert not report.passed

    def test_demographic_auto_filled_is_error(self):
        fields = [
            _FakeField("Race", semantic_type="race", auto_fill_value="prefer not to say")
        ]
        report = self._v().validate(fields)
        assert not report.passed

    def test_eeo_auto_filled_is_error(self):
        fields = [
            _FakeField("Gender", semantic_type="gender", auto_fill_value="male")
        ]
        report = self._v().validate(fields)
        assert not report.passed

    def test_sensitive_type_without_any_value_skipped(self):
        """No value at all means the field just won't be submitted — not a dup-protection error."""
        fields = [
            _FakeField("Veteran status", semantic_type="veteran_status")
        ]
        report = self._v().validate(fields)
        assert report.passed

    # ── human_required flag ─────────────────────────────────────────────────────

    def test_human_required_flag_without_answer_is_error(self):
        fields = [
            _FakeField("Custom essay", human_required=True, auto_fill_value="some text")
        ]
        report = self._v().validate(fields)
        assert not report.passed
        assert any("human_required" in e.issue for e in report.errors)

    def test_human_required_with_human_answer_passes(self):
        fields = [
            _FakeField("Custom essay", human_required=True, human_answer="My answer")
        ]
        report = self._v().validate(fields)
        assert report.passed

    # ── PreSubmitValidationError ────────────────────────────────────────────────

    def test_raises_pre_submit_validation_error(self):
        fields = [_FakeField("Name", is_required=True)]
        report = self._v().validate(fields)
        with pytest.raises(PreSubmitValidationError) as exc_info:
            if not report.passed:
                raise PreSubmitValidationError(report)
        assert exc_info.value.report is report

    def test_error_summary_contains_field_label(self):
        fields = [_FakeField("Work Email", is_required=True)]
        report = self._v().validate(fields)
        summary = report.summary()
        assert "Work Email" in summary
        assert "FAIL" in summary

    def test_pass_summary_shows_pass(self):
        fields = [_FakeField("Name", is_required=True, auto_fill_value="Alice")]
        report = self._v().validate(fields)
        assert "PASS" in report.summary()


class TestClaimScore:
    """Tests for ClaimScore dataclass added to claim_validator."""

    def test_claim_score_from_result(self):
        from app.services.claim_validator import ClaimScore, ClaimVerification, ValidationResult

        result = ValidationResult(
            verified_claims=["claim A"],
            plausible_claims=["claim B"],
            unverified_claims=[],
            contradicted_claims=[],
            detailed=[
                ClaimVerification(claim="claim A", status="SUPPORTED"),
                ClaimVerification(claim="claim B", status="PLAUSIBLE"),
            ],
        )
        score = ClaimScore.from_result(result)
        assert score.total == 2
        assert score.supported == 1
        assert score.plausible == 1
        assert score.unsupported == 0
        assert score.contradicted == 0
        assert score.support_rate == 1.0
        assert score.contradiction_rate == 0.0

    def test_claim_score_empty_result(self):
        from app.services.claim_validator import ClaimScore, ValidationResult

        score = ClaimScore.from_result(ValidationResult())
        assert score.total == 0
        assert score.support_rate == 1.0
        assert score.contradiction_rate == 0.0

    def test_claim_score_with_contradictions(self):
        from app.services.claim_validator import ClaimScore, ClaimVerification, ValidationResult

        result = ValidationResult(
            contradicted_claims=["bad claim"],
            detailed=[ClaimVerification(claim="bad claim", status="CONTRADICTED")],
        )
        score = ClaimScore.from_result(result)
        assert score.contradiction_rate == 1.0
        assert score.support_rate == 0.0
