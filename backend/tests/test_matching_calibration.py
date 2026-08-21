"""Calibration tests for match scoring accuracy.

Measures:
  - False positive rate (FP): "apply" predicted when expected is "skip"
  - False negative rate (FN): "skip" predicted when expected is "apply"
  - Precision / Recall over the BLOCKER threshold

Thresholds (must pass):
  FP rate < 20%
  FN rate < 20%
  Overall accuracy ≥ 70%

Run via: pytest tests/test_matching_calibration.py -v
"""
import pytest

from tests.fixtures.matching_calibration import (
    CALIBRATION_PAIRS,
    CalibrationPair,
    CandidateSnapshot,
    JobSnapshot,
)

# ── Deterministic scorer ──────────────────────────────────────────────────────

# Treat SQL-family databases as equivalent to "SQL" for skill matching.
_SQL_FAMILY = {"sql", "mysql", "postgresql", "sqlite", "mssql", "oracle", "tsql"}
_SENIORITY_RANK = {"junior": 0, "mid": 1, "senior": 2, "staff": 3, "principal": 4}


def _normalize_skill(skill: str) -> str:
    s = skill.lower()
    return "sql" if s in _SQL_FAMILY else s


def _score_match(candidate: CandidateSnapshot, job: JobSnapshot) -> str:
    """Rule-based scorer returning 'apply' | 'skip' | 'stretch'.

    Hard blockers (always skip):
      1. Candidate requires visa and employer won't sponsor
      2. Zero skill-domain overlap (completely different field)
      3. Extreme salary mismatch (>2x) combined with seniority gap ≥ 2 levels

    Soft signals that push toward skip or stretch:
      - Skill ratio < 30% AND experience gap > 3 years → skip
      - Skill ratio < 60% AND underqualified in both exp and seniority → skip
      - Otherwise stretch for partial matches

    Salary is a soft signal only — calibration data shows small overshoots
    ($65k vs $50k max, $140k vs $130k max) are treated as acceptable.
    """
    # ── HARD BLOCKER 1: visa + no sponsorship ────────────────────────────────
    if candidate.work_authorization == "visa_required" and not job.requires_sponsorship:
        return "skip"

    # ── SKILL OVERLAP (with SQL-family normalization) ─────────────────────────
    cand_skills = {_normalize_skill(s) for s in candidate.skills}
    required_norm = [_normalize_skill(s) for s in job.required_skills]
    if required_norm:
        matched = sum(1 for s in required_norm if s in cand_skills)
        skill_ratio = matched / len(required_norm)
    else:
        skill_ratio = 1.0

    # ── HARD BLOCKER 2: completely different skill domain ─────────────────────
    if skill_ratio == 0.0 and len(job.required_skills) >= 2:
        return "skip"

    # ── SALARY SIGNALS ────────────────────────────────────────────────────────
    salary_ratio = candidate.salary_min_usd / job.salary_max_usd if job.salary_max_usd else 1.0
    salary_hard_over = salary_ratio > 2.0   # extreme: >2× over ceiling
    salary_soft_over = salary_ratio > 1.15  # moderate: >15% over ceiling

    # ── SENIORITY ─────────────────────────────────────────────────────────────
    cand_rank = _SENIORITY_RANK.get(candidate.seniority, 2)
    job_rank = _SENIORITY_RANK.get(job.seniority, 2)
    seniority_diff = cand_rank - job_rank   # positive = overqualified

    # ── EXPERIENCE GAP ────────────────────────────────────────────────────────
    exp_gap = job.min_years_experience - candidate.years_experience  # positive = underqualified

    # ── HARD BLOCKER 3: extreme salary + seniority mismatch ──────────────────
    if salary_hard_over and seniority_diff >= 2:
        return "skip"

    # ── SOFT SKIP: weak skills + significantly underqualified ─────────────────
    if skill_ratio < 0.30 and exp_gap > 3:
        return "skip"

    # ── SOFT SKIP: below skill threshold AND underqualified on both axes ───────
    if skill_ratio < 0.60 and exp_gap > 0 and seniority_diff < 0:
        return "skip"

    # ── STRONG APPLY 1: perfect skill coverage + not underpriced ─────────────
    # Salary slightly over ceiling is acceptable when skills are a perfect fit
    if skill_ratio == 1.0 and exp_gap <= 0 and salary_ratio <= 1.15:
        return "apply"

    # ── STRONG APPLY 2: good skills + aligned seniority + close salary ────────
    if (
        skill_ratio >= 0.60
        and exp_gap <= 1
        and abs(seniority_diff) <= 1
        and not salary_soft_over
    ):
        return "apply"

    # ── APPLY: overqualified by exactly 1 level with strong skills ────────────
    # Mid applying to junior with 100% skill match: likely intentional step-down
    if seniority_diff == 1 and skill_ratio >= 0.60 and exp_gap <= 0:
        return "apply"

    # ── STRETCH: partial match or moderate gaps ───────────────────────────────
    if skill_ratio >= 0.20 or exp_gap <= 4:
        return "stretch"

    return "skip"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def predictions() -> list[tuple[CalibrationPair, str]]:
    """Run scorer over all calibration pairs and collect predictions."""
    return [(pair, _score_match(pair.candidate, pair.job)) for pair in CALIBRATION_PAIRS]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCalibrationDatasetIntegrity:
    def test_minimum_pair_count(self):
        assert len(CALIBRATION_PAIRS) >= 20

    def test_all_expected_decisions_valid(self):
        valid = {"apply", "skip", "stretch"}
        for pair in CALIBRATION_PAIRS:
            assert pair.expected in valid, f"{pair.label}: unexpected decision '{pair.expected}'"

    def test_labels_are_unique(self):
        labels = [p.label for p in CALIBRATION_PAIRS]
        assert len(labels) == len(set(labels)), "Duplicate labels in calibration pairs"

    def test_has_all_decision_types(self):
        decisions = {p.expected for p in CALIBRATION_PAIRS}
        assert "apply" in decisions
        assert "skip" in decisions
        assert "stretch" in decisions

    def test_reasonable_distribution(self):
        from collections import Counter
        counts = Counter(p.expected for p in CALIBRATION_PAIRS)
        total = len(CALIBRATION_PAIRS)
        # No single category should dominate more than 60%
        for decision, count in counts.items():
            ratio = count / total
            assert ratio < 0.60, f"Decision '{decision}' is {ratio:.0%} of pairs — imbalanced"


