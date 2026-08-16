"""Learning Loop: calibrate match scoring from real application outcomes.

Aggregates outcome data across a candidate's applications to detect
whether the scoring engine is over- or under-optimistic, and which
tiers need recalibration. Includes active threshold updates and A/B
experiment framework. No LLM calls — pure statistics.
"""
import hashlib
import math
from dataclasses import dataclass, field
from typing import Any


def _norm_sf(z: float) -> float:
    """Survival function (upper tail) of the standard normal — math-only, no scipy."""
    return 0.5 * math.erfc(z / math.sqrt(2))

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
    p_value: float | None = None   # two-tailed z-test p-value; None = insufficient data
    significant: bool = False      # True when p_value is not None and p_value < 0.05


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
        overall_interview_rate / weighted_expected  # type: ignore[operator]
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

    # Hypothesis test: z-test for proportion (observed rate vs weighted expected rate)
    p_value: float | None = None
    significant = False
    if (
        overall_interview_rate is not None
        and weighted_expected > 0
        and total_with_outcome >= MIN_OUTCOMES_FOR_CALIBRATION
    ):
        std_err = math.sqrt(weighted_expected * (1.0 - weighted_expected) / total_with_outcome)
        if std_err > 0:
            z_stat = (overall_interview_rate - weighted_expected) / std_err
            p_value = round(min(1.0, 2.0 * _norm_sf(abs(z_stat))), 4)
            significant = p_value < 0.05

    return CalibrationReport(
        total_outcomes=total_with_outcome,
        by_tier=tier_insights,
        overall_interview_rate=overall_interview_rate,
        bias_direction=bias_direction,
        calibration_score=calibration_score,
        insights=insights,
        p_value=p_value,
        significant=significant,
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


# ── Sprint L: Active Threshold Updates ───────────────────────────────────────

# Default score thresholds per tier (lower bound of the tier)
_DEFAULT_THRESHOLDS: dict[str, float] = {
    "excellent": 0.85,
    "strong":    0.70,
    "moderate":  0.50,
    "weak":      0.30,
    "poor":      0.00,
}

# Minimum number of outcomes before updating a tier's threshold
_MIN_OUTCOMES_FOR_THRESHOLD_UPDATE = 10

# How much to shift the threshold per calibration unit (damped to avoid oscillation)
_THRESHOLD_LEARNING_RATE = 0.05


@dataclass
class ThresholdUpdate:
    tier: str
    old_threshold: float
    new_threshold: float
    direction: str        # "raised" | "lowered" | "unchanged"
    reason: str


def _update_thresholds(
    calibration: CalibrationReport,
    current_thresholds: dict[str, float] | None = None,
) -> tuple[dict[str, float], list[ThresholdUpdate]]:
    """Compute updated match score thresholds from a calibration report.

    Uses the calibration_score per tier to nudge thresholds toward better alignment
    with observed interview rates. Returns (new_thresholds, list[ThresholdUpdate]).

    - over_optimistic tier  → raise its threshold (require higher score to enter that tier)
    - under_optimistic tier → lower its threshold (allow lower scores into the tier)
    - well_calibrated       → unchanged
    - insufficient data     → unchanged
    """
    thresholds = dict(current_thresholds or _DEFAULT_THRESHOLDS)
    updates: list[ThresholdUpdate] = []

    for ti in calibration.by_tier:
        if ti.interview_rate is None or ti.outcomes_recorded < _MIN_OUTCOMES_FOR_THRESHOLD_UPDATE:
            continue
        expected = ti.expected_interview_rate or 0
        if expected <= 0:
            continue

        tier_cal_score = ti.interview_rate / expected
        old = thresholds.get(ti.tier, _DEFAULT_THRESHOLDS.get(ti.tier, 0.0))

        if tier_cal_score < 0.75:
            # Over-optimistic: raise the threshold for this tier
            delta = _THRESHOLD_LEARNING_RATE * (1 - tier_cal_score)
            new = min(old + delta, 0.99)
            direction = "raised"
            reason = (
                f"interview rate {ti.interview_rate:.0%} vs {expected:.0%} expected "
                f"(cal_score={tier_cal_score:.2f})"
            )
        elif tier_cal_score > 1.35:
            # Under-optimistic: lower the threshold
            delta = _THRESHOLD_LEARNING_RATE * (tier_cal_score - 1)
            new = max(old - delta, 0.01)
            direction = "lowered"
            reason = (
                f"outperforming: {ti.interview_rate:.0%} vs {expected:.0%} expected "
                f"(cal_score={tier_cal_score:.2f})"
            )
        else:
            new = old
            direction = "unchanged"
            reason = f"well calibrated (cal_score={tier_cal_score:.2f})"

        thresholds[ti.tier] = new
        updates.append(ThresholdUpdate(
            tier=ti.tier,
            old_threshold=old,
            new_threshold=new,
            direction=direction,
            reason=reason,
        ))

    return thresholds, updates


# ── Sprint L: A/B Experiment Framework ───────────────────────────────────────

@dataclass
class ABVariant:
    name: str
    description: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ABExperiment:
    experiment_id: str
    description: str
    variants: list[ABVariant]
    traffic_split: list[float]   # must sum to 1.0; same length as variants

    def __post_init__(self) -> None:
        if len(self.variants) != len(self.traffic_split):
            raise ValueError("variants and traffic_split must have the same length")
        total = sum(self.traffic_split)
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(f"traffic_split must sum to 1.0, got {total}")

    def assign(self, unit_id: str) -> ABVariant:
        """Deterministically assign a unit (candidate_id, session_id, etc.) to a variant.

        Uses a hash of (experiment_id + unit_id) modulo 1000 to achieve stable assignment.
        The same unit always gets the same variant across calls.
        """
        hash_input = f"{self.experiment_id}:{unit_id}".encode()
        digest = int(hashlib.sha256(hash_input).hexdigest(), 16)
        bucket = (digest % 1000) / 1000.0   # 0.000 … 0.999

        cumulative = 0.0
        for variant, split in zip(self.variants, self.traffic_split, strict=True):
            cumulative += split
            if bucket < cumulative:
                return variant
        return self.variants[-1]  # safety fallback


# Pre-built experiments
DET_WEIGHT_EXPERIMENT = ABExperiment(
    experiment_id="det_weight_v1",
    description="Test 0.60 vs 0.50 deterministic weight in hybrid scoring",
    variants=[
        ABVariant(name="control", description="det_weight=0.60 (current default)", config={"det_weight": 0.60}),
        ABVariant(name="treatment", description="det_weight=0.50 (equal weights)", config={"det_weight": 0.50}),
    ],
    traffic_split=[0.50, 0.50],
)

APPLY_THRESHOLD_EXPERIMENT = ABExperiment(
    experiment_id="apply_threshold_v1",
    description="Test whether raising the apply threshold (0.60 → 0.65) improves interview rate",
    variants=[
        ABVariant(name="control",   description="apply_threshold=0.60", config={"apply_threshold": 0.60}),
        ABVariant(name="treatment", description="apply_threshold=0.65", config={"apply_threshold": 0.65}),
    ],
    traffic_split=[0.50, 0.50],
)
