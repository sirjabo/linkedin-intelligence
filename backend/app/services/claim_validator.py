"""ClaimValidator: verify generated text claims against candidate evidence records.

Deterministic, no LLM calls — uses keyword overlap and pattern matching.
Produces SUPPORTED / PLAUSIBLE / UNSUPPORTED classifications.
"""
import re
from dataclasses import dataclass, field
from typing import Literal

VerificationStatus = Literal["SUPPORTED", "PLAUSIBLE", "UNSUPPORTED"]

# Patterns that signal a factual claim worth verifying
_CLAIM_PATTERNS = [
    re.compile(r"\d+\s*(%|years?|months?|\+|\bx\b)", re.IGNORECASE),
    re.compile(r"\$[\d,]+|\d+[kKmM]\b"),
    re.compile(r"\b(reduced|increased|improved|saved|built|led|managed|delivered|launched)\b", re.IGNORECASE),
]


@dataclass
class ClaimVerification:
    claim: str
    status: VerificationStatus
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    verified_claims: list[str] = field(default_factory=list)       # SUPPORTED (backwards compat)
    unverified_claims: list[str] = field(default_factory=list)     # UNSUPPORTED (backwards compat)
    plausible_claims: list[str] = field(default_factory=list)      # PLAUSIBLE (new)
    detailed: list[ClaimVerification] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.unverified_claims) == 0

    def to_dict(self) -> dict:
        return {
            "verified_claims": self.verified_claims,
            "plausible_claims": self.plausible_claims,
            "unverified_claims": self.unverified_claims,
            "is_clean": self.is_clean,
        }


def _extract_claim_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if any(p.search(s) for p in _CLAIM_PATTERNS)]


def _keywords(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"\b\w{3,}\b", text)}


def _classify_claim(claim: str, evidence_records: list) -> ClaimVerification:
    """Classify a claim as SUPPORTED, PLAUSIBLE, or UNSUPPORTED.

    SUPPORTED  : ≥ 3 keyword matches across evidence records
    PLAUSIBLE  : 1–2 keyword matches (consistent but not strongly confirmed)
    UNSUPPORTED: 0 keyword matches or no evidence records
    """
    if not evidence_records:
        return ClaimVerification(claim=claim, status="UNSUPPORTED")

    claim_words = _keywords(claim)
    best_overlap: list[str] = []

    for record in evidence_records:
        evidence_text = getattr(record, "claim", "") or ""
        source_text = getattr(record, "source_text", "") or ""
        evidence_words = _keywords(evidence_text + " " + source_text)
        overlap = list(claim_words & evidence_words)
        if len(overlap) > len(best_overlap):
            best_overlap = overlap

    n = len(best_overlap)
    if n >= 3:
        status: VerificationStatus = "SUPPORTED"
    elif n >= 1:
        status = "PLAUSIBLE"
    else:
        status = "UNSUPPORTED"

    return ClaimVerification(claim=claim, status=status, matched_keywords=best_overlap)


def validate_claims(text: str, evidence_records: list) -> ValidationResult:
    """Check generated text claims against candidate evidence records.

    Returns categorized claims with SUPPORTED/PLAUSIBLE/UNSUPPORTED classification.
    Callers decide whether to reject unverified content.
    """
    claims = _extract_claim_sentences(text)
    result = ValidationResult()

    for claim in claims:
        verification = _classify_claim(claim, evidence_records)
        result.detailed.append(verification)

        if verification.status == "SUPPORTED":
            result.verified_claims.append(claim)
        elif verification.status == "PLAUSIBLE":
            result.plausible_claims.append(claim)
        else:
            result.unverified_claims.append(claim)

    return result
