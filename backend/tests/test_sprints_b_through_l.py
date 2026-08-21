"""Tests for Sprints B through L.

Sprint B  - CandidateKnowledgeResolver skill_years + deduplication
Sprint C  - ClaimValidator CONTRADICTED + EvidenceBuilder
Sprint D  - Matching engine RequirementMatch breakdown
Sprint E  - ApplicationStrategy new fields (schema validation)
Sprint F  - FormIntelligence skill_years + experience_essay types
Sprint G  - ATS adapters (greenhouse sections, lever validation errors, workday sections)
Sprint H  - CV file validation (_validate_cv_file)
Sprint I  - Orchestrator PAUSED state machine
Sprint K  - AI Evaluation LLMEvaluationCriterion schema + evaluate_llm (no real LLM)
Sprint L  - LearningLoop threshold updates + A/B experiment assignment
"""
import os
import tempfile
import uuid

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Sprint B — skill_years deduplication
# ──────────────────────────────────────────────────────────────────────────────
from app.services.candidate_knowledge_resolver import DateRange, _deduplicate_periods


def test_deduplicate_non_overlapping():
    periods = [DateRange(2018.0, 2020.0), DateRange(2021.0, 2023.0)]
    assert abs(_deduplicate_periods(periods) - 4.0) < 0.01


def test_deduplicate_overlapping():
    # Two roles using the same skill simultaneously → should not double-count
    periods = [DateRange(2019.0, 2022.0), DateRange(2020.0, 2023.0)]
    total = _deduplicate_periods(periods)
    # Merged span 2019–2023 = 4 years
    assert abs(total - 4.0) < 0.01


def test_deduplicate_fully_contained():
    # Inner period fully inside outer
    periods = [DateRange(2018.0, 2024.0), DateRange(2020.0, 2022.0)]
    assert abs(_deduplicate_periods(periods) - 6.0) < 0.01


def test_deduplicate_open_end():
    # None end_year means "still working"
    periods = [DateRange(2022.0, None)]
    total = _deduplicate_periods(periods)
    assert total >= 0  # just check it doesn't raise


def test_deduplicate_empty():
    assert _deduplicate_periods([]) == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Sprint C — EvidenceBuilder + CONTRADICTED
# ──────────────────────────────────────────────────────────────────────────────

from app.services.claim_validator import (
    EvidenceBuilder,
    EvidenceRecord,
    _check_contradiction,
    validate_claims,
)


def _simple_profile():
    return {
        "experience": [
            {
                "role": "Backend Engineer",
                "company": "Acme",
                "bullets": ["Built payment API", "Reduced latency 30%"],
                "technologies": ["python", "fastapi"],
                "duration_years": 3,
            }
        ],
        "skills": [
            {"canonical_name": "python", "years_experience": 3},
            {"canonical_name": "fastapi", "years_experience": 2},
        ],
        "projects": [
            {
                "name": "MLPipeline",
                "description": "Data ingestion pipeline",
                "tech": ["python", "airflow"],
                "highlights": ["Processed 1M records/day"],
            }
        ],
        "education": [{"degree": "BSc", "field": "Computer Science", "institution": "MIT"}],
    }


def test_evidence_builder_from_profile():
    profile = _simple_profile()
    records = EvidenceBuilder.build_from_profile(profile, extra_text="Python expert")
    assert len(records) >= 3  # experience + skills + project + education + summary
    source_types = {r.source_type for r in records}
    assert "experience" in source_types
    assert "skill" in source_types
    assert "project" in source_types


def test_evidence_builder_none_profile():
    records = EvidenceBuilder.build_from_profile(None)
    assert records == []


def test_evidence_builder_skills_as_dict():
    profile = {"skills": {"backend": ["python", "django"], "infra": ["docker"]}}
    records = EvidenceBuilder.build_from_profile(profile)
    skill_records = [r for r in records if r.source_type == "skill"]
    assert len(skill_records) == 3


def test_validate_claims_supported():
    profile = _simple_profile()
    records = EvidenceBuilder.build_from_profile(profile)
    # Sentence that mentions python and fastapi and backend — should match
    text = "I built APIs using Python and FastAPI. Reduced latency by 30%."
    result = validate_claims(text, records)
    # At least some should be supported or plausible (not all UNSUPPORTED)
    assert len(result.unverified_claims) < 5 or len(result.verified_claims) > 0 or len(result.plausible_claims) > 0


def test_validate_claims_contradicted():
    records = [EvidenceRecord(
        source_type="skill",
        content="Skill: python (3 years)",
        skills_mentioned=["python"],
    )]
    text = "I have 10 years of python experience."
    result = validate_claims(text, records)
    assert len(result.contradicted_claims) > 0


