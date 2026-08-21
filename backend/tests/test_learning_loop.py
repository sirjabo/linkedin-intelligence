"""Tests for Learning Loop: calibration analysis and insights endpoint."""
import pytest
from httpx import AsyncClient

from app.services.learning_loop import compute_calibration

SAMPLE_JD = """\
Senior Data Engineer — TechCorp
We are looking for a Senior Data Engineer with 5+ years of experience.
Location: Buenos Aires, Argentina (hybrid)
Full-time position. Mandatory: Python, SQL.
"""


# ── Unit tests: compute_calibration ──────────────────────────────────────────

def test_empty_outcomes_returns_insufficient():
    report = compute_calibration([])
    assert report.bias_direction == "insufficient_data"
    assert report.total_outcomes == 0
    assert report.overall_interview_rate is None


def test_fewer_than_min_outcomes_insufficient():
    outcomes = [
        {"tier": "strong", "outcome": "got_interview"},
        {"tier": "moderate", "outcome": "rejected"},
    ]
    report = compute_calibration(outcomes)
    assert report.bias_direction == "insufficient_data"
    assert report.total_outcomes == 2


def test_pending_outcomes_not_counted():
    outcomes = [{"tier": "strong", "outcome": None}] * 10
    report = compute_calibration(outcomes)
    assert report.total_outcomes == 0
    assert report.bias_direction == "insufficient_data"


def test_well_calibrated_detection():
    outcomes = (
        [{"tier": "excellent", "outcome": "got_interview"}] * 6 +
        [{"tier": "excellent", "outcome": "rejected"}] * 4 +
        [{"tier": "strong", "outcome": "got_interview"}] * 4 +
        [{"tier": "strong", "outcome": "rejected"}] * 6
    )
    report = compute_calibration(outcomes)
    assert report.total_outcomes == 20
    assert report.overall_interview_rate is not None
    assert report.bias_direction in ("well_calibrated", "over_optimistic", "under_optimistic")


def test_over_optimistic_detection():
    # All matches are "excellent" but nobody gets an interview
    outcomes = [{"tier": "excellent", "outcome": "rejected"}] * 10
    report = compute_calibration(outcomes)
    assert report.bias_direction == "over_optimistic"
    assert report.overall_interview_rate == 0.0
    assert any("over-optimistic" in i.lower() for i in report.insights)


def test_under_optimistic_detection():
    # All matches are "poor" but everyone gets an interview
    outcomes = [{"tier": "poor", "outcome": "got_interview"}] * 10
    report = compute_calibration(outcomes)
    assert report.bias_direction == "under_optimistic"
    assert report.overall_interview_rate == 1.0
    assert any("under-optimistic" in i.lower() for i in report.insights)


def test_calibration_score_well_calibrated():
    # Strong tier: expected 40% interview rate, simulate ~40%
    outcomes = (
        [{"tier": "strong", "outcome": "got_interview"}] * 4 +
        [{"tier": "strong", "outcome": "rejected"}] * 6
    )
    report = compute_calibration(outcomes)
    assert report.calibration_score is not None
    assert 0.5 < report.calibration_score < 2.0


def test_by_tier_breakdown_populated():
    outcomes = (
        [{"tier": "strong", "outcome": "got_interview"}] * 3 +
        [{"tier": "moderate", "outcome": "rejected"}] * 3 +
        [{"tier": "weak", "outcome": "ghosted"}] * 2
    )
    report = compute_calibration(outcomes)
    tiers = {t.tier for t in report.by_tier}
    assert "strong" in tiers
    assert "moderate" in tiers

    strong = next(t for t in report.by_tier if t.tier == "strong")
    assert strong.interview_rate == pytest.approx(1.0)
    assert strong.rejection_rate == pytest.approx(0.0)


def test_offer_counts_as_positive():
    outcomes = [{"tier": "excellent", "outcome": "offer"}] * 5 + \
               [{"tier": "excellent", "outcome": "rejected"}] * 5
    report = compute_calibration(outcomes)
    assert report.overall_interview_rate == pytest.approx(0.5)


def test_withdrew_outcome_ignored_in_rates():
    # "withdrew" is neither positive nor negative
    outcomes = [{"tier": "strong", "outcome": "withdrew"}] * 3 + \
               [{"tier": "strong", "outcome": "got_interview"}] * 4 + \
               [{"tier": "strong", "outcome": "rejected"}] * 3
    report = compute_calibration(outcomes)
    # withdrew doesn't go into interview_rate calculation for the tier
    strong = next(t for t in report.by_tier if t.tier == "strong")
    # 4 positives / 7 recorded (withdrew counts as recorded but not positive/negative)
    assert strong.outcomes_recorded == 10
    assert strong.interview_rate == pytest.approx(4 / 10)


# ── Integration test ─────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v2/auth/register", json={"email": email, "password": "Secure1234"})
    assert reg.status_code == 201
    return reg.json()["access_token"]


@pytest.mark.asyncio
async def test_learning_insights_no_outcomes(client: AsyncClient):
    token = await _register_and_login(client, "learn1@example.com")
    resp = await client.get(
        "/api/v2/candidates/me/learning-insights",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bias_direction"] == "insufficient_data"
    assert data["total_outcomes"] == 0


@pytest.mark.asyncio
async def test_learning_insights_after_feedback(client: AsyncClient, mock_job_agent, mock_match_agent):
    token = await _register_and_login(client, "learn2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create job and match
    job_resp = await client.post("/api/v2/jobs", headers=headers, json={"raw_jd": SAMPLE_JD})
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    await client.post(f"/api/v2/jobs/{job_id}/match", headers=headers)

    # Record outcome
    fb = await client.post(
        f"/api/v2/jobs/{job_id}/match/feedback",
        headers=headers,
        json={"outcome": "rejected"},
    )
    assert fb.status_code == 200

    # Learning insights should now include 1 outcome (insufficient for calibration)
    resp = await client.get("/api/v2/candidates/me/learning-insights", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_outcomes"] == 1
    assert data["bias_direction"] == "insufficient_data"
    assert len(data["by_tier"]) > 0
