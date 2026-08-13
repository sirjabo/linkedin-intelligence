# Backward-compatibility shim — redirects to the new models package.
# Remove this file when all imports are updated.
from app.db.models.cv_session import CVSession, ChatMessage  # noqa: F401
from app.db.models.user import User  # noqa: F401
from app.db.models.candidate import Candidate, CandidateSource, CandidateProfile, EvidenceRecord  # noqa: F401
