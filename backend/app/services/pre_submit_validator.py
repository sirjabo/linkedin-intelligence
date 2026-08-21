"""PreSubmitValidator: structured pre-submission check before browser form submit.

Validates that all required fields have values, sensitive fields were answered
by a human (not auto-filled), and basic format constraints hold. Raises
PreSubmitValidationError with a structured report when validation fails.

Called by ApplicationAgentOrchestrator.submit() before clicking the submit
button, replacing the previous HTML5-only :invalid check.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Semantic types that MUST have a human answer, never an auto-filled value
_HUMAN_REQUIRED_TYPES: frozenset[str] = frozenset({
    "salary",
    "salary_expectation",
    "sponsorship",
    "work_authorization",
    "demographic",
    "race",
    "ethnicity",
    "gender",
    "disability",
    "veteran_status",
    "eeo",
})


@dataclass
class FieldValidationIssue:
    field_label: str
    semantic_type: str
    issue: str
    severity: str  # "error" | "warning"


@dataclass
class PreSubmitReport:
    issues: list[FieldValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[FieldValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[FieldValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [f"PreSubmit: {'PASS' if self.passed else 'FAIL'} "
                 f"({len(self.errors)} errors, {len(self.warnings)} warnings)"]
        for issue in self.issues:
            icon = "✗" if issue.severity == "error" else "⚠"
            lines.append(f"  {icon} [{issue.field_label}] {issue.issue}")
        return "\n".join(lines)


class PreSubmitValidationError(Exception):
    def __init__(self, report: PreSubmitReport) -> None:
        self.report = report
        super().__init__(report.summary())


class PreSubmitValidator:
    """Validates form fields before browser submit.

    Usage:
        validator = PreSubmitValidator()
        report = validator.validate(form_fields)
        if not report.passed:
            raise PreSubmitValidationError(report)
    """

    def validate(self, form_fields: list[Any]) -> PreSubmitReport:
        """Validate a list of ApplicationFormField ORM objects.

        Args:
            form_fields: list of ApplicationFormField instances with attributes:
                label, semantic_type, is_required, human_required,
                auto_fill_value, human_answer

        Returns:
            PreSubmitReport with any errors and warnings found.
        """
        report = PreSubmitReport()

        for f in form_fields:
            label = getattr(f, "label", None) or getattr(f, "name", "") or "unknown"
            sem_type = getattr(f, "semantic_type", "") or ""
            is_required = bool(getattr(f, "is_required", False))
            human_required = bool(getattr(f, "human_required", False))
            auto_val = getattr(f, "auto_fill_value", None)
            human_val = getattr(f, "human_answer", None)

            effective_value = human_val or auto_val

            # Required fields must have a value
            if is_required and not effective_value:
                report.issues.append(FieldValidationIssue(
                    field_label=label,
                    semantic_type=sem_type,
                    issue="required field has no value",
                    severity="error",
                ))
                continue

            # Sensitive semantic types must be answered by a human
            if sem_type in _HUMAN_REQUIRED_TYPES and not human_val and auto_val:
                report.issues.append(FieldValidationIssue(
                    field_label=label,
                    semantic_type=sem_type,
                    issue=f"sensitive field '{sem_type}' has only an auto-filled value; human answer required",
                    severity="error",
                ))

            # human_required flag set but no human answer
            if human_required and not human_val:
                report.issues.append(FieldValidationIssue(
                    field_label=label,
                    semantic_type=sem_type,
                    issue="field flagged human_required but has no human_answer",
                    severity="error",
                ))

        return report