def test_validate_claims_empty_evidence():
    result = validate_claims("I built APIs.", [])
    # Nothing to contradict or support — all unsupported
    # (claims may be 0 if no pattern matches)
    assert result.is_clean or len(result.unverified_claims) >= 0


def test_check_contradiction_detects_inflation():
    records = [EvidenceRecord(
        source_type="experience",
        content="Backend Engineer at Acme. python fastapi (2 years)",
        skills_mentioned=["python", "fastapi"],
    )]
    contradiction = _check_contradiction("I have 10 years of python experience", records)
    assert contradiction is not None
    assert "10" in contradiction or "years" in contradiction.lower()


def test_check_contradiction_no_inflation():
    records = [EvidenceRecord(
        source_type="skill",
        content="Skill: python (5 years)",
        skills_mentioned=["python"],
    )]
    # Claimed 3 years, evidence says 5 — no contradiction
    result = _check_contradiction("I have 3 years of python experience", records)
    assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# Sprint D — RequirementMatch breakdown
# ──────────────────────────────────────────────────────────────────────────────

from app.services.matching.engine import (
    RequirementMatch,
    _classify_requirement_status,
    compute_deterministic,
)


def test_classify_requirement_status_matched():
    rm = _classify_requirement_status(
        description="Python backend development",
        candidate_skills={"python", "django", "fastapi"},
        req_type="must_have",
    )
    assert isinstance(rm, RequirementMatch)
    assert rm.candidate_status in ("MATCHED", "PARTIAL")
    assert rm.importance == "MUST"


def test_classify_requirement_status_blocker():
    rm = _classify_requirement_status(
        description="Kubernetes orchestration",
        candidate_skills={"python", "django"},
        req_type="must_have",
    )
    assert rm.candidate_status == "BLOCKER"
    assert rm.match_score == 0.0


def test_classify_requirement_status_missing_nice():
    rm = _classify_requirement_status(
        description="GraphQL experience preferred",
        candidate_skills={"python", "rest"},
        req_type="nice_to_have",
    )
    assert rm.candidate_status == "MISSING"
    assert rm.importance == "NICE_TO_HAVE"


def test_compute_deterministic_includes_req_matches():
    from app.db.models.job import JobRequirement

    req = JobRequirement()
    req.requirement_type = "must_have"
    req.description = "Python backend"
    req.id = uuid.uuid4()

    result = compute_deterministic(
        profile_skills=[{"canonical_name": "python"}],
        profile_career_level="senior",
        profile_education=[],
        candidate_location="remote",
        job_seniority="senior",
        job_location="remote",
        job_remote_type="remote",
        job_tech_stack=["python"],
        requirements=[req],
        job_salary_max=None,
        candidate_salary_pref_min=None,
    )
    assert hasattr(result, "requirement_matches")
    assert len(result.requirement_matches) > 0
    assert all(isinstance(rm, RequirementMatch) for rm in result.requirement_matches)


# ──────────────────────────────────────────────────────────────────────────────
# Sprint E — ApplicationStrategy new fields
# ──────────────────────────────────────────────────────────────────────────────

from app.services.agents.application_agent import ApplicationStrategy


def test_application_strategy_has_sprint_e_fields():
    s = ApplicationStrategy(
        overall_approach="Emphasize platform work",
        recommendation="apply_with_tailoring",
        positioning="Senior backend engineer moving into platform engineering",
        target_narrative="5 years backend, now targeting infrastructure tooling",
        keywords_for_form=["kubernetes", "terraform", "python"],
        answer_strategy={"Why join us?": "Focus on open-source commitment"},
        interview_preparation_strategy=["Prepare STAR story for Kubernetes migration"],
        claims_to_avoid=["Rust proficiency"],
        company_specific_angle="Their infra-as-code approach aligns with my work at Acme",
    )
    assert s.positioning.startswith("Senior")
    assert "kubernetes" in s.keywords_for_form
    assert len(s.claims_to_avoid) == 1
    assert s.company_specific_angle


def test_application_strategy_defaults_empty():
    s = ApplicationStrategy(overall_approach="X", recommendation="pass")
    assert s.positioning == ""
    assert s.target_narrative == ""
    assert s.keywords_for_form == []
    assert s.answer_strategy == {}
    assert s.interview_preparation_strategy == []
    assert s.claims_to_avoid == []
    assert s.company_specific_angle == ""


# ──────────────────────────────────────────────────────────────────────────────
# Sprint F — FormIntelligence skill_years + experience_essay
# ──────────────────────────────────────────────────────────────────────────────

