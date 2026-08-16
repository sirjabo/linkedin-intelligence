"""Model router: choose the right Anthropic model based on task complexity.

Economy tier (haiku) — fast, cheap, good enough for:
  - field classification, simple extraction, keyword scoring
  - form field mapping, retry classification

Capable tier (sonnet) — higher quality for:
  - full JD parsing, CV personalization, cover letter generation
  - match reasoning, profile consolidation, strategy generation
  - anything with complex structured output or long context
"""
from typing import Literal

TaskType = Literal[
    # economy tasks
    "field_classify",
    "keyword_extract",
    "simple_extract",
    "skill_classify",
    "answer_simple",
    "calibration",
    # capable tasks
    "jd_parse",
    "cv_personalize",
    "cover_letter",
    "match_reason",
    "profile_consolidate",
    "strategy",
    "interview_prep",
    "answer_complex",
    "evaluation",
]

# Map each task type to a model ID
_ROUTING_TABLE: dict[TaskType, str] = {
    # Economy — claude-haiku-4-5
    "field_classify":       "claude-haiku-4-5-20251001",
    "keyword_extract":      "claude-haiku-4-5-20251001",
    "simple_extract":       "claude-haiku-4-5-20251001",
    "skill_classify":       "claude-haiku-4-5-20251001",
    "answer_simple":        "claude-haiku-4-5-20251001",
    "calibration":          "claude-haiku-4-5-20251001",
    # Capable — claude-sonnet-5
    "jd_parse":             "claude-sonnet-5",
    "cv_personalize":       "claude-sonnet-5",
    "cover_letter":         "claude-sonnet-5",
    "match_reason":         "claude-sonnet-5",
    "profile_consolidate":  "claude-sonnet-5",
    "strategy":             "claude-sonnet-5",
    "interview_prep":       "claude-sonnet-5",
    "answer_complex":       "claude-sonnet-5",
    "evaluation":           "claude-sonnet-5",
}

# Default fallback
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def route_model(task: TaskType) -> str:
    """Return the model ID for the given task type."""
    return _ROUTING_TABLE.get(task, _DEFAULT_MODEL)


def economy_model() -> str:
    return "claude-haiku-4-5-20251001"


def capable_model() -> str:
    return "claude-sonnet-5"
