"""Tests for P3 Phase 17: TF-IDF cosine similarity job recommender.

Verifies:
  - _candidate_keywords() returns Counter with skill-weighted tokens
  - _compute_idf() assigns higher IDF to rare terms
  - score_job() returns 0.0 when no overlap; > 0 when overlap exists
  - rank_jobs() orders by descending score
  - High-overlap job beats low-overlap job in ranking
"""


from app.services.job_recommender import (
    _candidate_keywords,
    _compute_idf,
    rank_jobs,
    score_job,
)
from app.services.job_sources.base import JobRaw


def _job(external_id: str, title: str, desc: str, tags: list[str]) -> JobRaw:
    return JobRaw(
        external_id=external_id,
        title=title,
        company="TestCo",
        location="Remote",
        remote_type="remote",
        url=f"https://example.com/{external_id}",
        description=desc,
        tech_tags=tags,
    )


# ── _candidate_keywords ───────────────────────────────────────────────────────

def test_candidate_keywords_returns_counter():
    profile = {"skills": ["python", "sql"], "summary": "data engineer", "experience": [], "education": []}
    result = _candidate_keywords(profile)
    assert isinstance(result, dict)


def test_candidate_keywords_skill_tokens_present():
    profile = {"skills": [{"canonical_name": "Apache Kafka"}], "summary": "", "experience": [], "education": []}
    result = _candidate_keywords(profile)
    assert "apache" in result
    assert "kafka" in result


def test_candidate_keywords_skills_outweigh_summary():
    profile = {
        "skills": ["python"],
        "summary": "python developer",
        "experience": [],
        "education": [],
    }
    kw = _candidate_keywords(profile)
    # "python" appears in skills (weight 3) + summary (weight 1) = 4
    # "developer" appears only in summary (weight 1)
    assert kw["python"] > kw["developer"]


# ── _compute_idf ─────────────────────────────────────────────────────────────

def test_compute_idf_rare_term_higher():
    """Rare terms should have higher IDF than common ones."""
    job_a = _job("a", "Python Developer", "python web api", ["python"])
    job_b = _job("b", "Java Developer", "java web api", ["java"])
    idf = _compute_idf([job_a, job_b])
    # "web" and "api" appear in both → lower IDF
    # "python" appears only in job_a → higher IDF
    assert idf.get("python", 0) > idf.get("web", 0)


def test_compute_idf_empty_corpus():
    idf = _compute_idf([])
    assert idf == {}


def test_compute_idf_single_job_all_same():
    """All terms in a single-job corpus share the same IDF = log(2/2)+1 = 1.0."""
    job = _job("a", "Python Engineer", "python stuff", ["python"])
    idf = _compute_idf([job])
    for val in idf.values():
        assert abs(val - 1.0) < 1e-9


# ── score_job ─────────────────────────────────────────────────────────────────

def test_score_job_zero_on_no_overlap():
    job = _job("a", "Java Backend", "java spring boot", ["java", "spring"])
    idf = _compute_idf([job])
    candidate: dict[str, float] = {"python": 3, "sql": 3}
    result = score_job(job, candidate, idf)
    assert result.score == 0.0
    assert result.matched_keywords == []


def test_score_job_positive_on_overlap():
    job = _job("a", "Python Engineer", "python sql work", ["python", "sql"])
    idf = _compute_idf([job])
    candidate: dict[str, float] = {"python": 3, "sql": 3}
    result = score_job(job, candidate, idf)
    assert result.score > 0.0
    assert "python" in result.matched_keywords or "sql" in result.matched_keywords


def test_score_job_empty_candidate():
    job = _job("a", "Python Engineer", "python work", ["python"])
    idf = _compute_idf([job])
    result = score_job(job, {}, idf)
    assert result.score == 0.0


def test_score_job_within_bounds():
    job = _job("a", "ML Engineer", "python pytorch ml", ["python", "pytorch"])
    idf = _compute_idf([job])
    candidate: dict[str, float] = {"python": 3, "pytorch": 3, "ml": 3}
    result = score_job(job, candidate, idf)
    assert 0.0 <= result.score <= 1.0


# ── rank_jobs ─────────────────────────────────────────────────────────────────

def test_rank_jobs_sorted_descending():
    jobs = [
        _job("a", "Java Dev", "java spring", ["java"]),
        _job("b", "Python Data Engineer", "python sql dbt", ["python", "sql", "dbt"]),
        _job("c", "Python Dev", "python work", ["python"]),
    ]
    profile = {"skills": ["Python", "SQL", "dbt"], "summary": "", "experience": [], "education": []}
    ranked = rank_jobs(jobs, profile)
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_jobs_best_match_first():
    jobs = [
        _job("a", "Java Backend Engineer", "java spring boot", ["java"]),
        _job("b", "Data Engineer Python SQL", "python sql dbt data pipelines", ["python", "sql", "dbt"]),
    ]
    profile = {"skills": ["Python", "SQL", "dbt"], "summary": "data engineer", "experience": [], "education": []}
    ranked = rank_jobs(jobs, profile)
    assert ranked[0].job.external_id == "b"


def test_rank_jobs_empty_returns_empty():
    ranked = rank_jobs([], {"skills": ["python"]})
    assert ranked == []


def test_rank_jobs_empty_profile_all_zero():
    jobs = [_job("a", "Python Dev", "python work", ["python"])]
    ranked = rank_jobs(jobs, {})
    assert len(ranked) == 1
    assert ranked[0].score == 0.0


def test_rank_jobs_idf_boosts_rare_skills():
    """A job matching a rare skill should outscore a job matching only common words."""
    jobs = [
        _job("common", "Data Engineer", "python data pipelines work build", ["python"]),
        _job("rare", "Flink Engineer", "flink streaming kafka data", ["flink", "kafka"]),
    ]
    profile = {
        "skills": ["Flink", "Kafka"],
        "summary": "data engineer",
        "experience": [],
        "education": [],
    }
    ranked = rank_jobs(jobs, profile)
    # "flink" and "kafka" appear only in rare job → rare job should win
    assert ranked[0].job.external_id == "rare"
