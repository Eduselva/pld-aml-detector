import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.investigation import Investigation, SourceResult
from app.schemas.investigation import InvestigationCreate, InvestigationResponse, InvestigationListResponse
from app.schemas.report import DossierReport, RiskScore, SourceFinding, Alert, HistoryEntry, InvestigationHistory, GraphNodeOut, GraphEdgeOut, GraphEdgeCreate, GraphStats, GraphResponse
from app.schemas.case import CaseCreate, CaseUpdate, CaseOut

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
        government_score = 0.0
        legal_score = 0.0
        social_score = 0.0
        email_score = 0.0

        for sr in source_results:
            if sr.source_name in ("cnpj", "qsa_search"):
                corporate_score = max(corporate_score, sr.risk_contribution)
            elif sr.source_name in ("negative_media", "gazettes"):
                media_score = max(media_score, sr.risk_contribution)
            elif sr.source_name == "restrictive_lists":
                lists_score = sr.risk_contribution
            elif sr.source_name == "transparency_gov":
                government_score = sr.risk_contribution
            elif sr.source_name == "court_records":
                legal_score = sr.risk_contribution
            elif sr.source_name in ("social_linkedin", "social_instagram", "social_twitter", "social_tiktok",
                                    "social_facebook", "social_pinterest", "social_flickr"):
                social_score = max(social_score, sr.risk_contribution)
            elif sr.source_name == "hibp":
                email_score = sr.risk_contribution

        risk_score_obj = RiskScore(
            total=investigation.risk_score,
            level=investigation.risk_level,
            corporate=corporate_score,
            media=media_score,
            lists=lists_score,
            government=government_score,
            legal=legal_score,
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


@router.get("/investigations/{investigation_id}/history", response_model=InvestigationHistory)
async def get_history(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Investigation).where(Investigation.id == investigation_id)
    )
    current = result.scalar_one_or_none()
    if not current:
        raise HTTPException(status_code=404, detail="Investigação não encontrada")

    # Find all completed investigations for the same entity
    query = select(Investigation).where(
        Investigation.status == "complete",
        Investigation.entity_type == current.entity_type,
    )
    if current.entity_id:
        query = query.where(Investigation.entity_id == current.entity_id)
    else:
        name_key = current.entity_name or current.nickname
        query = query.where(
            (Investigation.entity_name == name_key) | (Investigation.nickname == name_key)
        )
    query = query.order_by(desc(Investigation.created_at))

    all_inv = (await db.execute(query)).scalars().all()

    entries: list[HistoryEntry] = []
    for inv in all_inv:
        src_result = await db.execute(
            select(SourceResult).where(SourceResult.investigation_id == inv.id)
        )
        sources = src_result.scalars().all()

        alerts: list[Alert] = []
        source_scores: dict[str, float] = {}
        for sr in sources:
            source_scores[sr.source_name] = sr.risk_contribution
            if sr.findings and isinstance(sr.findings, dict):
                for a in sr.findings.get("alerts", []):
                    alerts.append(Alert(**a))

        severity_order = {"critical": 0, "danger": 1, "warning": 2, "info": 3}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 99))

        entries.append(HistoryEntry(
            id=inv.id,
            created_at=inv.created_at,
            risk_score=inv.risk_score,
            risk_level=inv.risk_level,
            alerts=alerts,
            source_scores=source_scores,
        ))

    return InvestigationHistory(entries=entries)


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    db: AsyncSession = Depends(get_db),
    case_id: Optional[str] = Query(default=None),
):
    from app.models.graph import GraphNode, GraphEdge
    from app.models.case import CaseInvestigation
    from collections import defaultdict

    if case_id:
        # Resolve investigations belonging to the case
        ci_result = await db.execute(
            select(CaseInvestigation).where(CaseInvestigation.case_id == case_id)
        )
        case_inv_ids = {ci.investigation_id for ci in ci_result.scalars().all()}

        # Subject nodes for those investigations
        subj_result = await db.execute(
            select(GraphNode).where(
                GraphNode.type == "subject",
                GraphNode.investigation_id.in_(case_inv_ids),
            )
        )
        subject_nodes = subj_result.scalars().all()
        subject_ids = {n.id for n in subject_nodes}

        # Edges: auto edges from case subjects, manual edges only if both endpoints are case subjects
        all_edges_result = await db.execute(select(GraphEdge))
        all_edges = all_edges_result.scalars().all()
        edges = []
        extra_node_ids: set[str] = set()
        for e in all_edges:
            src_is_subj = e.source_id in subject_ids
            tgt_is_subj = e.target_id in subject_ids
            if e.is_manual:
                if src_is_subj and tgt_is_subj:
                    edges.append(e)
            else:
                if src_is_subj:
                    edges.append(e)
                    extra_node_ids.add(e.target_id)

        # Fetch referenced entity nodes
        all_node_ids = subject_ids | extra_node_ids
        if all_node_ids:
            nodes_result = await db.execute(
                select(GraphNode).where(GraphNode.id.in_(all_node_ids))
            )
            nodes = nodes_result.scalars().all()
        else:
            nodes = list(subject_nodes)
    else:
        nodes_result = await db.execute(select(GraphNode))
        nodes = nodes_result.scalars().all()
        edges_result = await db.execute(select(GraphEdge))
        edges = edges_result.scalars().all()

    # Compute shared_entities: entity nodes connected to 2+ distinct subject nodes
    subject_ids_all = {n.id for n in nodes if n.type == "subject"}
    node_to_subjects: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.source_id in subject_ids_all:
            node_to_subjects[edge.target_id].add(edge.source_id)
    shared_entities = sum(1 for subjs in node_to_subjects.values() if len(subjs) >= 2)

    stats = GraphStats(
        subjects=sum(1 for n in nodes if n.type == "subject"),
        companies=sum(1 for n in nodes if n.type == "company"),
        partners=sum(1 for n in nodes if n.type == "partner"),
        shared_entities=shared_entities,
    )

    return GraphResponse(
        nodes=[GraphNodeOut(
            id=n.id, type=n.type, label=n.label, value=n.value,
            investigation_id=n.investigation_id,
            risk_level=n.risk_level, risk_score=n.risk_score,
        ) for n in nodes],
        edges=[GraphEdgeOut(
            id=e.id, source_id=e.source_id, target_id=e.target_id, label=e.label,
            relationship_type=e.relationship_type or "auto",
            is_manual=bool(e.is_manual),
        ) for e in edges],
        stats=stats,
    )


