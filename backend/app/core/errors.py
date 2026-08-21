"""Structured error taxonomy for LinkedIn Intelligence.

Use ErrorCode values in API responses and log events so errors are
machine-filterable in observability dashboards.
"""
from enum import StrEnum


class ErrorCode(StrEnum):
    # Auth
    UNAUTHORIZED = "auth.unauthorized"
    FORBIDDEN = "auth.forbidden"
    TOKEN_EXPIRED = "auth.token_expired"

    # Candidate
    CANDIDATE_NOT_FOUND = "candidate.not_found"
    CANDIDATE_PROFILE_MISSING = "candidate.profile_missing"

    # Job
    JOB_NOT_FOUND = "job.not_found"
    JOB_PARSE_FAILED = "job.parse_failed"

    # Application
    APPLICATION_NOT_FOUND = "application.not_found"
    APPLICATION_ALREADY_SUBMITTED = "application.already_submitted"
    APPLICATION_WRONG_STATUS = "application.wrong_status"

    # Form
    FORM_NOT_FOUND = "form.not_found"
    FORM_FIELDS_PENDING = "form.fields_pending"
    FORM_VALIDATION_FAILED = "form.validation_failed"
    FORM_SENSITIVE_FIELD_MISSING = "form.sensitive_field_missing"

    # Agent / browser automation
    AGENT_SESSION_NOT_FOUND = "agent.session_not_found"
    AGENT_WRONG_STATUS = "agent.wrong_status"
    AGENT_DUPLICATE_SUBMIT = "agent.duplicate_submit"
    AGENT_BROWSER_ERROR = "agent.browser_error"
    AGENT_STALE_ELEMENT = "agent.stale_element"
    AGENT_SUBMIT_FAILED = "agent.submit_failed"
    AGENT_CONFIRMATION_MISSING = "agent.confirmation_missing"
    AGENT_CRASH = "agent.crash"

    # LLM / AI
    LLM_TIMEOUT = "llm.timeout"
    LLM_RATE_LIMITED = "llm.rate_limited"
    LLM_PROMPT_INJECTION = "llm.prompt_injection_blocked"
    LLM_RESPONSE_INVALID = "llm.response_invalid"

    # Budget
    BUDGET_EXCEEDED = "budget.exceeded"
    BUDGET_WARNING = "budget.warning"

    # Privacy / GDPR
    DATA_DELETION_FAILED = "privacy.deletion_failed"

    # Generic
    INTERNAL_ERROR = "internal.error"
    VALIDATION_ERROR = "validation.error"
    NOT_FOUND = "generic.not_found"
    CONFLICT = "generic.conflict"
    RATE_LIMITED = "generic.rate_limited"
