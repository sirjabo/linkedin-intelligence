"""AI evaluation suite — LLM-judge tests over synthetic candidate outputs.

All candidate data is entirely fictional. No real personal information is used.
Tests are marked to skip when ANTHROPIC_API_KEY is not set.
Uses claude-haiku-4-5-20251001 for fast, inexpensive evaluation.
"""
import os
import pytest

from app.services.ai_evaluation import (
    CVFactualityCriterion,
    CVPersonalizationCriterion,
    CoverLetterClicheCriterion,
    CoverLetterCompanyHookCriterion,
    EvalReport,
    cv_differentiation_score,
    evaluate_llm,
)

# Skip all LLM tests unless an API key is present
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping LLM evaluation tests",
)

# ── Synthetic candidate data (all fictional) ───────────────────────────────────

_CV_FACTUAL_GOOD = """\
Software Engineer at Acme Corp (2019–2023).
Reduced CI pipeline duration by 40% by migrating from Jenkins to GitHub Actions.
Built a distributed caching layer using Redis that decreased API latency from 120ms to 45ms.
Led migration of a PostgreSQL 9.6 cluster to PostgreSQL 14 with zero downtime.
"""

_CV_FACTUAL_BAD = """\
Legendary Software Engineer with 30 years of Python experience (Python was created in 1991,
so this is plausible for an expert who started in 1994). Singlehandedly grew company revenue
from $0 to $50 billion in 18 months. Invented a novel compression algorithm that outperforms
all known methods by 10,000×. Managed a team of 500 engineers as a mid-level IC.
"""

_CV_PERSONALIZED_GOOD = """\
Senior Backend Engineer with 5 years in fintech, specialising in Python/FastAPI payment systems.
Experience directly relevant to the Payment Processing Engineer role at FinPay Inc:
- Built high-throughput payment ingestion pipelines handling 500K transactions/day
- Implemented PCI-DSS compliant card tokenisation using Stripe and Braintree APIs
- Reduced payment failure rates from 3.2% to 0.8% via retry logic improvements
"""

_CV_GENERIC = """\
Experienced software engineer with strong communication skills and a passion for technology.
Highly motivated self-starter with excellent problem-solving abilities.
Team player with leadership experience. Eager to contribute to a dynamic and fast-paced environment.
"""

_COVER_LETTER_NO_CLICHES = """\
I'm applying for the Machine Learning Engineer position at DataSphere.

In my last role at CloudCo, I reduced model inference latency by 60% by switching from
a synchronous REST gateway to an async gRPC service. The same architecture change let us
serve 3× more concurrent requests with identical GPU budget.

I saw that DataSphere's inference platform (written up in your 2024 NeurIPS paper) uses
a similar multi-model serving approach — I'd be excited to push that work further.
"""

_COVER_LETTER_WITH_CLICHES = """\
I am passionate about technology and eager to bring my hard-working, results-driven,
team-player attitude to your dynamic environment. I am a quick learner who thrives
in fast-paced settings. I believe I would be a great cultural fit for your innovative team.
I am excited to leverage my synergies and hit the ground running at your world-class company.
"""

_COVER_LETTER_COMPANY_HOOK = """\
The reason I'm excited about CircleDB specifically is your recent open-source release of
`vector-bench` — I spent a weekend running it against our internal embedding service and
found the latency numbers match our production data almost exactly. That level of rigour
in your benchmarking methodology is exactly what I look for in a team to join.
"""

_COVER_LETTER_GENERIC = """\
I am writing to express my interest in a position at your company.
I admire your company and believe my skills would be a great fit.
Please find my resume attached. I look forward to hearing from you.
"""


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_cv_factuality_passes_on_realistic_cv():
    report = await evaluate_llm(_CV_FACTUAL_GOOD, [CVFactualityCriterion])
    assert isinstance(report, EvalReport)
    assert report.results[0].passed, f"Expected PASS, got: {report.results[0].detail}"


async def test_cv_factuality_fails_on_invented_claims():
    report = await evaluate_llm(_CV_FACTUAL_BAD, [CVFactualityCriterion])
    assert isinstance(report, EvalReport)
    assert not report.results[0].passed, f"Expected FAIL, got: {report.results[0].detail}"


