"""LLM cost estimation for per-application budget tracking.

Estimates are based on published pricing for claude-haiku-3 (the cheapest model
used in the system). Actuals differ by model; this gives a conservative floor.

Pricing (as of 2025-Q3, USD per 1M tokens):
  Input:  $0.25
  Output: $1.25

The tracker is deliberately simple — no DB writes, no external calls.
It is called at the end of each orchestrator session to log the estimate and
emit a budget alert if thresholds are exceeded.
"""
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.logging import get_logger

logger = get_logger(__name__)

# Haiku pricing per million tokens (conservative floor)
_INPUT_COST_PER_M = 0.25
_OUTPUT_COST_PER_M = 1.25


@dataclass
class CostEstimate:
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "claude-haiku-3"
    notes: list[str] = field(default_factory=list)

    @property
    def estimated_usd(self) -> float:
        return (
            self.input_tokens / 1_000_000 * _INPUT_COST_PER_M
            + self.output_tokens / 1_000_000 * _OUTPUT_COST_PER_M
        )

    def add(self, input_tokens: int = 0, output_tokens: int = 0, note: str = "") -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        if note:
            self.notes.append(note)

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_usd": round(self.estimated_usd, 6),
            "notes": self.notes,
        }


def check_budget_and_log(
    estimate: CostEstimate,
    application_id: str,
    session_id: str,
) -> bool:
    """Log cost and return True if over budget (hard cap exceeded).

    Side effects:
    - Always logs the cost estimate at INFO level.
    - Logs WARNING if over the soft cap.
    - Logs ERROR with ErrorCode.BUDGET_EXCEEDED if over the hard cap.
    """
    cost = estimate.estimated_usd
    logger.info(
        "application_cost",
        application_id=application_id,
        session_id=session_id,
        **estimate.to_dict(),
    )

    if cost > settings.COST_BUDGET_HARD_CAP_USD:
        logger.error(
            "budget_exceeded",
            error_code=ErrorCode.BUDGET_EXCEEDED,
            application_id=application_id,
            session_id=session_id,
            estimated_usd=cost,
            hard_cap_usd=settings.COST_BUDGET_HARD_CAP_USD,
        )
        return True

    if cost > settings.COST_BUDGET_WARNING_USD:
        logger.warning(
            "budget_warning",
            error_code=ErrorCode.BUDGET_WARNING,
            application_id=application_id,
            session_id=session_id,
            estimated_usd=cost,
            warning_cap_usd=settings.COST_BUDGET_WARNING_USD,
        )

    return False


# Rough token estimates for common operations
# Used to pre-fill CostEstimate when exact counts aren't available
TYPICAL_TOKENS = {
    "field_classify": {"input": 200, "output": 10},
    "cv_generation": {"input": 3000, "output": 1500},
    "cover_letter": {"input": 2000, "output": 800},
    "match_reasoning": {"input": 2500, "output": 600},
    "claim_validation": {"input": 1000, "output": 200},
}


def estimate_session_cost(operations: list[str]) -> CostEstimate:
    """Build a CostEstimate from a list of operation names."""
    estimate = CostEstimate()
    for op in operations:
        tokens = TYPICAL_TOKENS.get(op, {"input": 500, "output": 200})
        estimate.add(input_tokens=tokens["input"], output_tokens=tokens["output"], note=op)
    return estimate
