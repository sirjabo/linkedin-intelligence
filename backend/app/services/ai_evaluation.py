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


# ── Sprint K: LLM Judge criteria ──────────────────────────────────────────────

@dataclass
class LLMEvaluationCriterion:
    """Criterion evaluated by a language model rather than deterministically.

    The `prompt_template` receives the output text via {text} and must instruct
    the LLM to reply with a single line: PASS <reason> or FAIL <reason>.
    """
    name: str
    prompt_template: str
    weight: float = 1.0
    model: str = "claude-haiku-4-5-20251001"

    async def evaluate_async(self, text: str) -> EvalResult:
        """Call the LLM and parse PASS/FAIL from the response."""
        try:
            import anthropic

            from app.core.config import settings

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            prompt = self.prompt_template.format(text=text[:4000])
            resp = await client.messages.create(
                model=self.model,
                max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            block = resp.content[0]
            answer = (getattr(block, "text", "") or "").strip()
            passed = answer.upper().startswith("PASS")
            detail = answer[5:].strip() if len(answer) > 5 else answer
            return EvalResult(name=self.name, passed=passed, detail=detail, weight=self.weight)
        except Exception as exc:
            return EvalResult(
                name=self.name, passed=False,
                detail=f"LLM criterion errored: {exc}", weight=self.weight,
            )


# ── Pre-built LLM criteria ────────────────────────────────────────────────────

CVFactualityCriterion = LLMEvaluationCriterion(
    name="cv_factuality",
    weight=2.0,
    prompt_template=(
        "You are a factuality auditor. Review the following CV text and determine "
        "whether it contains any invented metrics, dates, or accomplishments that "
        "a candidate could NOT plausibly defend in an interview.\n\n"
        "CV text:\n{text}\n\n"
        "Reply with a single line: PASS if the CV appears factual, "
        "FAIL if it contains suspicious or invented claims. Follow with a brief reason."
    ),
)

CVPersonalizationCriterion = LLMEvaluationCriterion(
    name="cv_personalization",
    weight=1.5,
    prompt_template=(
        "You are evaluating whether a CV has been meaningfully personalized for a job. "
        "A generic CV that reads the same for any job FAILS. A CV with role-specific "
        "language, prioritized relevant experience, and adapted bullet points PASSES.\n\n"
        "CV text:\n{text}\n\n"
        "Reply with a single line: PASS or FAIL, followed by a brief reason."
    ),
)

CoverLetterClicheCriterion = LLMEvaluationCriterion(
    name="cover_letter_no_cliches",
    weight=1.0,
    prompt_template=(
        "You are reviewing a cover letter for overused clichés. "
        "Phrases like 'I am passionate about', 'team player', 'hard worker', "
        "'dynamic environment', 'results-driven' are red flags.\n\n"
        "Cover letter:\n{text}\n\n"
        "Reply with: PASS if the letter is specific and cliché-free, "
        "FAIL if it contains 2 or more clichés. Add a brief reason."
    ),
)

CoverLetterCompanyHookCriterion = LLMEvaluationCriterion(
    name="cover_letter_company_hook",
    weight=1.0,
    prompt_template=(
        "Does the following cover letter demonstrate genuine knowledge of the "
        "company (mentions their product, mission, recent news, or culture "
        "in a specific way)? Generic 'I admire your company' does not count.\n\n"
        "Cover letter:\n{text}\n\n"
        "Reply with: PASS if company-specific knowledge is evident, FAIL otherwise. "
        "Include a brief reason."
    ),
)


async def evaluate_llm(
    text: str,
    criteria: list[LLMEvaluationCriterion],
) -> EvalReport:
    """Run all LLM criteria concurrently against text and return an EvalReport."""
    import asyncio

    results = await asyncio.gather(*(c.evaluate_async(text) for c in criteria))
    return EvalReport(results=list(results))