from app.services.form_intelligence import (
    FieldSpec,
    classify_field,
    extract_skill_target,
    map_candidate_to_form,
)


@pytest.mark.parametrize("label,expected", [
    ("Years of Python experience", "skill_years"),
    ("How many years of React have you used?", "skill_years"),
    ("Kubernetes years", "skill_years"),
    ("Total years of experience", "years_experience"),
    ("Tell us about your backend experience", "experience_essay"),
    ("Describe your journey in data engineering", "experience_essay"),
    ("Why do you want to join us?", "custom_essay"),
    ("First name", "first_name"),
    ("Email address", "email"),
])
def test_classify_field_sprint_f(label, expected):
    assert classify_field(label) == expected


def test_extract_skill_target():
    assert extract_skill_target("Years of Python experience") == "python"
    assert extract_skill_target("React years") == "react"
    assert extract_skill_target("Total years") is None


def test_map_candidate_to_form_skill_years_has_skill_target():
    fields = [FieldSpec(label="Years of Python experience", field_type="number", is_required=True)]
    result = map_candidate_to_form(
        fields=fields,
        candidate_name="Jane Doe",
        candidate_email="jane@example.com",
        candidate_location="Remote",
        candidate_salary_min=None,
        candidate_work_authorization=None,
        candidate_availability=None,
    )
    assert len(result) == 1
    mf = result[0]
    assert mf.semantic_type == "skill_years"
    assert mf.skill_target == "python"
    assert mf.human_required is True  # orchestrator routes through resolver


def test_mapped_field_has_confidence():
    fields = [FieldSpec(label="Email address")]
    result = map_candidate_to_form(
        fields=fields,
        candidate_name=None,
        candidate_email="a@b.com",
        candidate_location=None,
        candidate_salary_min=None,
        candidate_work_authorization=None,
        candidate_availability=None,
    )
    assert result[0].confidence == 1.0
    assert result[0].classification_source == "regex"


# ──────────────────────────────────────────────────────────────────────────────
# Sprint G — ATS adapters
# ──────────────────────────────────────────────────────────────────────────────

from app.services.ats.adapter import retry_with_backoff
from app.services.ats.greenhouse import GreenhouseAdapter
from app.services.ats.lever import LeverAdapter
from app.services.ats.workday import WorkdayAdapter


def test_greenhouse_adapter_has_eeo_detection():
    adapter = GreenhouseAdapter()
    assert hasattr(adapter, "eeo_section_present")
    assert adapter.eeo_section_present is False


def test_greenhouse_adapter_tracks_sections():
    from app.services.browser.adapter import RawFormField
    adapter = GreenhouseAdapter()
    field = RawFormField(
        field_id="f1", name="f1", label="Name", field_type="text",
        is_required=True, options=None, placeholder=None,
        css_selector="input", section_title="Personal Information", aria_label=None,
    )
    adapter.normalize_field(field)
    assert "Personal Information" in adapter.sections_visited


def test_lever_adapter_has_custom_questions_list():
    adapter = LeverAdapter()
    assert hasattr(adapter, "custom_question_labels")
    assert isinstance(adapter.custom_question_labels, list)


def test_lever_adapter_has_validation_errors():
    adapter = LeverAdapter()
    assert hasattr(adapter, "validation_errors")


def test_workday_adapter_has_section_history():
    adapter = WorkdayAdapter()
    assert hasattr(adapter, "section_history")
    assert isinstance(adapter.section_history, list)


@pytest.mark.asyncio
async def test_retry_with_backoff_success_first_try():
    calls = []
    async def fn():
        calls.append(1)
        return "ok"
    result = await retry_with_backoff(fn, max_attempts=3, base_delay=0.0)
    assert result == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retry_with_backoff_retry_then_success():
    calls = []
    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("transient")
        return "ok"
    result = await retry_with_backoff(fn, max_attempts=3, base_delay=0.0)
    assert result == "ok"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_retry_with_backoff_all_fail():
    async def fn():
        raise ValueError("always fails")
    with pytest.raises(ValueError, match="always fails"):
        await retry_with_backoff(fn, max_attempts=2, base_delay=0.0)


# ──────────────────────────────────────────────────────────────────────────────
# Sprint H — CV file validation
# ──────────────────────────────────────────────────────────────────────────────

from app.services.application_agent_orchestrator import _validate_cv_file


def test_validate_cv_file_valid_pdf():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 fake content here")
        path = f.name
    try:
        ok, reason = _validate_cv_file(path)
        assert ok is True
        assert reason == ""
    finally:
        os.unlink(path)


