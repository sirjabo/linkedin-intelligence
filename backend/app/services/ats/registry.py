"""ATSRegistry: detect which ATS a URL belongs to and return the right adapter."""
from app.services.ats.adapter import ATSAdapter
from app.services.ats.ashby import AshbyAdapter
from app.services.ats.generic import GenericFormAgent
from app.services.ats.greenhouse import GreenhouseAdapter
from app.services.ats.lever import LeverAdapter
from app.services.ats.smart_recruiters import SmartRecruitersAdapter
from app.services.ats.workday import WorkdayAdapter

# Ordered: more specific patterns first
_ADAPTERS: list[ATSAdapter] = [
    GreenhouseAdapter(),
    LeverAdapter(),
    AshbyAdapter(),
    WorkdayAdapter(),
    SmartRecruitersAdapter(),
]

_GENERIC = GenericFormAgent()


def detect_ats(url: str):
    """Return the ATS adapter for the given URL, or GenericFormAgent if none match."""
    for adapter in _ADAPTERS:
        for pattern in adapter.url_patterns:
            if pattern.search(url):
                return adapter
    return _GENERIC


class ATSRegistry:
    """Registry that maps job application URLs to their ATS adapter."""

    def detect(self, url: str):
        return detect_ats(url)

    @property
    def supported_ats(self) -> list[str]:
        return [a.ats_name for a in _ADAPTERS]
