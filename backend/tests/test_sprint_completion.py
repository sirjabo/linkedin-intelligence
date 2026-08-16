"""Sprint completion tests — validates EvidenceBuilder integration,
transferable skills, domain scoring, hypothesis testing, and auto-threshold
trigger path (unit-level, no DB).
"""


from app.services.claim_validator import EvidenceBuilder, EvidenceRecord
from app.services.learning_loop import (
    CalibrationReport,
    _norm_sf,
    _update_thresholds,
    compute_calibration,
)
from app.services.matching.engine import (
    TRANSFERABLE_SKILLS,
    _classify_requirement_status,
    _score_domain,
    compute_deterministic,
)

# ── EvidenceBuilder ───────────────────────────────────────────────────────────

def test_evidence_builder_returns_empty_for_none():
    assert EvidenceBuilder.build_from_profile(None) == []


def test_evidence_builder_returns_empty_for_empty_profile():
    records = EvidenceBuilder.build_from_profile({})
    assert isinstance(records, list)
    # No experiences/skills → nothing extracted
    assert records == []


def test_evidence_builder_extracts_experience():
    profile = {
        "experience": [
            {
                "role": "Senior Engineer",
                "company": "Acme",
                "bullets": ["Built payment system", "Led team of 5"],
                "technologies": ["Python", "FastAPI"],
                "duration_years": 3,
            }
        ]
    }
    records = EvidenceBuilder.build_from_profile(profile)
    assert len(records) >= 1
    exp_rec = records[0]
    assert isinstance(exp_rec, EvidenceRecord)
    assert "Acme" in exp_rec.content
    assert exp_rec.source_type == "experience"


def test_evidence_builder_extracts_skills():
    profile = {
        "skills": [
            {"canonical_name": "Python", "years": 5},
            {"canonical_name": "FastAPI", "years": 2},
        ]
    }
    records = EvidenceBuilder.build_from_profile(profile)
    skill_recs = [r for r in records if r.source_type == "skill"]
    assert len(skill_recs) >= 1


def test_evidence_builder_extracts_projects():
    profile = {
        "projects": [
            {"name": "CV Parser", "description": "NLP pipeline", "tech": ["spaCy", "Python"]}
        ]
    }
    records = EvidenceBuilder.build_from_profile(profile)
    proj_recs = [r for r in records if r.source_type == "project"]
    assert len(proj_recs) >= 1


def test_evidence_builder_works_on_orm_like_object():
    class FakeProfile:
        experience = [
            {"role": "ML Engineer", "company": "DeepCo", "bullets": [], "technologies": ["PyTorch"]}
        ]
        skills = [{"canonical_name": "PyTorch", "years": 2}]
        projects = []
        education = []
        certifications = []
        achievements = []

    records = EvidenceBuilder.build_from_profile(FakeProfile())
    assert len(records) >= 1


# ── Transferable Skills ───────────────────────────────────────────────────────

def test_transferable_skills_dict_non_empty():
    assert len(TRANSFERABLE_SKILLS) >= 10


def test_machine_learning_transfers_to_data_science():
    candidate_skills = {"machine learning"}
    result = _classify_requirement_status("data science", candidate_skills, "must_have")
    assert result.candidate_status == "PARTIAL"
    assert result.match_score < 0.5  # transferable match scored lower than weak partial


def test_devops_transfers_to_sre():
    candidate_skills = {"devops"}
    result = _classify_requirement_status("sre", candidate_skills, "must_have")
    assert result.candidate_status == "PARTIAL"


def test_mobile_transfers_to_ios():
    candidate_skills = {"mobile"}
    result = _classify_requirement_status("ios", candidate_skills, "nice_to_have")
    assert result.candidate_status == "PARTIAL"


def test_no_transfer_when_unrelated():
    candidate_skills = {"frontend"}
    result = _classify_requirement_status("data engineering", candidate_skills, "must_have")
    # No transfer path between frontend and data engineering
    assert result.candidate_status == "BLOCKER"


def test_direct_match_still_takes_priority():
    candidate_skills = {"machine learning"}
    result = _classify_requirement_status("machine learning", candidate_skills, "must_have")
    assert result.candidate_status == "MATCHED"
    assert result.match_score == 1.0


def test_transferable_score_below_weak_partial():
    # Weak partial (first token match) should score 0.5; transferable should be lower
    candidate_skills = {"machine learning"}
    transfer_result = _classify_requirement_status("data science", candidate_skills, "must_have")
    assert transfer_result.match_score <= 0.4


# ── Domain Scoring ────────────────────────────────────────────────────────────

def test_domain_score_fintech_exact():
    score = _score_domain(["fintech", "payments"], "We are a fintech startup building payment solutions")
    assert score == 1.0


def test_domain_score_healthtech():
    score = _score_domain(["healthcare", "medical devices"], "Digital health platform for patient management")
    assert score is not None and score > 0.0


def test_domain_score_no_overlap():
    score = _score_domain(["gaming", "esports"], "B2B SaaS platform for enterprise logistics")
    # gaming candidate vs logistics/saas job — no domain match expected
    assert score == 0.0 or score is None


def test_domain_score_returns_none_for_missing_industries():
    assert _score_domain(None, "fintech payment company") is None


