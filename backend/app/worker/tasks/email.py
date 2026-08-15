"""Celery tasks for email — weekly market digest."""
import asyncio
from app.worker.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.worker.tasks.email.send_weekly_digests", bind=True, max_retries=2)
def send_weekly_digests(self):
    """Send weekly market digest to all users who have a candidate profile with target_roles.

    Runs every Monday at 8 AM ART via Celery Beat. Skips users without SMTP configured.
    """
    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import select
        from app.core.config import settings
        from app.db.models.candidate import Candidate
        from app.db.models.user import User
        from app.api.routes.market import _aggregate_skills, _CACHE
        from app.services.email_service import send_email, _digest_html

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        sent = 0
        skipped = 0

        async with Session() as db:
            rows = await db.execute(
                select(User.email, Candidate.target_roles)
                .join(Candidate, Candidate.user_id == User.id)
                .where(Candidate.target_roles.isnot(None))
            )
            users = rows.all()

        for user_email, target_roles in users:
            if not target_roles:
                skipped += 1
                continue

            role = target_roles[0] if isinstance(target_roles, list) else "ai_engineer"

            try:
                jobs, tag_counter = await _aggregate_skills(role, limit=20)
                n = max(len(jobs), 1)

                top_skills = [
                    {"skill": slug.title(), "frequency_pct": round(cnt / n * 100, 1)}
                    for slug, cnt in tag_counter.most_common(10)
                ]

                from collections import Counter
                company_counter: Counter = Counter()
                for job in jobs:
                    if job.company:
                        company_counter[job.company.strip()] += 1
                top_companies = [{"name": name} for name, _ in company_counter.most_common(5)]

                html = _digest_html(
                    user_email=user_email,
                    top_skills=top_skills,
                    top_companies=top_companies,
                    profile_tips=[],
                    role=role,
                )
                ok = send_email(
                    to=user_email,
                    subject=f"⚡ Mercado tech esta semana — Top skills para {role.replace('_', ' ').title()}",
                    html_body=html,
                )
                if ok:
                    sent += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.error("digest_user_failed", user=user_email, error=str(exc))
                skipped += 1

        await engine.dispose()
        logger.info("weekly_digests_done", sent=sent, skipped=skipped)
        return {"sent": sent, "skipped": skipped}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("send_weekly_digests_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=600)