async def test_cv_personalization_passes_on_targeted_cv():
    report = await evaluate_llm(_CV_PERSONALIZED_GOOD, [CVPersonalizationCriterion])
    assert isinstance(report, EvalReport)
    assert report.results[0].passed, f"Expected PASS, got: {report.results[0].detail}"


async def test_cv_personalization_fails_on_generic_cv():
    report = await evaluate_llm(_CV_GENERIC, [CVPersonalizationCriterion])
    assert isinstance(report, EvalReport)
    assert not report.results[0].passed, f"Expected FAIL, got: {report.results[0].detail}"


async def test_cover_letter_no_cliches_passes():
    report = await evaluate_llm(_COVER_LETTER_NO_CLICHES, [CoverLetterClicheCriterion])
    assert isinstance(report, EvalReport)
    assert report.results[0].passed, f"Expected PASS, got: {report.results[0].detail}"


async def test_cover_letter_cliches_fail():
    report = await evaluate_llm(_COVER_LETTER_WITH_CLICHES, [CoverLetterClicheCriterion])
    assert isinstance(report, EvalReport)
    assert not report.results[0].passed, f"Expected FAIL, got: {report.results[0].detail}"


async def test_cover_letter_company_hook_passes():
    report = await evaluate_llm(_COVER_LETTER_COMPANY_HOOK, [CoverLetterCompanyHookCriterion])
    assert isinstance(report, EvalReport)
    assert report.results[0].passed, f"Expected PASS, got: {report.results[0].detail}"


async def test_cover_letter_generic_fails_company_hook():
    report = await evaluate_llm(_COVER_LETTER_GENERIC, [CoverLetterCompanyHookCriterion])
    assert isinstance(report, EvalReport)
    assert not report.results[0].passed, f"Expected FAIL, got: {report.results[0].detail}"


async def test_multiple_criteria_combined():
    """Run all four criteria on the best synthetic CV; expect ≥ 3 to pass."""
    all_criteria = [
        CVFactualityCriterion,
        CVPersonalizationCriterion,
        CoverLetterClicheCriterion,
        CoverLetterCompanyHookCriterion,
    ]
    combined_text = _CV_FACTUAL_GOOD + "\n\n" + _COVER_LETTER_NO_CLICHES + "\n\n" + _COVER_LETTER_COMPANY_HOOK
    report = await evaluate_llm(combined_text, all_criteria)
    assert report.passed_count >= 3, f"Expected ≥3 passes but got {report.passed_count}: {report.summary()}"


# ── Deterministic tests (no API key needed) ────────────────────────────────────

@pytest.mark.filterwarnings("ignore")
def test_cv_differentiation_score_no_shared_bullets():
    class FakeBullet:
        def __init__(self, text):
            self.adapted = text

    class FakeExp:
        def __init__(self, bullets):
            self.bullets_adapted = [FakeBullet(b) for b in bullets]

    class FakeCV:
        def __init__(self, bullets):
            self.experience_personalized = [FakeExp(bullets)]

    cv_a = FakeCV(["Built payment API", "Reduced latency"])
    cv_b = FakeCV(["Designed data pipeline", "Improved throughput"])
    score = cv_differentiation_score([cv_a, cv_b])
    assert score == 1.0  # no shared bullets


def test_cv_differentiation_score_identical_bullets():
    class FakeBullet:
        def __init__(self, text):
            self.adapted = text

    class FakeExp:
        def __init__(self, bullets):
            self.bullets_adapted = [FakeBullet(b) for b in bullets]

    class FakeCV:
        def __init__(self, bullets):
            self.experience_personalized = [FakeExp(bullets)]

    bullets = ["Led cross-functional team to deliver platform migration"]
    cv_a = FakeCV(bullets)
    cv_b = FakeCV(bullets)
    score = cv_differentiation_score([cv_a, cv_b])
    assert score == 0.0  # completely identical


def test_cv_differentiation_single_cv_returns_one():
    class FakeCV:
        experience_personalized = []

    assert cv_differentiation_score([FakeCV()]) == 1.0
