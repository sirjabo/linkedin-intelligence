"""ApplicationAgentOrchestrator — coordinates browser automation + candidate knowledge.

Three-phase flow:
  start()  → discover form, classify fields, resolve values, persist session
  resume() → validate all human fields answered, transition to ready_to_fill
  submit() → re-navigate, fill all fields in browser, click submit, capture confirmation

Security invariants:
  - submit() requires human_confirmed=True; raises without it
  - Never invents field values — all values come from CandidateKnowledgeResolver
  - No auto-submit without explicit human confirmation
"""
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.application import Application, ApplicationSubmission
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.form import ApplicationForm, ApplicationFormField
from app.db.models.agent_session import ApplicationAgentSession
from app.services.browser.playwright_adapter import PlaywrightAdapter
from app.services.browser.adapter import RawFormField
from app.services.candidate_knowledge_resolver import CandidateKnowledgeResolver
from app.services.cv_storage import generate_cv_file, cv_exists, get_cv_path
from app.services.ats.registry import detect_ats
from app.services.form_intelligence import classify_field
from app.core.logging import get_logger

logger = get_logger(__name__)

_resolver = CandidateKnowledgeResolver()


class AgentError(Exception):
    pass


class ApplicationAgentOrchestrator:

    async def start(
        self,
        *,
        application_id: uuid.UUID,
        form_url: str,
        db: AsyncSession,
    ) -> ApplicationAgentSession:
        """Discover the form and resolve all field values from candidate data.

        Creates ApplicationAgentSession + ApplicationForm + ApplicationFormField rows.
        Returns the session with status="awaiting_human" (or "ready_to_fill" if none needed).
        """
        # Load application + candidate + profile
        app, candidate, profile = await _load_application_context(application_id, db)

        # Detect ATS
        ats_adapter = detect_ats(form_url)

        # Create session
        session = ApplicationAgentSession(
            application_id=application_id,
            status="initializing",
            ats_name=ats_adapter.ats_name,
            form_url=form_url,
            started_at=datetime.utcnow(),
        )
        db.add(session)
        await db.flush()

        try:
            # Open browser, run any ATS-specific pre-discovery steps, discover form
            session.status = "discovering"
            async with PlaywrightAdapter(headless=True) as browser:
                await ats_adapter.before_discover(browser)
                await browser.open_url(form_url)
                raw_form = await browser.discover_form()

            session.discovered_at = datetime.utcnow()
            session.fields_total = len(raw_form.fields)
            logger.info("form_discovered", session_id=str(session.id), fields=len(raw_form.fields))

            # Delete any prior form for this application
            existing = await db.execute(
                select(ApplicationForm).where(ApplicationForm.application_id == application_id)
            )
            existing_form = existing.scalar_one_or_none()
            if existing_form:
                await db.delete(existing_form)
                await db.flush()

            # Create ApplicationForm
            form = ApplicationForm(
                application_id=application_id,
                form_url=form_url,
                discovery_method="playwright",
                status="mapped",
            )
            db.add(form)
            await db.flush()

            # Classify + resolve each field
            session.status = "mapping"
            auto_count = 0
            human_count = 0
            total_confidence = 0.0

            for i, raw_field in enumerate(raw_form.fields):
                sem_type = classify_field(raw_field.label or raw_field.name)

                # Apply ATS-specific field normalization
                normalized = ats_adapter.normalize_field(raw_field)

                resolution = await _resolver.resolve(
                    semantic_type=sem_type,
                    field_label=normalized.label or normalized.name,
                    field_options=normalized.options,
                    candidate=candidate,
                    profile=profile,
                    application=app,
                )

                is_human = resolution.source == "HUMAN_REQUIRED"
                if is_human:
                    human_count += 1
                else:
                    auto_count += 1

                total_confidence += resolution.confidence

                db.add(ApplicationFormField(
                    form_id=form.id,
                    label=raw_field.label or raw_field.name,
                    field_type=raw_field.field_type,
                    semantic_type=sem_type,
                    is_required=raw_field.is_required,
                    auto_fill_value=resolution.value,
                    human_required=is_human,
                    options=raw_field.options,
                    sort_order=i,
                ))

            # Update session counters
            n = len(raw_form.fields)
            session.fields_auto_filled = auto_count
            session.fields_human_pending = human_count
            session.avg_confidence = total_confidence / n if n else None

            form.human_fields_pending = human_count
            form.status = "ready" if human_count == 0 else "mapped"

            # Handle CV file
            cv_path = _ensure_cv_file(candidate, profile, app)
            if cv_path:
                # Mark the cv_file field as ready (we have the file)
                # The actual path injection happens at fill time
                session.screenshot_before_path = None  # reset

            session.status = "ready_to_fill" if human_count == 0 else "awaiting_human"
            await db.commit()

            logger.info(
                "agent.start.complete",
                session_id=str(session.id),
                auto=auto_count,
                human=human_count,
                status=session.status,
            )
            return session

        except Exception as exc:
            session.status = "failed"
            session.error_message = str(exc)
            session.completed_at = datetime.utcnow()
            await db.commit()
            logger.error("agent.start.failed", session_id=str(session.id), error=str(exc))
            raise AgentError(f"start() failed: {exc}") from exc

    async def resume(
        self,
        *,
        session_id: uuid.UUID,
        db: AsyncSession,
    ) -> ApplicationAgentSession:
        """Check if all human fields have answers and advance the session to ready_to_fill."""
        session = await _load_session(session_id, db)
        if session.status not in ("awaiting_human", "ready_to_fill"):
            raise AgentError(f"Cannot resume session in status '{session.status}'")

        form = await _load_form(session.application_id, db)
        unanswered = [
            f for f in form.fields
            if f.human_required and f.auto_fill_value is None and f.human_answer is None
        ]

        if unanswered:
            session.fields_human_pending = len(unanswered)
            await db.commit()
            return session

        session.status = "ready_to_fill"
        session.fields_human_pending = 0
        form.status = "ready"
        await db.commit()
        return session

    async def submit(
        self,
        *,
        session_id: uuid.UUID,
        human_confirmed: bool,
        db: AsyncSession,
    ) -> ApplicationAgentSession:
        """Fill the form in a real browser and submit.

        Requires human_confirmed=True — raises AgentError without it.
        """
        if not human_confirmed:
            raise AgentError("submit() requires human_confirmed=True — the user must explicitly confirm before submission")

        session = await _load_session(session_id, db)
        if session.status not in ("ready_to_fill",):
            raise AgentError(f"Cannot submit from session status '{session.status}' — must be 'ready_to_fill'")

        form = await _load_form(session.application_id, db)
        app, candidate, profile = await _load_application_context(session.application_id, db)

        session.status = "filling"
        await db.commit()

        try:
            cv_path = _ensure_cv_file(candidate, profile, app)

            async with PlaywrightAdapter(headless=True) as browser:
                await browser.open_url(session.form_url)
                raw_form = await browser.discover_form()

                # Build name → RawFormField map for selector lookup
                field_map: dict[str, RawFormField] = {f.name: f for f in raw_form.fields}

                # Fill each field
                filled = 0
                for db_field in form.fields:
                    value = db_field.auto_fill_value
                    if db_field.human_required:
                        value = db_field.human_answer or db_field.auto_fill_value

                    if value is None and not db_field.is_required:
                        continue  # skip optional unanswered fields

                    # Find matching browser field by label → name matching
                    raw = _find_matching_raw_field(db_field.label, db_field.field_type, raw_form.fields)
                    if not raw:
                        logger.warning("field_not_found_in_browser", label=db_field.label)
                        continue

                    selector = raw.css_selector
                    ftype = raw.field_type

                    if ftype == "file":
                        path = cv_path or value
                        if path:
                            await browser.upload_file(selector, path)
                            filled += 1
                    elif ftype == "select":
                        if value:
                            await browser.select_option(selector, value)
                            filled += 1
                    elif ftype == "checkbox":
                        checked = bool(value) and value.lower() not in ("false", "0", "no", "")
                        await browser.check_checkbox(selector, checked)
                        filled += 1
                    elif ftype == "number":
                        # Only fill if value is a valid numeric string
                        if value and value.replace(".", "", 1).lstrip("-").isdigit():
                            await browser.fill_text(selector, value)
                            filled += 1
                    elif ftype == "url":
                        # Only fill if value is a well-formed URL; invalid URLs trigger browser validation
                        if value and (value.startswith("http://") or value.startswith("https://")):
                            await browser.fill_text(selector, value)
                            filled += 1
                    elif value:
                        await browser.fill_text(selector, value)
                        filled += 1

                session.fields_confirmed = filled
                session.filled_at = datetime.utcnow()

                # Screenshot before submit
                screenshot = await browser.capture_screenshot()

                # Click submit
                session.status = "submitting"
                await db.commit()

                ats_adapter = detect_ats(session.form_url)
                success = await ats_adapter.submit(browser)

                if not success:
                    # Try to detect confirmation anyway
                    success = await browser.is_confirmation_page()

                confirmation_id = await browser.extract_confirmation_id()
                final_url = None
                try:
                    state = await browser.open_url(browser._page.url if browser._page else session.form_url)
                    final_url = state.url
                except Exception:
                    pass

            # Commit submission outcome
            session.status = "submitted" if success else "failed"
            session.confirmation_id = confirmation_id
            session.final_url = final_url
            session.submitted_at = datetime.utcnow()
            session.completed_at = datetime.utcnow()

            if success:
                # Create ApplicationSubmission record
                db.add(ApplicationSubmission(
                    application_id=session.application_id,
                    submitted_at=datetime.utcnow(),
                    confirmation_number=confirmation_id,
                    submission_url=final_url or session.form_url,
                    submitted_via="agent",
                ))
                # Update Application status
                app.status = "applied"
                app.applied_at = datetime.utcnow()

            await db.commit()
            logger.info(
                "agent.submit.complete",
                session_id=str(session.id),
                success=success,
                confirmation_id=confirmation_id,
            )
            return session

        except AgentError:
            raise
        except Exception as exc:
            session.status = "failed"
            session.error_message = str(exc)
            session.completed_at = datetime.utcnow()
            await db.commit()
            logger.error("agent.submit.failed", session_id=str(session.id), error=str(exc))
            raise AgentError(f"submit() failed: {exc}") from exc


