"""ATSRegistry: detect which ATS a URL belongs to and return the right adapter.

Each call to detect_ats() / ATSRegistry.detect() returns a **fresh** adapter
instance so adapters can safely store per-session state without concurrent
requests corrupting each other.
"""
from app.services.ats.adapter import ATSAdapter, ATSCapabilities
from app.services.ats.ashby import AshbyAdapter
from app.services.ats.generic import GenericFormAgent
from app.services.ats.greenhouse import GreenhouseAdapter
from app.services.ats.lever import LeverAdapter
from app.services.ats.smart_recruiters import SmartRecruitersAdapter
from app.services.ats.workday import WorkdayAdapter

# Ordered: more specific patterns first.
# Each entry is a zero-arg factory so detect_ats() can return fresh instances.
_ADAPTER_FACTORIES: list[tuple[type, ...]] = [
    (GreenhouseAdapter,),
    (LeverAdapter,),
    (AshbyAdapter,),
    (WorkdayAdapter,),
    (SmartRecruitersAdapter,),
]

# Probe instances are used only for URL pattern matching (read-only).
_PROBES: list[ATSAdapter] = [cls() for (cls,) in _ADAPTER_FACTORIES]


def detect_ats(url: str) -> ATSAdapter:
    """Return a **fresh** ATS adapter instance for the given URL.

    Returns a new GenericFormAgent if no known pattern matches.
    Each call produces a separate instance — safe to use concurrently.
    """
    for probe, (cls,) in zip(_PROBES, _ADAPTER_FACTORIES, strict=True):
        for pattern in probe.url_patterns:
            if pattern.search(url):
                return cls()
    return GenericFormAgent()


class ATSRegistry:
    """Registry that maps job application URLs to their ATS adapter."""

    def detect(self, url: str) -> ATSAdapter:
        return detect_ats(url)

    @property
    def supported_ats(self) -> list[str]:
        return [probe.ats_name for probe in _PROBES]

    def capabilities_for(self, url: str) -> ATSCapabilities:
        """Return capability matrix for the ATS that owns this URL."""
        adapter = detect_ats(url)
        return adapter.capabilities
