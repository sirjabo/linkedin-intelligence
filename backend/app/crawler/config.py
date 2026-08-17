"""Crawler configuration — docs/08-CRAWLERS.md."""

CRAWLER_SCHEDULE = {
    "indeed": {"cron": "0 */6 * * *", "enabled": True},
    "greenhouse": {"cron": "0 8 * * *", "enabled": True},
    "lever": {"cron": "0 8 * * *", "enabled": True},
}

RATE_LIMITS = {
    "indeed": 0.2,  # 1 req / 5s
    "greenhouse": 1.0,
    "lever": 1.0,
}

INDEED_DOMAINS = {
    "AR": "https://ar.indeed.com",
    "MX": "https://mx.indeed.com",
    "ES": "https://es.indeed.com",
}

ROLES_TO_CRAWL = [
    ("AI Engineer", "Argentina", "AR", "ai_engineer"),
    ("AI Engineer", "Mexico", "MX", "ai_engineer"),
    ("AI Engineer", "Spain", "ES", "ai_engineer"),
    ("Analytics Engineer", "Argentina", "AR", "analytics_engineer"),
    ("Analytics Engineer", "Mexico", "MX", "analytics_engineer"),
    ("Analytics Engineer", "Spain", "ES", "analytics_engineer"),
    ("Data Engineer", "Argentina", "AR", "data_engineer"),
    ("Data Engineer", "Mexico", "MX", "data_engineer"),
    ("Data Engineer", "Spain", "ES", "data_engineer"),
]

USER_AGENT = (
    "LinkedInIntelligenceBot/0.1 (+https://github.com/sirjabo/linkedin-intelligence; research)"
)
