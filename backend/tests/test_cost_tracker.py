"""Tests for cost tracker and budget alert logic."""
import pytest
from unittest.mock import patch

from app.services.cost_tracker import (
    CostEstimate,
    check_budget_and_log,
    estimate_session_cost,
    TYPICAL_TOKENS,
)


class TestCostEstimate:
    def test_zero_tokens_zero_cost(self):
        est = CostEstimate()
        assert est.estimated_usd == 0.0
        assert est.input_tokens == 0
        assert est.output_tokens == 0

    def test_add_tokens(self):
        est = CostEstimate()
        est.add(input_tokens=1000, output_tokens=500, note="cv_generation")
        assert est.input_tokens == 1000
        assert est.output_tokens == 500
        assert est.notes == ["cv_generation"]

    def test_cost_calculation(self):
        est = CostEstimate(input_tokens=1_000_000, output_tokens=1_000_000)
        # $0.25 input + $1.25 output = $1.50
        assert abs(est.estimated_usd - 1.50) < 0.001

    def test_add_multiple_operations(self):
        est = CostEstimate()
        est.add(input_tokens=100, output_tokens=50, note="op1")
        est.add(input_tokens=200, output_tokens=100, note="op2")
        assert est.input_tokens == 300
        assert est.output_tokens == 150
        assert est.notes == ["op1", "op2"]

    def test_to_dict(self):
        est = CostEstimate(input_tokens=500, output_tokens=200)
        d = est.to_dict()
        assert "model" in d
        assert "input_tokens" in d
        assert "output_tokens" in d
        assert "estimated_usd" in d
        assert isinstance(d["estimated_usd"], float)


class TestEstimateSessionCost:
    def test_estimate_from_known_ops(self):
        est = estimate_session_cost(["cv_generation", "cover_letter"])
        assert est.input_tokens > 0
        assert est.output_tokens > 0
        assert len(est.notes) == 2

    def test_unknown_op_uses_default(self):
        est = estimate_session_cost(["some_unknown_op"])
        assert est.input_tokens > 0

    def test_empty_ops_zero_cost(self):
        est = estimate_session_cost([])
        assert est.estimated_usd == 0.0

    def test_full_session_ops(self):
        ops = ["cv_generation", "cover_letter", "match_reasoning", "claim_validation"]
        ops.extend(["field_classify"] * 5)
        est = estimate_session_cost(ops)
        assert est.estimated_usd > 0
        # A typical session should be well under the $0.50 hard cap
        assert est.estimated_usd < 0.50


class TestBudgetAlert:
    def test_under_budget_returns_false(self):
        est = CostEstimate(input_tokens=100, output_tokens=50)  # ~$0.000088
        over = check_budget_and_log(est, "app-123", "session-456")
        assert over is False

    def test_over_hard_cap_returns_true(self):
        # $1.25 cost (1M output tokens)
        est = CostEstimate(input_tokens=0, output_tokens=1_000_000)
        over = check_budget_and_log(est, "app-123", "session-456")
        assert over is True

    def test_over_warning_threshold_returns_false(self):
        # Between warning and hard cap
        # warning=$0.10, hard_cap=$0.50
        # 80k output tokens ≈ $0.10
        est = CostEstimate(input_tokens=0, output_tokens=100_000)
        over = check_budget_and_log(est, "app-123", "session-456")
        assert over is False