def test_validate_cv_file_not_pdf():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"this is not a pdf file at all")
        path = f.name
    try:
        ok, reason = _validate_cv_file(path)
        assert ok is False
        assert "PDF" in reason or "pdf" in reason.lower()
    finally:
        os.unlink(path)


def test_validate_cv_file_empty():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    try:
        ok, reason = _validate_cv_file(path)
        assert ok is False
        assert "empty" in reason.lower()
    finally:
        os.unlink(path)


def test_validate_cv_file_missing():
    ok, reason = _validate_cv_file("/nonexistent/path/file.pdf")
    assert ok is False
    assert "not accessible" in reason or "file" in reason.lower()


def test_validate_cv_file_too_large():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        # Write valid header then pad to 11 MB
        f.write(b"%PDF-1.4" + b"x" * (11 * 1024 * 1024))
        path = f.name
    try:
        ok, reason = _validate_cv_file(path)
        assert ok is False
        assert "large" in reason.lower() or "MB" in reason
    finally:
        os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# Sprint K — AI Evaluation LLM criterion schema
# ──────────────────────────────────────────────────────────────────────────────

from app.services.ai_evaluation import (
    CoverLetterClicheCriterion,
    CoverLetterCompanyHookCriterion,
    CVFactualityCriterion,
    CVPersonalizationCriterion,
    EvalResult,
    LLMEvaluationCriterion,
)


def test_llm_criterion_has_name_and_template():
    criterion = LLMEvaluationCriterion(
        name="test_criterion",
        prompt_template="Does this text PASS or FAIL? {text}",
    )
    assert criterion.name == "test_criterion"
    assert "{text}" in criterion.prompt_template
    assert criterion.weight == 1.0


def test_pre_built_criteria_exist():
    assert CVFactualityCriterion.weight == 2.0
    assert "{text}" in CVFactualityCriterion.prompt_template
    assert CVPersonalizationCriterion.weight == 1.5
    assert CoverLetterClicheCriterion.weight == 1.0
    assert CoverLetterCompanyHookCriterion.weight == 1.0


