import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.investigation import Investigation, SourceResult
from app.schemas.investigation import InvestigationCreate, InvestigationResponse, InvestigationListResponse
from app.schemas.report import DossierReport, RiskScore, SourceFinding, Alert

router = APIRouter(prefix="/api/v1", tags=["investigations"])


def _dispatch(investigation_id: str):
    """Try Celery first; fall back to inline async execution via BackgroundTasks."""
    try:
        from app.workers.celery_app import celery_app
        # Ping the broker to check availability before dispatching
        celery_app.control.inspect(timeout=1).ping()
        from app.workers.tasks import run_investigation
        run_investigation.delay(investigation_id)
        return True
    except Exception:
        return False


async def _run_inline(investigation_id: str):
    """Run investigation directly in the FastAPI process (no Redis/Celery needed)."""
    from app.workers.tasks import _run_investigation_async
    await _run_investigation_async(investigation_id)


@router.post("/investigations", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    payload: InvestigationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    investigation = Investigation(
        id=str(uuid.uuid4()),
        status="pending",
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        entity_name=payload.entity_name,
        email=payload.email,
        nickname=payload.nickname,
        phone=payload.phone,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    # Try Celery; if unavailable run inline as FastAPI background task
    if not _dispatch(investigation.id):
        background_tasks.add_task(_run_inline, investigation.id)

    return investigation


@router.get("/investigations", response_model=InvestigationListResponse)
async def list_investigations(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    result = await db.execute(
        select(Investigation).order_by(desc(Investigation.created_at)).offset(skip).limit(limit)
    )
    investigations = result.scalars().all()

    count_result = await db.execute(select(Investigation))
    total = len(count_result.scalars().all())

    return InvestigationListResponse(
        investigations=[InvestigationResponse.model_validate(i) for i in investigations],
        total=total,
    )


@router.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id)
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigação não encontrada")
    return investigation


@router.get("/investigations/{investigation_id}/report", response_model=DossierReport)
async def get_report(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id)
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigação não encontrada")

    sources_result = await db.execute(
        select(SourceResult).where(SourceResult.investigation_id == investigation_id)
    )
    source_results = sources_result.scalars().all()

    # Build risk score breakdown
    risk_score_obj = None
    if investigation.risk_score is not None and investigation.risk_level is not None:
        corporate_score = 0.0
        media_score = 0.0
        lists_score = 0.0
        social_score = 0.0
        email_score = 0.0

        for sr in source_results:
            if sr.source_name in ("cnpj", "qsa_search"):
                corporate_score = max(corporate_score, sr.risk_contribution)
            elif sr.source_name == "negative_media":
                media_score = sr.risk_contribution
            elif sr.source_name == "restrictive_lists":
                lists_score = sr.risk_contribution
            elif sr.source_name in ("social_linkedin", "social_instagram", "social_twitter", "social_tiktok"):
                social_score = max(social_score, sr.risk_contribution)
            elif sr.source_name == "hibp":
                email_score = sr.risk_contribution

        risk_score_obj = RiskScore(
            total=investigation.risk_score,
            level=investigation.risk_level,
            corporate=corporate_score,
            media=media_score,
            lists=lists_score,
            social=social_score,
            email=email_score,
        )

    # Build alerts
    alerts: List[Alert] = []
    for sr in source_results:
        if sr.findings and isinstance(sr.findings, dict):
            for alert_data in sr.findings.get("alerts", []):
                alerts.append(Alert(**alert_data))

    # Sort alerts by severity
    severity_order = {"critical": 0, "danger": 1, "warning": 2, "info": 3}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 99))

    sources = [
        SourceFinding(
            source_name=sr.source_name,
            status=sr.status,
            findings=sr.findings,
            risk_contribution=sr.risk_contribution,
            collected_at=sr.collected_at,
            error_message=sr.error_message,
        )
        for sr in source_results
    ]

    return DossierReport(
        investigation_id=investigation.id,
        entity_name=investigation.entity_name,
        entity_type=investigation.entity_type,
        entity_id=investigation.entity_id,
        email=investigation.email,
        status=investigation.status,
        created_at=investigation.created_at,
        risk_score=risk_score_obj,
        alerts=alerts,
        sources=sources,
    )


@router.delete("/investigations/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id)
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigação não encontrada")
    await db.delete(investigation)
    await db.commit()