# ── Private helpers ───────────────────────────────────────────────────────────

async def _load_application_context(
    application_id: uuid.UUID, db: AsyncSession
) -> tuple[Application, Candidate, CandidateProfile | None]:
    result = await db.execute(
        select(Application)
        .options(
            selectinload(Application.cover_letters),
            selectinload(Application.cv_versions),
        )
        .where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise AgentError(f"Application {application_id} not found")

    cand_result = await db.execute(
        select(Candidate)
        .options(selectinload(Candidate.sources))
        .where(Candidate.id == app.candidate_id)
    )
    candidate = cand_result.scalar_one()

    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate.id)
    )
    profile = profile_result.scalar_one_or_none()

    return app, candidate, profile


async def _load_session(session_id: uuid.UUID, db: AsyncSession) -> ApplicationAgentSession:
    result = await db.execute(
        select(ApplicationAgentSession).where(ApplicationAgentSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise AgentError(f"AgentSession {session_id} not found")
    return session


async def _load_form(application_id: uuid.UUID, db: AsyncSession) -> ApplicationForm:
    result = await db.execute(
        select(ApplicationForm)
        .options(selectinload(ApplicationForm.fields))
        .where(ApplicationForm.application_id == application_id)
    )
    form = result.scalar_one_or_none()
    if not form:
        raise AgentError(f"No ApplicationForm for application {application_id}")
    return form


def _ensure_cv_file(
    candidate: Candidate,
    profile: CandidateProfile | None,
    application: Application,
) -> str | None:
    try:
        if not cv_exists(candidate.id, application.id):
            return generate_cv_file(candidate, profile, application)
        return get_cv_path(candidate.id, application.id)
    except Exception as exc:
        logger.warning("cv_file_generation_failed", error=str(exc))
        return None


def _find_matching_raw_field(
    label: str,
    field_type: str,
    raw_fields: list[RawFormField],
) -> RawFormField | None:
    """Find the best matching raw field from the browser for a stored DB field."""
    label_lower = label.lower().strip()

    # 1. Exact label match
    for raw in raw_fields:
        if (raw.label or "").lower().strip() == label_lower:
            return raw

    # 2. Label contains match
    for raw in raw_fields:
        raw_label = (raw.label or "").lower().strip()
        if raw_label and (label_lower in raw_label or raw_label in label_lower):
            return raw

    # 3. Name heuristic (label words in field name)
    label_words = set(label_lower.split())
    best, best_score = None, 0
    for raw in raw_fields:
        name_words = set((raw.name or "").lower().replace("_", " ").replace("-", " ").split())
        score = len(label_words & name_words)
        if score > best_score:
            best, best_score = raw, score

    return best if best_score > 0 else None
