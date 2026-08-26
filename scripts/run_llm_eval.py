#!/usr/bin/env python3
"""Run LLM-judged evaluation suite when API keys are present.

Usage:
    python scripts/run_llm_eval.py [--model claude-haiku-4-5-20251001]

Requires ANTHROPIC_API_KEY or OPENROUTER_API_KEY in environment.
Skips gracefully if neither key is set (same behaviour as CI).

Exit codes:
    0 — all criteria passed (score >= 0.80)
    1 — some criteria failed
    2 — no API key available (skipped)
"""
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend package is importable when run from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")


def _check_keys() -> str | None:
    """Return the first available key type, or None."""
    if ANTHROPIC_KEY:
        return "anthropic"
    if OPENROUTER_KEY:
        return "openrouter"
    return None


def _build_client(key_type: str, model: str):
    if key_type == "anthropic":
        import anthropic
        return anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY), model
    # OpenRouter uses the Anthropic SDK with a custom base URL
    import anthropic
    client = anthropic.AsyncAnthropic(
        api_key=OPENROUTER_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
    return client, f"anthropic/{model}"


async def _llm_judge(client, model: str, prompt: str, rubric: str) -> tuple[bool, str]:
    """Ask the LLM to judge output quality against a rubric."""
    resp = await client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": (
                f"You are an evaluator. Rate the following output against this rubric.\n\n"
                f"RUBRIC: {rubric}\n\n"
                f"OUTPUT:\n{prompt}\n\n"
                f"Respond with PASS or FAIL followed by a one-sentence reason."
            ),
        }],
    )
    text = resp.content[0].text.strip()
    passed = text.upper().startswith("PASS")
    return passed, text


async def run_eval(model: str = "claude-haiku-4-5-20251001") -> int:
    key_type = _check_keys()
    if key_type is None:
        print("SKIP: No ANTHROPIC_API_KEY or OPENROUTER_API_KEY set.")
        return 2

    print(f"Running LLM evaluation with key_type={key_type}, model={model}")
    client, resolved_model = _build_client(key_type, model)

    # Import sample outputs to evaluate
    from app.services.form_intelligence import classify_field, map_candidate_to_form, FieldSpec

    results: list[tuple[str, bool, str]] = []

    # ── Criterion 1: classify_field LLM fallback — unknown field ──────────────
    from app.services.form_intelligence import classify_field_llm_with_confidence
    sem, conf = await classify_field_llm_with_confidence(
        label="Desired compensation range",
        field_type="text",
    )
    passed = sem == "salary_expectation"
    detail = f"classified as '{sem}' (confidence={conf:.2f})"
    results.append(("LLM classify: salary label", passed, detail))

    sem2, conf2 = await classify_field_llm_with_confidence(
        label="Tell us about a time you led a team through a difficult technical challenge",
        field_type="textarea",
    )
    passed2 = sem2 in ("custom_essay", "experience_essay")
    detail2 = f"classified as '{sem2}' (confidence={conf2:.2f})"
    results.append(("LLM classify: leadership essay", passed2, detail2))

    sem3, conf3 = await classify_field_llm_with_confidence(
        label="GitHub profile",
        field_type="url",
    )
    passed3 = sem3 == "github_url"
    detail3 = f"classified as '{sem3}' (confidence={conf3:.2f})"
    results.append(("LLM classify: github url", passed3, detail3))

    # ── Criterion 2: LLM judge — form field mapping quality ───────────────────
    fields = [
        FieldSpec(label="Full Name"),
        FieldSpec(label="Email Address"),
        FieldSpec(label="Why are you interested in this role?", field_type="textarea"),
        FieldSpec(label="Years of Python experience", field_type="number"),
    ]
    mapped = map_candidate_to_form(
        fields,
        candidate_name="Maria Garcia",
        candidate_email="maria@example.com",
        candidate_location="Madrid, Spain",
        candidate_salary_min=80000,
        candidate_work_authorization="authorized",
        candidate_availability="2 weeks",
    )
    mapping_summary = "\n".join(
        f"- {m.label}: type={m.semantic_type}, auto_fill={m.auto_fill_value!r}, "
        f"human_required={m.human_required}, skill_target={m.skill_target}"
        for m in mapped
    )
    llm_passed, llm_detail = await _llm_judge(
        client, resolved_model,
        prompt=mapping_summary,
        rubric=(
            "Full Name should be auto-filled with candidate name. "
            "Email should be auto-filled with candidate email. "
            "Essay/why question should require human input. "
            "Years of Python experience should be classified as skill_years "
            "with skill_target='python' and require human input."
        ),
    )
    results.append(("LLM judge: field mapping quality", llm_passed, llm_detail))

    # ── Criterion 3: LLM classify unknown field resolves correctly ────────────
    sem4, conf4 = await classify_field_llm_with_confidence(
        label="Preferred start date",
        field_type="date",
    )
    passed4 = sem4 in ("start_date", "availability")
    detail4 = f"classified as '{sem4}' (confidence={conf4:.2f})"
    results.append(("LLM classify: start date field", passed4, detail4))

    # ── Print results ─────────────────────────────────────────────────────────
    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)
    score = passed_count / total_count if total_count else 0.0

    print(f"\n{'='*60}")
    print(f"LLM Evaluation Results — {passed_count}/{total_count} passed ({score:.0%})")
    print(f"{'='*60}")
    for name, passed, detail in results:
        icon = "✓" if passed else "✗"
        status = "PASS" if passed else "FAIL"
        print(f"  {icon} [{status}] {name}")
        print(f"      {detail}")
    print()

    if score >= 0.80:
        print("OVERALL: PASS")
        return 0
    else:
        print(f"OVERALL: FAIL (score {score:.0%} < 80%)")
        return 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run LLM evaluation suite")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001", help="Model to use")
    args = parser.parse_args()
    sys.exit(asyncio.run(run_eval(model=args.model)))