@router.post("/graph/edges", response_model=GraphEdgeOut, status_code=status.HTTP_201_CREATED)
async def create_graph_edge(
    payload: GraphEdgeCreate,
    db: AsyncSession = Depends(get_db),
):
    from app.models.graph import GraphNode, GraphEdge

    src = await db.get(GraphNode, payload.source_node_id)
    tgt = await db.get(GraphNode, payload.target_node_id)
    if not src or not tgt:
        raise HTTPException(status_code=404, detail="Nó não encontrado")

    edge = GraphEdge(
        id=str(uuid.uuid4()),
        source_id=payload.source_node_id,
        target_id=payload.target_node_id,
        label=payload.label,
        relationship_type=payload.relationship_type,
        is_manual=True,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)

    return GraphEdgeOut(
        id=edge.id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        label=edge.label,
        relationship_type=edge.relationship_type,
        is_manual=True,
    )


@router.delete("/graph/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_graph_edge(
    edge_id: str,
    db: AsyncSession = Depends(get_db),
):
    from app.models.graph import GraphEdge

    edge = await db.get(GraphEdge, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="Aresta não encontrada")
    if not edge.is_manual:
        raise HTTPException(status_code=400, detail="Apenas conexões manuais podem ser removidas")
    await db.delete(edge)
    await db.commit()


