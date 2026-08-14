"""Learning Loop: calibrate match scoring from real application outcomes.

Aggregates outcome data across a candidate's applications to detect
whether the scoring engine is over- or under-optimistic, and which
tiers need recalibration. No LLM calls — pure statistics.
"""
from dataclasses import dataclass, field

# Outcomes counted as positive signals (candidate advanced)
_POSITIVE = {"got_interview", "offer"}
# Outcomes counted as negative signals
_NEGATIVE = {"rejected", "ghosted"}

_TIER_ORDER = ["excellent", "strong", "moderate", "weak", "poor"]

# Expected interview rates per tier (based on matching intent, not calibrated data)
_EXPECTED_INTERVIEW_RATE = {
    "excellent": 0.60,
    "strong": 0.40,
    "moderate": 0.20,
    "weak": 0.08,
    "poor": 0.02,
}

MIN_OUTCOMES_FOR_CALIBRATION = 5


@dataclass
class TierInsight:
    tier: str
    total_applications: int
    outcomes_recorded: int
    interview_rate: float | None  # None if no outcomes yet
    rejection_rate: float | None
    expected_interview_rate: float | None


@dataclass
class CalibrationReport:
    total_outcomes: int
    by_tier: list[TierInsight]
    overall_interview_rate: float | None
    # over_optimistic | well_calibrated | under_optimistic | insufficient_data
    bias_direction: str
    calibration_score: float | None  # actual / expected overall interview rate
    insights: list[str] = field(default_factory=list)


def compute_calibration(
    outcomes: list[dict],
) -> CalibrationReport:
    """Compute a calibration report from outcome records.

    Args:
        outcomes: list of dicts with keys: tier (str), outcome (str | None).
                  outcome may be None (pending), "got_interview", "offer",
                  "rejected", "ghosted", "withdrew".
    """
    if not outcomes:
        return CalibrationReport(
            total_outcomes=0,
            by_tier=[],
            overall_interview_rate=None,
            bias_direction="insufficient_data",
            calibration_score=None,
            insights=["No outcome data recorded yet. Use the feedback endpoint to log application results."],
        )

    # Group by tier
    by_tier: dict[str, list[str | None]] = {t: [] for t in _TIER_ORDER}
    for row in outcomes:
        tier = row.get("tier") or "poor"
        if tier not in by_tier:
            by_tier[tier] = []
        by_tier[tier].append(row.get("outcome"))

    tier_insights: list[TierInsight] = []
    total_with_outcome = 0
    total_positive = 0

    for tier in _TIER_ORDER:
        tier_outcomes = by_tier[tier]
        if not tier_outcomes:
            continue

        recorded = [o for o in tier_outcomes if o is not None]
        positives = [o for o in recorded if o in _POSITIVE]
        negatives = [o for o in recorded if o in _NEGATIVE]

        interview_rate = len(positives) / len(recorded) if recorded else None
        rejection_rate = len(negatives) / len(recorded) if recorded else None

        total_with_outcome += len(recorded)
        total_positive += len(positives)

        tier_insights.append(TierInsight(
            tier=tier,
            total_applications=len(tier_outcomes),
            outcomes_recorded=len(recorded),
            interview_rate=interview_rate,
            rejection_rate=rejection_rate,
            expected_interview_rate=_EXPECTED_INTERVIEW_RATE.get(tier),
        ))

    overall_interview_rate = (
        total_positive / total_with_outcome if total_with_outcome >= MIN_OUTCOMES_FOR_CALIBRATION
        else None
    )

    if total_with_outcome < MIN_OUTCOMES_FOR_CALIBRATION:
        return CalibrationReport(
            total_outcomes=total_with_outcome,
            by_tier=tier_insights,
            overall_interview_rate=overall_interview_rate,
            bias_direction="insufficient_data",
            calibration_score=None,
            insights=[
                f"Only {total_with_outcome} outcome(s) recorded. "
                f"Need {MIN_OUTCOMES_FOR_CALIBRATION} for calibration analysis."
            ],
        )

    # Compute weighted expected rate based on tier distribution
    total_apps_with_tier = sum(ti.total_applications for ti in tier_insights)
    weighted_expected = sum(
        ti.total_applications / total_apps_with_tier * (ti.expected_interview_rate or 0)
        for ti in tier_insights
    ) if total_apps_with_tier else 0

    calibration_score = (
        overall_interview_rate / weighted_expected
        if weighted_expected > 0 else None
    )

    # calibration_score = actual / expected
    # <1 → actual < expected → scoring was too optimistic (over_optimistic)
    # >1 → actual > expected → scoring was too conservative (under_optimistic)
    if calibration_score is None:
        bias_direction = "insufficient_data"
    elif 0.75 <= calibration_score <= 1.35:
        bias_direction = "well_calibrated"
    elif calibration_score < 0.75:
        bias_direction = "over_optimistic"
    else:
        bias_direction = "under_optimistic"

    insights = _generate_insights(tier_insights, bias_direction, overall_interview_rate, calibration_score)

    return CalibrationReport(
        total_outcomes=total_with_outcome,
        by_tier=tier_insights,
        overall_interview_rate=overall_interview_rate,
        bias_direction=bias_direction,
        calibration_score=calibration_score,
        insights=insights,
    )


def _generate_insights(
    tier_insights: list[TierInsight],
    bias_direction: str,
    overall_rate: float | None,
    cal_score: float | None,
) -> list[str]:
    insights: list[str] = []

    if bias_direction == "well_calibrated":
        insights.append(
            f"Match scoring is well-calibrated. "
            f"Your {overall_rate:.0%} interview rate is close to the expected range."
        )
    elif bias_direction == "over_optimistic":
        insights.append(
            "Scoring tends to be over-optimistic: high-tier matches are converting "
            "to interviews less often than expected. Consider raising the minimum "
            "score threshold before applying."
        )
    elif bias_direction == "under_optimistic":
        insights.append(
            "Scoring is under-optimistic: you are getting interviews from matches "
            "the engine rated conservatively. Consider applying to more 'stretch' roles."
        )

    # Per-tier observations
    for ti in tier_insights:
        if ti.interview_rate is None or ti.outcomes_recorded < 3:
            continue
        expected = ti.expected_interview_rate or 0
        if ti.interview_rate > expected * 1.5:
            insights.append(
                f"'{ti.tier.title()}' tier is outperforming expectations "
                f"({ti.interview_rate:.0%} vs {expected:.0%} expected)."
            )
        elif ti.interview_rate < expected * 0.4 and ti.outcomes_recorded >= 5:
            insights.append(
                f"'{ti.tier.title()}' tier is underperforming "
                f"({ti.interview_rate:.0%} vs {expected:.0%} expected). "
                "Consider targeting roles that are a closer skill match."
            )

    return insights
