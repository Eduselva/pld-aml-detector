import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.workers.tasks.run_investigation", max_retries=2)
def run_investigation(self, investigation_id: str):
    """Run all OSINT sources for an investigation."""
    logger.info(f"Starting investigation {investigation_id}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_investigation_async(investigation_id))
        finally:
            loop.close()
    except Exception as exc:
        logger.exception(f"Investigation {investigation_id} failed: {exc}")
        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)
        try:
            loop2.run_until_complete(_mark_failed(investigation_id, str(exc)))
        finally:
            loop2.close()
        raise self.retry(exc=exc, countdown=60)


async def _mark_failed(investigation_id: str, error: str):
    from app.database import AsyncSessionLocal
    from app.models.investigation import Investigation
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Investigation).where(Investigation.id == investigation_id))
        investigation = result.scalar_one_or_none()
        if investigation:
            investigation.status = "failed"
            investigation.error_message = error
            investigation.updated_at = datetime.utcnow()
            await db.commit()


async def _run_investigation_async(investigation_id: str):
    from app.database import AsyncSessionLocal
    from app.models.investigation import Investigation, SourceResult
    from app.scoring.engine import ScoringEngine
    from sqlalchemy import select
    import uuid

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Investigation).where(Investigation.id == investigation_id))
        investigation = result.scalar_one_or_none()
        if not investigation:
            logger.error(f"Investigation {investigation_id} not found")
            return

        investigation.status = "running"
        investigation.updated_at = datetime.utcnow()
        await db.commit()

        entity_name = investigation.entity_name
        entity_type = investigation.entity_type
        entity_id = investigation.entity_id
        email = investigation.email
        phone = investigation.phone
        nickname = investigation.nickname

    # Run all sources concurrently
    source_tasks = _build_source_tasks(entity_name, entity_type, entity_id, email, nickname=nickname, phone=phone)

    source_findings = {}
    async def run_source(source_name: str, coro):
        try:
            result = await asyncio.wait_for(coro, timeout=30.0)
            return source_name, result, None
        except asyncio.TimeoutError:
            logger.warning(f"Source {source_name} timed out")
            return source_name, None, "Timeout após 30 segundos"
        except Exception as e:
            logger.exception(f"Source {source_name} failed: {e}")
            return source_name, None, str(e)

    tasks = [run_source(name, coro) for name, coro in source_tasks]
    results = await asyncio.gather(*tasks)

    # Save results and compute scores
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Investigation).where(Investigation.id == investigation_id))
        investigation = result.scalar_one_or_none()
        if not investigation:
            return

        scoring_data = {}
        for source_name, findings, error in results:
            risk_contribution = 0.0
            status = "complete"
            if error:
                status = "failed"
            elif findings is not None:
                risk_contribution = findings.get("raw_score", 0.0)

            source_result = SourceResult(
                id=str(uuid.uuid4()),
                investigation_id=investigation_id,
                source_name=source_name,
                status=status,
                findings=findings if findings else {},
                risk_contribution=risk_contribution,
                collected_at=datetime.utcnow(),
                error_message=error,
            )
            db.add(source_result)
            scoring_data[source_name] = risk_contribution

        # Compute final score
        engine = ScoringEngine()
        total_score, risk_level = engine.compute_final_score(scoring_data)

        investigation.risk_score = total_score
        investigation.risk_level = risk_level
        investigation.status = "complete"
        investigation.updated_at = datetime.utcnow()

        await db.commit()
        logger.info(f"Investigation {investigation_id} complete. Score: {total_score:.1f} ({risk_level})")


def _build_source_tasks(entity_name: str, entity_type: str, entity_id: str, email: Optional[str], nickname: Optional[str] = None, phone: Optional[str] = None):
    """Build list of (source_name, coroutine) tuples."""
    from app.sources.corporate.cnpj import CNPJSource
    from app.sources.media.negative_media import NegativeMediaSource
    from app.sources.lists.restrictive import RestrictiveListsSource
    from app.sources.email_intel.hibp import HIBPSource
    from app.sources.social.linkedin import LinkedInSource
    from app.sources.social.instagram import InstagramSource
    from app.sources.social.twitter import TwitterSource
    from app.sources.social.tiktok import TikTokSource

    tasks = []

    if entity_type == "cnpj":
        tasks.append(("cnpj", CNPJSource().collect(entity_id=entity_id, entity_name=entity_name)))
    else:
        # For CPF (individuals), skip CNPJ source
        tasks.append(("cnpj", _empty_source("cnpj")))

    tasks.append(("negative_media", NegativeMediaSource().collect(entity_id=entity_id, entity_name=entity_name, nickname=nickname, phone=phone)))
    tasks.append(("restrictive_lists", RestrictiveListsSource().collect(entity_id=entity_id, entity_name=entity_name)))

    if email:
        tasks.append(("hibp", HIBPSource().collect(entity_id=entity_id, entity_name=entity_name, email=email)))
    else:
        tasks.append(("hibp", _empty_source("hibp")))

    tasks.append(("social_linkedin", LinkedInSource().collect(entity_id=entity_id, entity_name=entity_name, nickname=nickname)))
    tasks.append(("social_instagram", InstagramSource().collect(entity_id=entity_id, entity_name=entity_name, email=email, nickname=nickname)))
    tasks.append(("social_twitter", TwitterSource().collect(entity_id=entity_id, entity_name=entity_name, email=email, nickname=nickname)))
    tasks.append(("social_tiktok", TikTokSource().collect(entity_id=entity_id, entity_name=entity_name, email=email, nickname=nickname)))

    return tasks


async def _empty_source(source_name: str) -> dict:
    return {
        "source": source_name,
        "raw_score": 0.0,
        "summary": "Não aplicável",
        "alerts": [],
        "data": {},
    }
