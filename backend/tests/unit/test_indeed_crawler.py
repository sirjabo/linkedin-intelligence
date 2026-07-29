"""Tests for Indeed HTML parsing (no network)."""

from __future__ import annotations

from app.crawler.jobs.indeed import IndeedCrawler, content_hash


SAMPLE_HTML = """
<html><body>
<div class="job_seen_beacon" data-jk="abc123">
  <h2 class="jobTitle"><a href="/viewjob?jk=abc123">AI Engineer</a></h2>
  <span data-testid="company-name">Mercado Libre</span>
  <div data-testid="text-location">Buenos Aires, AR</div>
  <div data-testid="job-snippet">Python LangChain RAG FastAPI remote</div>
</div>
</body></html>
"""


def test_content_hash_stable() -> None:
    a = content_hash("AI Engineer", "Acme", "Python")
    b = content_hash("AI Engineer", "Acme", "Python")
    c = content_hash("AI Engineer", "Acme", "Java")
    assert a == b
    assert a != c


def test_parse_job_cards() -> None:
    crawler = IndeedCrawler(max_pages=1)
    jobs = crawler.parse(SAMPLE_HTML)
    crawler.close()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "AI Engineer"
    assert jobs[0]["company"] == "Mercado Libre"
    assert jobs[0]["external_id"] == "abc123"
