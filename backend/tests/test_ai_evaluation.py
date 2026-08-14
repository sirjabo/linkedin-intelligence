"""Unit tests for the AI Evaluation framework (no LLM calls)."""
from dataclasses import dataclass
from app.services.ai_evaluation import (
    evaluate,
    EvalCriterion,
    EvalReport,
    field_not_empty,
    field_in_range,
    field_contains_keyword,
    field_one_of,
    list_items_have_field,
)


@dataclass
class _Sample:
    title: str | None = None
    score: float | None = None
    tags: list | None = None
    items: list | None = None


@dataclass
class _Item:
    name: str | None = None


# ── evaluate() ────────────────────────────────────────────────────────────────

def test_evaluate_all_pass():
    obj = _Sample(title="hello", score=0.75, tags=["a", "b"])
    criteria = [field_not_empty("title"), field_in_range("score", 0.0, 1.0)]
    report = evaluate(obj, criteria)
    assert report.passed_count == 2
    assert report.score == 1.0
    assert report.passed


def test_evaluate_some_fail():
    obj = _Sample(title=None, score=0.5)
    criteria = [field_not_empty("title"), field_in_range("score", 0.0, 1.0)]
    report = evaluate(obj, criteria)
    assert report.passed_count == 1
    assert report.score == 0.5
    assert not report.passed  # < 0.8 threshold


def test_evaluate_empty_criteria():
    report = evaluate(_Sample(), [])
    assert report.score == 0.0
    assert report.total_count == 0


def test_evaluate_criterion_exception_is_failure():
    def bad_check(_):
        raise ValueError("oops")

    criteria = [EvalCriterion(name="bad", check=bad_check)]
    report = evaluate(_Sample(), criteria)
    assert report.passed_count == 0
    assert "ValueError" in report.results[0].detail


# ── field_not_empty ────────────────────────────────────────────────────────────

def test_field_not_empty_passes():
    obj = _Sample(title="Senior Engineer")
    c = field_not_empty("title", min_length=5)
    passed, _ = c.check(obj)
    assert passed


def test_field_not_empty_fails_none():
    obj = _Sample(title=None)
    c = field_not_empty("title")
    passed, detail = c.check(obj)
    assert not passed
    assert "None" in detail


def test_field_not_empty_fails_short_string():
    obj = _Sample(title="ab")
    c = field_not_empty("title", min_length=5)
    passed, _ = c.check(obj)
    assert not passed


def test_field_not_empty_list():
    obj = _Sample(tags=["python", "sql"])
    passed, _ = field_not_empty("tags", min_length=2).check(obj)
    assert passed

    obj2 = _Sample(tags=[])
    passed2, _ = field_not_empty("tags", min_length=1).check(obj2)
    assert not passed2


# ── field_in_range ────────────────────────────────────────────────────────────

def test_field_in_range_passes():
    obj = _Sample(score=0.75)
    passed, _ = field_in_range("score", 0.0, 1.0).check(obj)
    assert passed


def test_field_in_range_fails_above():
    obj = _Sample(score=1.5)
    passed, _ = field_in_range("score", 0.0, 1.0).check(obj)
    assert not passed


def test_field_in_range_fails_none():
    obj = _Sample(score=None)
    passed, _ = field_in_range("score", 0.0, 1.0).check(obj)
    assert not passed


# ── field_contains_keyword ────────────────────────────────────────────────────

def test_field_contains_keyword_string():
    obj = _Sample(title="Senior Python Engineer")
    passed, _ = field_contains_keyword("title", "python").check(obj)
    assert passed


def test_field_contains_keyword_list():
    obj = _Sample(tags=["python", "sql", "dbt"])
    passed, _ = field_contains_keyword("tags", "dbt").check(obj)
    assert passed


def test_field_contains_keyword_missing():
    obj = _Sample(title="Frontend Developer")
    passed, _ = field_contains_keyword("title", "python").check(obj)
    assert not passed


# ── field_one_of ──────────────────────────────────────────────────────────────

def test_field_one_of_passes():
    obj = _Sample(title="senior")
    passed, _ = field_one_of("title", {"senior", "staff", "lead"}).check(obj)
    assert passed


def test_field_one_of_fails():
    obj = _Sample(title="intern")
    passed, _ = field_one_of("title", {"senior", "staff"}).check(obj)
    assert not passed


# ── list_items_have_field ─────────────────────────────────────────────────────

def test_list_items_have_field_passes():
    obj = _Sample(items=[_Item(name="alice"), _Item(name="bob")])
    passed, _ = list_items_have_field("items", "name", min_non_empty=2).check(obj)
    assert passed


def test_list_items_have_field_fails():
    obj = _Sample(items=[_Item(name=None), _Item(name=None)])
    passed, _ = list_items_have_field("items", "name", min_non_empty=1).check(obj)
    assert not passed


# ── EvalReport ────────────────────────────────────────────────────────────────

def test_eval_report_score_weighted():
    from app.services.ai_evaluation import EvalResult
    report = EvalReport(results=[
        EvalResult(name="a", passed=True, detail="ok", weight=2.0),
        EvalResult(name="b", passed=False, detail="fail", weight=1.0),
    ])
    # 2/(2+1) ≈ 0.667
    assert abs(report.score - 2 / 3) < 0.01
    assert not report.passed  # < 0.8


def test_eval_report_summary_contains_criteria():
    from app.services.ai_evaluation import EvalResult
    report = EvalReport(results=[
        EvalResult(name="title_check", passed=True, detail="present"),
        EvalResult(name="score_check", passed=False, detail="too low"),
    ])
    summary = report.summary()
    assert "title_check" in summary
    assert "score_check" in summary