# ── Cases ────────────────────────────────────────────────────────────────────

@router.post("/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(payload: CaseCreate, db: AsyncSession = Depends(get_db)):
    from app.models.case import Case

    case = Case(id=str(uuid.uuid4()), name=payload.name.strip(), description=payload.description)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return CaseOut(
        id=case.id, name=case.name, description=case.description,
        created_at=case.created_at, investigation_ids=[], investigation_count=0,
    )


@router.get("/cases", response_model=list[CaseOut])
async def list_cases(db: AsyncSession = Depends(get_db)):
    from app.models.case import Case, CaseInvestigation
    from collections import defaultdict

    cases_result = await db.execute(select(Case).order_by(Case.created_at))
    cases = cases_result.scalars().all()

    ci_result = await db.execute(select(CaseInvestigation))
    ci_all = ci_result.scalars().all()

    inv_ids_by_case: dict[str, list[str]] = defaultdict(list)
    for ci in ci_all:
        inv_ids_by_case[ci.case_id].append(ci.investigation_id)

    return [
        CaseOut(
            id=c.id, name=c.name, description=c.description, created_at=c.created_at,
            investigation_ids=inv_ids_by_case.get(c.id, []),
            investigation_count=len(inv_ids_by_case.get(c.id, [])),
        )
        for c in cases
    ]


@router.get("/cases/{case_id}", response_model=CaseOut)
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.case import Case, CaseInvestigation

    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Caso não encontrado")

    ci_result = await db.execute(
        select(CaseInvestigation).where(CaseInvestigation.case_id == case_id)
    )
    inv_ids = [ci.investigation_id for ci in ci_result.scalars().all()]
    return CaseOut(
        id=case.id, name=case.name, description=case.description,
        created_at=case.created_at, investigation_ids=inv_ids,
        investigation_count=len(inv_ids),
    )


@router.put("/cases/{case_id}", response_model=CaseOut)
async def update_case(case_id: str, payload: CaseUpdate, db: AsyncSession = Depends(get_db)):
    from app.models.case import Case, CaseInvestigation

    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    if payload.name is not None:
        case.name = payload.name.strip()
    if payload.description is not None:
        case.description = payload.description
    await db.commit()
    await db.refresh(case)

    ci_result = await db.execute(
        select(CaseInvestigation).where(CaseInvestigation.case_id == case_id)
    )
    inv_ids = [ci.investigation_id for ci in ci_result.scalars().all()]
    return CaseOut(
        id=case.id, name=case.name, description=case.description,
        created_at=case.created_at, investigation_ids=inv_ids,
        investigation_count=len(inv_ids),
    )


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(case_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.case import Case

    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    await db.delete(case)
    await db.commit()


@router.post("/cases/{case_id}/investigations/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_investigation_to_case(
    case_id: str, investigation_id: str, db: AsyncSession = Depends(get_db)
):
    from app.models.case import Case, CaseInvestigation

    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Caso não encontrado")

    inv = await db.get(Investigation, investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada")

    existing = await db.execute(
        select(CaseInvestigation).where(
            CaseInvestigation.case_id == case_id,
            CaseInvestigation.investigation_id == investigation_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(CaseInvestigation(case_id=case_id, investigation_id=investigation_id))
        await db.commit()


@router.delete("/cases/{case_id}/investigations/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_investigation_from_case(
    case_id: str, investigation_id: str, db: AsyncSession = Depends(get_db)
):
    from app.models.case import CaseInvestigation

    ci = await db.execute(
        select(CaseInvestigation).where(
            CaseInvestigation.case_id == case_id,
            CaseInvestigation.investigation_id == investigation_id,
        )
    )
    ci_obj = ci.scalar_one_or_none()
    if ci_obj:
        await db.delete(ci_obj)
        await db.commit()


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
