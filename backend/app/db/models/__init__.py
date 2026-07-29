"""SQLAlchemy models package."""

from app.db.models.cv_analysis import CVAnalysis
from app.db.models.job_posting import JobPosting
from app.db.models.skill_demand import SkillDemand
from app.db.models.skills_catalog import SkillsCatalog
from app.db.models.user import User

__all__ = [
    "User",
    "JobPosting",
    "SkillsCatalog",
    "SkillDemand",
    "CVAnalysis",
]
