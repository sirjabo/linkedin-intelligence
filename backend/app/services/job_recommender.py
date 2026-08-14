"""Ranks external job postings against a candidate profile.

Uses a TF-IDF cosine similarity approach with field-weighted term vectors:
  - Skill tokens from the candidate profile are extracted and IDF-weighted
  - Job fields are weighted: tech_tags (3×), title (2×), description (1×)
  - IDF is computed across the job corpus at ranking time (no external deps)

Falls back gracefully to 0.0 for empty queries or empty corpora.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass

from app.services.job_sources.base import JobRaw

# Stopwords that add no signal to skill/job matching
_STOPWORDS = frozenset({
    "the", "and", "for", "with", "in", "of", "to", "a", "an", "at", "be",
    "is", "are", "we", "our", "you", "your", "this", "that", "will", "have",
    "has", "or", "on", "it", "as", "not", "by", "from", "was", "were",
})

# Field weights: how much each job field contributes to the term vector
_FIELD_WEIGHTS = {
    "tags": 3.0,
    "title": 2.0,
    "description": 1.0,
}


@dataclass
class ScoredJob:
    job: JobRaw
    score: float  # 0.0 – 1.0
    matched_keywords: list[str]


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9#+.]+", text.lower())
    return [t for t in tokens if len(t) >= 2 and t not in _STOPWORDS]


def _candidate_keywords(profile_data: dict) -> Counter:
    """Build a weighted token counter from the candidate profile.

    Skills are counted with weight 3, summary/experience tokens with weight 1.
    """
    counter: Counter = Counter()

    for skill in profile_data.get("skills") or []:
        if isinstance(skill, str):
            for tok in _tokenize(skill):
                counter[tok] += 3
        elif isinstance(skill, dict):
            name = skill.get("canonical_name") or skill.get("name") or ""
            for tok in _tokenize(name):
                counter[tok] += 3

    for tok in _tokenize(profile_data.get("summary") or ""):
        counter[tok] += 1

    for exp in profile_data.get("experience") or []:
        if isinstance(exp, dict):
            for tok in _tokenize(exp.get("title", "")):
                counter[tok] += 1
            for tok in _tokenize(exp.get("company", "")):
                counter[tok] += 1

    for edu in profile_data.get("education") or []:
        if isinstance(edu, dict):
            for tok in _tokenize(edu.get("field", "")):
                counter[tok] += 1

    return counter


def _job_token_counter(job: JobRaw) -> Counter:
    """Build a field-weighted term counter for a single job."""
    counter: Counter = Counter()
    for tok in _tokenize(job.title):
        counter[tok] += _FIELD_WEIGHTS["title"]
    for tag in job.tech_tags:
        for tok in _tokenize(tag):
            counter[tok] += _FIELD_WEIGHTS["tags"]
    for tok in _tokenize(job.description[:3000]):
        counter[tok] += _FIELD_WEIGHTS["description"]
    return counter


def _compute_idf(jobs: list[JobRaw]) -> dict[str, float]:
    """Compute smoothed IDF for every token in the job corpus.

    idf(t) = log((N + 1) / (df(t) + 1)) + 1
    """
    n = len(jobs)
    if n == 0:
        return {}
    df: Counter = Counter()
    for job in jobs:
        seen = set(_tokenize(job.title))
        seen.update(_tokenize(job.description[:3000]))
        for tag in job.tech_tags:
            seen.update(_tokenize(tag))
        for tok in seen:
            df[tok] += 1
    return {tok: math.log((n + 1) / (count + 1)) + 1.0 for tok, count in df.items()}


def _cosine_score(
    query: Counter,
    doc: Counter,
    idf: dict[str, float],
) -> tuple[float, list[str]]:
    """Cosine similarity between TF-IDF weighted query and document vectors."""
    if not query or not doc:
        return 0.0, []

    def weighted(counter: Counter) -> dict[str, float]:
        return {tok: tf * idf.get(tok, 1.0) for tok, tf in counter.items()}

    q_vec = weighted(query)
    d_vec = weighted(doc)

    common = set(q_vec) & set(d_vec)
    if not common:
        return 0.0, []

    dot = sum(q_vec[t] * d_vec[t] for t in common)
    q_norm = math.sqrt(sum(v * v for v in q_vec.values()))
    d_norm = math.sqrt(sum(v * v for v in d_vec.values()))

    if q_norm == 0 or d_norm == 0:
        return 0.0, []

    score = dot / (q_norm * d_norm)

    # Identify matched surface-level keywords (from original profile skills / tags)
    matched = sorted(
        t for t in common
        if query.get(t, 0) >= 3  # only tokens that were skill-weighted in candidate
    )

    return round(min(score, 1.0), 4), matched


def score_job(job: JobRaw, candidate_counter: Counter, idf: dict[str, float]) -> ScoredJob:
    """Score a single job against the candidate counter using TF-IDF cosine similarity."""
    doc = _job_token_counter(job)
    raw_score, matched = _cosine_score(candidate_counter, doc, idf)
    return ScoredJob(job=job, score=raw_score, matched_keywords=matched)


def rank_jobs(jobs: list[JobRaw], profile_data: dict) -> list[ScoredJob]:
    """Score and sort jobs by TF-IDF cosine similarity to the candidate profile."""
    if not jobs:
        return []

    candidate = _candidate_keywords(profile_data)
    idf = _compute_idf(jobs)
    scored = [score_job(j, candidate, idf) for j in jobs]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
