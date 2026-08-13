"""ClaimValidator: verify generated text claims against candidate evidence records.

Deterministic, no LLM calls — uses keyword overlap for MVP.
"""
import re
from dataclasses import dataclass, field


# Patterns that signal a factual claim worth verifying
_CLAIM_PATTERNS = [
    re.compile(r"\d+\s*(%|years?|months?|\+|\bx\b)", re.IGNORECASE),
    re.compile(r"\$[\d,]+|\d+[kKmM]\b"),
    re.compile(r"\b(reduced|increased|improved|saved|built|led|managed|delivered|launched)\b", re.IGNORECASE),
]


@dataclass
class ValidationResult:
    verified_claims: list[str] = field(default_factory=list)
    unverified_claims: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.unverified_claims) == 0

    def to_dict(self) -> dict:
        return {
            "verified_claims": self.verified_claims,
            "unverified_claims": self.unverified_claims,
            "is_clean": self.is_clean,
        }


def _extract_claim_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if any(p.search(s) for p in _CLAIM_PATTERNS)]


def _keywords(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"\b\w{3,}\b", text)}


def _has_evidence_support(claim: str, evidence_records: list) -> bool:
    if not evidence_records:
        return False
    claim_words = _keywords(claim)
    for record in evidence_records:
        evidence_text = getattr(record, "claim", "") or ""
        source_text = getattr(record, "source_text", "") or ""
        evidence_words = _keywords(evidence_text + " " + source_text)
        overlap = claim_words & evidence_words
        # Require at least 3 meaningful keyword matches
        if len(overlap) >= 3:
            return True
    return False


def validate_claims(text: str, evidence_records: list) -> ValidationResult:
    """Check generated text claims against candidate evidence records.

    Returns categorized claims. Callers decide whether to reject unverified content.
    """
    claims = _extract_claim_sentences(text)
    result = ValidationResult()

    for claim in claims:
        if _has_evidence_support(claim, evidence_records):
            result.verified_claims.append(claim)
        else:
            result.unverified_claims.append(claim)

    return result