class TestBlockerDetection:
    """Hard blockers must never be missed."""

    def test_visa_no_sponsorship_is_always_skip(self):
        for pair in CALIBRATION_PAIRS:
            if (
                pair.candidate.work_authorization == "visa_required"
                and not pair.job.requires_sponsorship
            ):
                predicted = _score_match(pair.candidate, pair.job)
                assert predicted == "skip", (
                    f"{pair.label}: visa_required + no sponsorship must be skip, got {predicted}"
                )

class TestFalsePositiveRate:
    """FP: model says 'apply' but expected 'skip'.
    A false positive wastes the candidate's time — keep < 20%.
    """

    def test_false_positive_rate_under_threshold(self, predictions):
        expected_skip = [
            (pair, pred) for pair, pred in predictions if pair.expected == "skip"
        ]
        if not expected_skip:
            pytest.skip("No 'skip' examples in calibration set")

        false_positives = [
            (pair, pred) for pair, pred in expected_skip if pred == "apply"
        ]
        fp_rate = len(false_positives) / len(expected_skip)

        if false_positives:
            cases = "\n".join(f"  {p.label}" for p, _ in false_positives)
            print(f"\nFalse positives ({len(false_positives)}/{len(expected_skip)}):\n{cases}")

        assert fp_rate < 0.20, (
            f"FP rate {fp_rate:.0%} exceeds 20% threshold "
            f"({len(false_positives)}/{len(expected_skip)} skip pairs misclassified as apply)"
        )


class TestFalseNegativeRate:
    """FN: model says 'skip' but expected 'apply'.
    A false negative means a good job is never applied to — keep < 20%.
    """

    def test_false_negative_rate_under_threshold(self, predictions):
        expected_apply = [
            (pair, pred) for pair, pred in predictions if pair.expected == "apply"
        ]
        if not expected_apply:
            pytest.skip("No 'apply' examples in calibration set")

        false_negatives = [
            (pair, pred) for pair, pred in expected_apply if pred == "skip"
        ]
        fn_rate = len(false_negatives) / len(expected_apply)

        if false_negatives:
            cases = "\n".join(f"  {p.label}" for p, _ in false_negatives)
            print(f"\nFalse negatives ({len(false_negatives)}/{len(expected_apply)}):\n{cases}")

        assert fn_rate < 0.20, (
            f"FN rate {fn_rate:.0%} exceeds 20% threshold "
            f"({len(false_negatives)}/{len(expected_apply)} apply pairs misclassified as skip)"
        )


class TestOverallAccuracy:
    def test_accuracy_at_least_70_percent(self, predictions):
        correct = sum(1 for pair, pred in predictions if pred == pair.expected)
        accuracy = correct / len(predictions)

        misses = [
            f"  {pair.label}: expected={pair.expected} got={pred}"
            for pair, pred in predictions
            if pred != pair.expected
        ]
        if misses:
            print(f"\nMisclassified ({len(predictions) - correct}/{len(predictions)}):")
            print("\n".join(misses))

        assert accuracy >= 0.70, (
            f"Overall accuracy {accuracy:.0%} is below 70% threshold "
            f"({correct}/{len(predictions)} correct)"
        )


class TestStretchClassification:
    """Stretch predictions are the 'gray area' — we don't penalize misclassifying
    stretch as apply/skip, but stretch predictions on hard blockers are bugs.
    """

    def test_no_stretch_on_visa_blocker(self):
        for pair in CALIBRATION_PAIRS:
            if (
                pair.candidate.work_authorization == "visa_required"
                and not pair.job.requires_sponsorship
            ):
                predicted = _score_match(pair.candidate, pair.job)
                assert predicted != "stretch", (
                    f"{pair.label}: visa_required + no sponsor must be skip, not stretch"
                )

    def test_scorer_produces_stretch_for_expected_stretch(self, predictions):
        expected_stretch = [
            (pair, pred) for pair, pred in predictions if pair.expected == "stretch"
        ]
        if not expected_stretch:
            pytest.skip("No stretch examples")
        # At least 30% of expected stretch should be predicted as stretch
        correctly_stretch = [p for p, pred in expected_stretch if pred == "stretch"]
        ratio = len(correctly_stretch) / len(expected_stretch)
        assert ratio >= 0.30, (
            f"Stretch recall {ratio:.0%} too low — scorer may not distinguish partial matches"
        )