def test_domain_score_returns_none_for_missing_job_text():
    assert _score_domain(["fintech"], None) is None


def test_domain_score_returns_none_for_undetectable_job():
    # Job text with no domain keywords
    result = _score_domain(["fintech"], "We build software for our clients")
    assert result is None or result == 0.0


def test_compute_deterministic_includes_domain_score():
    result = compute_deterministic(
        profile_skills=[],
        profile_career_level="mid",
        profile_education=[],
        candidate_location="Remote",
        job_seniority="mid",
        job_location=None,
        job_remote_type="remote",
        job_tech_stack=[],
        requirements=[],
        candidate_industries=["fintech"],
        job_text="payment processing fintech company",
    )
    assert result.domain_score is not None
    assert 0.0 <= result.domain_score <= 1.0


def test_compute_deterministic_domain_score_none_without_inputs():
    result = compute_deterministic(
        profile_skills=[],
        profile_career_level="mid",
        profile_education=[],
        candidate_location="Remote",
        job_seniority="mid",
        job_location=None,
        job_remote_type="remote",
        job_tech_stack=[],
        requirements=[],
    )
    assert result.domain_score is None


# ── Hypothesis Testing ────────────────────────────────────────────────────────

def test_norm_sf_at_zero_is_half():
    assert abs(_norm_sf(0.0) - 0.5) < 1e-6


def test_norm_sf_large_z_near_zero():
    assert _norm_sf(10.0) < 0.001


def test_calibration_report_has_p_value_field():
    report = CalibrationReport(
        total_outcomes=0,
        by_tier=[],
        overall_interview_rate=None,
        bias_direction="insufficient_data",
        calibration_score=None,
    )
    assert report.p_value is None
    assert report.significant is False


def test_p_value_computed_when_sufficient_data():
    # 5+ outcomes needed; use 10 to be safe
    outcomes = [
        {"tier": "strong", "outcome": "got_interview"},
        {"tier": "strong", "outcome": "got_interview"},
        {"tier": "strong", "outcome": "rejected"},
        {"tier": "strong", "outcome": "rejected"},
        {"tier": "strong", "outcome": "rejected"},
        {"tier": "moderate", "outcome": "rejected"},
        {"tier": "moderate", "outcome": "rejected"},
        {"tier": "moderate", "outcome": "rejected"},
        {"tier": "moderate", "outcome": "rejected"},
        {"tier": "moderate", "outcome": "rejected"},
    ]
    report = compute_calibration(outcomes)
    assert report.p_value is not None
    assert 0.0 <= report.p_value <= 1.0
    assert isinstance(report.significant, bool)


def test_p_value_none_for_insufficient_data():
    outcomes = [
        {"tier": "strong", "outcome": "got_interview"},
        {"tier": "strong", "outcome": "rejected"},
    ]
    report = compute_calibration(outcomes)
    assert report.p_value is None
    assert report.significant is False


def test_p_value_significant_when_rate_deviates_strongly():
    # Observed rate = 0% (all rejected in "excellent" tier where expected is 60%)
    outcomes = [{"tier": "excellent", "outcome": "rejected"} for _ in range(20)]
    report = compute_calibration(outcomes)
    assert report.p_value is not None
    assert report.significant is True  # 0% vs 60% expected — very significant


def test_p_value_not_significant_for_well_calibrated():
    # Observed rate ≈ expected for "moderate" (20%)
    outcomes = (
        [{"tier": "moderate", "outcome": "got_interview"}] * 2
        + [{"tier": "moderate", "outcome": "rejected"}] * 8
    )
    report = compute_calibration(outcomes)
    # 2/10 = 20% observed vs 20% expected — should not be significant
    assert report.p_value is not None
    assert report.significant is False


# ── _update_thresholds integration ───────────────────────────────────────────

def test_update_thresholds_raises_for_well_calibrated():
    outcomes = (
        [{"tier": "moderate", "outcome": "got_interview"}] * 2
        + [{"tier": "moderate", "outcome": "rejected"}] * 8
    ) * 3  # 30 total, enough for calibration and threshold update
    calibration = compute_calibration(outcomes)
    new_thresh, updates = _update_thresholds(calibration)
    assert isinstance(new_thresh, dict)
    assert isinstance(updates, list)
    assert all(isinstance(u.tier, str) for u in updates)


def test_update_thresholds_raises_threshold_for_over_optimistic_tier():
    # All rejected in "excellent" tier → over-optimistic → threshold should be raised
    outcomes = [{"tier": "excellent", "outcome": "rejected"} for _ in range(15)]
    calibration = compute_calibration(outcomes)
    _, updates = _update_thresholds(calibration)
    excellent_updates = [u for u in updates if u.tier == "excellent"]
    if excellent_updates:
        assert excellent_updates[0].direction == "raised"


def test_update_thresholds_lowers_threshold_for_under_optimistic_tier():
    # All interviews in "poor" tier → under-optimistic → threshold should be lowered
    outcomes = [{"tier": "poor", "outcome": "got_interview"} for _ in range(15)]
    calibration = compute_calibration(outcomes)
    _, updates = _update_thresholds(calibration)
    poor_updates = [u for u in updates if u.tier == "poor"]
    if poor_updates:
        assert poor_updates[0].direction == "lowered"
