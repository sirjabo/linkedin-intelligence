"""AI Evaluation framework: structural and semantic quality criteria for LLM outputs.

Provides criterion-based evaluation of agent outputs without requiring
ground-truth labels. Used in smoke tests and offline evaluation runs.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalCriterion:
    name: str
    check: Callable[[Any], tuple[bool, str]]
    weight: float = 1.0  # relative weight in composite score


@dataclass
class EvalResult:
    name: str
    passed: bool
    detail: str
    weight: float = 1.0


@dataclass
class EvalReport:
    results: list[EvalResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def score(self) -> float:
        if not self.results:
            return 0.0
        total_weight = sum(r.weight for r in self.results)
        passed_weight = sum(r.weight for r in self.results if r.passed)
        return passed_weight / total_weight if total_weight else 0.0

    @property
    def passed(self) -> bool:
        return self.score >= 0.8

    def summary(self) -> str:
        lines = [f"Score: {self.score:.0%} ({self.passed_count}/{self.total_count} criteria)"]
        for r in self.results:
            icon = "✓" if r.passed else "✗"
            lines.append(f"  {icon} {r.name}: {r.detail}")
        return "\n".join(lines)


def evaluate(output: Any, criteria: list[EvalCriterion]) -> EvalReport:
    """Run all criteria against output and return an EvalReport."""
    results = []
    for criterion in criteria:
        try:
            passed, detail = criterion.check(output)
        except Exception as exc:
            passed, detail = False, f"criterion raised {type(exc).__name__}: {exc}"
        results.append(EvalResult(name=criterion.name, passed=passed, detail=detail, weight=criterion.weight))
    return EvalReport(results=results)


# ── Reusable criterion factories ──────────────────────────────────────────────

def field_not_empty(field_name: str, min_length: int = 1) -> EvalCriterion:
    def check(output: Any) -> tuple[bool, str]:
        val = getattr(output, field_name, None)
        if val is None:
            return False, f"{field_name} is None"
        if isinstance(val, str) and len(val.strip()) < min_length:
            return False, f"{field_name} is too short ({len(val.strip())} chars, min {min_length})"
        if isinstance(val, list) and len(val) < min_length:
            return False, f"{field_name} list has {len(val)} items, min {min_length}"
        return True, f"{field_name} is present ({len(val) if isinstance(val, (str, list)) else 'set'})"
    return EvalCriterion(name=f"{field_name}_not_empty", check=check)


def field_in_range(field_name: str, lo: float, hi: float) -> EvalCriterion:
    def check(output: Any) -> tuple[bool, str]:
        val = getattr(output, field_name, None)
        if val is None:
            return False, f"{field_name} is None"
        if not (lo <= float(val) <= hi):
            return False, f"{field_name}={val} outside [{lo}, {hi}]"
        return True, f"{field_name}={val:.3f}"
    return EvalCriterion(name=f"{field_name}_in_range", check=check)


def field_contains_keyword(field_name: str, keyword: str) -> EvalCriterion:
    def check(output: Any) -> tuple[bool, str]:
        val = getattr(output, field_name, None)
        if val is None:
            return False, f"{field_name} is None"
        text = " ".join(val).lower() if isinstance(val, list) else str(val).lower()
        found = keyword.lower() in text
        return found, f"'{keyword}' {'found' if found else 'NOT found'} in {field_name}"
    return EvalCriterion(name=f"{field_name}_has_{keyword.replace(' ', '_')}", check=check)


def field_one_of(field_name: str, valid_values: set) -> EvalCriterion:
    def check(output: Any) -> tuple[bool, str]:
        val = getattr(output, field_name, None)
        if val is None:
            return False, f"{field_name} is None"
        found = str(val).lower() in {v.lower() for v in valid_values}
        return found, f"{field_name}='{val}' {'valid' if found else 'invalid, expected one of ' + str(valid_values)}"
    return EvalCriterion(name=f"{field_name}_valid_value", check=check)


def list_items_have_field(list_field: str, item_field: str, min_non_empty: int = 1) -> EvalCriterion:
    def check(output: Any) -> tuple[bool, str]:
        items = getattr(output, list_field, []) or []
        count = sum(1 for item in items if getattr(item, item_field, None))
        ok = count >= min_non_empty
        return ok, f"{count}/{len(items)} {list_field}[*].{item_field} populated"
    return EvalCriterion(name=f"{list_field}_items_{item_field}", check=check)