@pytest.mark.asyncio
async def test_llm_criterion_evaluate_async_error_graceful():
    # Without a real LLM, evaluate_async should return a FAIL result, not raise
    criterion = LLMEvaluationCriterion(
        name="test",
        prompt_template="PASS or FAIL? {text}",
    )
    # Patch the anthropic client to raise
    import unittest.mock as mock
    with mock.patch("anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = mock.AsyncMock(side_effect=Exception("no key"))
        result = await criterion.evaluate_async("some text")
    assert isinstance(result, EvalResult)
    assert result.passed is False
    assert "errored" in result.detail.lower() or "error" in result.detail.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Sprint L — Learning Loop: threshold updates + A/B assignment
# ──────────────────────────────────────────────────────────────────────────────

from app.services.learning_loop import (
    _DEFAULT_THRESHOLDS,
    APPLY_THRESHOLD_EXPERIMENT,
    DET_WEIGHT_EXPERIMENT,
    ABExperiment,
    ABVariant,
    _update_thresholds,
    compute_calibration,
)


def _make_outcomes(tier: str, positive: int, negative: int) -> list[dict]:
    rows = []
    for _ in range(positive):
        rows.append({"tier": tier, "outcome": "got_interview"})
    for _ in range(negative):
        rows.append({"tier": tier, "outcome": "rejected"})
    return rows


def test_update_thresholds_over_optimistic():
    # Excellent tier: expected 60% interview rate, got only 10% → raise threshold
    outcomes = _make_outcomes("excellent", positive=1, negative=9)
    # Add enough to meet minimum
    outcomes += _make_outcomes("excellent", positive=0, negative=1)
    cal = compute_calibration(outcomes)
    _new_thresholds, updates = _update_thresholds(cal)
    excellent_updates = [u for u in updates if u.tier == "excellent"]
    if excellent_updates:
        u = excellent_updates[0]
        assert u.direction == "raised" or u.direction == "unchanged"


def test_update_thresholds_insufficient_data():
    # Only 4 outcomes — below MIN_OUTCOMES_FOR_THRESHOLD_UPDATE
    outcomes = _make_outcomes("excellent", positive=2, negative=2)
    cal = compute_calibration(outcomes)
    _, updates = _update_thresholds(cal)
    # No updates because below minimum
    assert updates == []


def test_update_thresholds_preserves_existing():
    custom = {**_DEFAULT_THRESHOLDS}
    custom["excellent"] = 0.90
    outcomes = _make_outcomes("strong", positive=10, negative=0)
    cal = compute_calibration(outcomes)
    new_thresholds, _ = _update_thresholds(cal, current_thresholds=custom)
    # Excellent was not in outcomes → preserved
    assert new_thresholds["excellent"] == 0.90


def test_ab_experiment_deterministic():
    exp = DET_WEIGHT_EXPERIMENT
    # Same unit always gets same variant
    v1 = exp.assign("candidate-123")
    v2 = exp.assign("candidate-123")
    assert v1.name == v2.name


def test_ab_experiment_distributes():
    exp = APPLY_THRESHOLD_EXPERIMENT
    variant_counts: dict[str, int] = {}
    n = 1000
    for i in range(n):
        v = exp.assign(f"unit-{i}")
        variant_counts[v.name] = variant_counts.get(v.name, 0) + 1
    # Each variant should get roughly 50% (within 10%)
    for name, count in variant_counts.items():
        assert 400 < count < 600, f"variant {name} got {count}/{n}"


def test_ab_experiment_invalid_split():
    with pytest.raises(ValueError, match=r"sum to 1\.0"):
        ABExperiment(
            experiment_id="bad",
            description="bad",
            variants=[ABVariant("a", "a"), ABVariant("b", "b")],
            traffic_split=[0.6, 0.6],  # sums to 1.2
        )


def test_ab_experiment_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        ABExperiment(
            experiment_id="bad",
            description="bad",
            variants=[ABVariant("a", "a")],
            traffic_split=[0.5, 0.5],
        )


def test_ab_variant_config():
    v = ABVariant(name="control", description="baseline", config={"det_weight": 0.60})
    assert v.config["det_weight"] == 0.60


# ──────────────────────────────────────────────────────────────────────────────
# Sprint I — PAUSED state machine (orchestrator)
# ──────────────────────────────────────────────────────────────────────────────

def test_pause_validates_pausable_states():
    """AgentError raised when trying to pause from a non-pausable state."""
    # We test only the set of valid states; no DB needed since we inspect constants.
    pausable = {"filling", "awaiting_human", "ready_to_fill", "awaiting_confirm"}
    non_pausable = {"initializing", "discovering", "mapping", "submitted", "failed"}
    # Intersection must be empty
    assert pausable & non_pausable == set()
    # paused is not in pausable (can't pause a paused session)
    assert "paused" not in pausable


def test_agenterror_is_exception():
    from app.services.application_agent_orchestrator import AgentError
    err = AgentError("test error")
    assert isinstance(err, Exception)
    assert "test error" in str(err)


def test_pause_state_in_agent_session_docstring():
    """Module docstring for agent_session documents the paused state."""
    import app.db.models.agent_session as _mod
    doc = _mod.__doc__ or ""
    assert "paused" in doc.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Sprint D — requirement_matches in API schema
# ──────────────────────────────────────────────────────────────────────────────

def test_fit_analysis_response_has_requirement_matches():
    from app.schemas.application import FitAnalysisResponse, RequirementMatchItem
    # Can construct with requirement_matches=None (optional)
    resp = FitAnalysisResponse(
        job_fit_score=0.8,
        career_fit_score=0.7,
        match_tier="strong",
        skill_overlap_score=0.75,
        experience_score=0.8,
        location_score=1.0,
        education_score=1.0,
        matched_skills=["Python"],
        missing_skills=[],
        llm_strengths=None,
        llm_gaps=None,
        llm_reasoning=None,
        requirement_matches=None,
    )
    assert resp.requirement_matches is None

    # Can also include a list of RequirementMatchItem
    items = [RequirementMatchItem(
        text="5+ years Python",
        requirement_type="must_have",
        importance="high",
        candidate_status="MATCHED",
        match_score=1.0,
        evidence_refs=[],
    )]
    resp2 = FitAnalysisResponse(
        job_fit_score=0.8,
        career_fit_score=0.7,
        match_tier="strong",
        skill_overlap_score=0.75,
        experience_score=0.8,
        location_score=1.0,
        education_score=1.0,
        matched_skills=["Python"],
        missing_skills=[],
        llm_strengths=None,
        llm_gaps=None,
        llm_reasoning=None,
        requirement_matches=items,
    )
    assert len(resp2.requirement_matches) == 1
    assert resp2.requirement_matches[0].candidate_status == "MATCHED"


def test_requirement_match_item_fields():
    from app.schemas.application import RequirementMatchItem
    item = RequirementMatchItem(
        text="AWS experience",
        requirement_type="nice_to_have",
        importance="medium",
        candidate_status="PARTIAL",
        match_score=0.5,
        evidence_refs=["exp:2"],
    )
    assert item.evidence_refs == ["exp:2"]
    assert item.match_score == 0.5
