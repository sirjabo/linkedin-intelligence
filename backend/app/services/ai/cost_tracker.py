"""Token and cost accounting for all LLM calls."""
from dataclasses import dataclass, field
from datetime import datetime

# Cost per 1M tokens in USD — update when pricing changes
COST_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "claude-sonnet-5": {"input": 3.0, "output": 15.0},
    "claude-opus-5": {"input": 15.0, "output": 75.0},
}


@dataclass
class CallRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


# In-memory accumulator for the current process (resets on restart).
# Replace with a DB-backed tracker in Phase 7.
_records: list[CallRecord] = []


def track_call(model: str, input_tokens: int, output_tokens: int) -> None:
    rates = COST_PER_MILLION_TOKENS.get(model, {"input": 3.0, "output": 15.0})
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
    _records.append(CallRecord(model=model, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost))


def get_totals() -> dict[str, float]:
    return {
        "total_input_tokens": sum(r.input_tokens for r in _records),
        "total_output_tokens": sum(r.output_tokens for r in _records),
        "total_cost_usd": sum(r.cost_usd for r in _records),
        "total_calls": len(_records),
    }
