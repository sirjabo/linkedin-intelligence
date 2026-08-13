"""Ranks external job postings against a candidate profile (deterministic, no LLM)."""
from dataclasses import dataclass

from app.services.job_sources.base import JobRaw


@dataclass
class ScoredJob:
    job: JobRaw
    score: float  # 0.0 – 1.0
    matched_keywords: list[str]


def _tokenize(text: str) -> set[str]:
    import re
    tokens = re.findall(r"[a-z0-9#+.]+", text.lower())
    return {t for t in tokens if len(t) >= 2}


def _candidate_keywords(profile_data: dict) -> set[str]:
    """Extract meaningful keywords from a serialized CandidateProfile."""
    tokens: set[str] = set()

    # Skills
    for skill in profile_data.get("skills") or []:
        if isinstance(skill, str):
            tokens |= _tokenize(skill)
        elif isinstance(skill, dict):
            tokens |= _tokenize(skill.get("name", ""))

    # Summary
    tokens |= _tokenize(profile_data.get("summary") or "")

    # Experience titles / companies
    for exp in profile_data.get("experience") or []:
        if isinstance(exp, dict):
            tokens |= _tokenize(exp.get("title", ""))
            tokens |= _tokenize(exp.get("company", ""))

    # Education
    for edu in profile_data.get("education") or []:
        if isinstance(edu, dict):
            tokens |= _tokenize(edu.get("field", ""))
            tokens |= _tokenize(edu.get("degree", ""))

    # Remove very common stopwords
    stopwords = {"the", "and", "for", "with", "in", "of", "to", "a", "an", "at", "be"}
    return tokens - stopwords


def score_job(job: JobRaw, candidate_keywords: set[str]) -> ScoredJob:
    """Score a single job against a set of candidate keywords."""
    job_text = " ".join([
        job.title,
        job.description[:2000],  # cap to avoid huge docs
        " ".join(job.tech_tags),
    ])
    job_tokens = _tokenize(job_text)
    job_tokens |= {t.lower() for t in job.tech_tags}

    if not candidate_keywords:
        return ScoredJob(job=job, score=0.0, matched_keywords=[])

    matched = candidate_keywords & job_tokens
    # Jaccard-like but biased toward candidate — recall over precision
    score = len(matched) / len(candidate_keywords)
    score = min(score, 1.0)

    return ScoredJob(job=job, score=round(score, 4), matched_keywords=sorted(matched))


def rank_jobs(jobs: list[JobRaw], profile_data: dict) -> list[ScoredJob]:
    """Score and sort jobs by relevance to the candidate profile."""
    keywords = _candidate_keywords(profile_data)
    scored = [score_job(j, keywords) for j in jobs]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
