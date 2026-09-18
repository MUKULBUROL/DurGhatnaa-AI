from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import AsyncSessionLocal, get_db
from backend.app.models.models import (
    AgentRunModel,
    EvaluationModel,
    HypothesisModel,
    IncidentModel,
    PatchModel,
    ServiceModel,
    utc_now,
)
from backend.app.schemas.schemas import (
    AgentRunCreate,
    AgentRunDetail,
    AgentRunRead,
    EvaluationRead,
    HypothesisRead,
    IncidentCreate,
    IncidentRead,
    IncidentUpdate,
    PatchRead,
)
from backend.app.agent.orchestrator import agent_orchestrator
from backend.app.services.service_registry import service_registry

router = APIRouter(prefix="/incidents", tags=["Incidents & AI Investigation"])


@router.get("", response_model=List[IncidentRead])
async def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity_filter: Optional[str] = Query(None, alias="severity"),
    session: AsyncSession = Depends(get_db),
):
    """List all incidents with optional status or severity filters."""
    query = select(IncidentModel).order_by(IncidentModel.created_at.desc())
    if status_filter:
        query = query.where(IncidentModel.status == status_filter.upper())
    if severity_filter:
        query = query.where(IncidentModel.severity == severity_filter.upper())

    result = await session.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    background_tasks: BackgroundTasks,
    auto_investigate: bool = Query(False, description="Automatically trigger AI agent investigation"),
    session: AsyncSession = Depends(get_db),
):
    """Create a new incident (or ingest alert)."""
    incident = IncidentModel(**payload.model_dump())
    session.add(incident)
    await session.commit()
    await session.refresh(incident)

    if auto_investigate:
        # Run investigation in background
        async def _run_bg():
            async with AsyncSessionLocal() as bg_session:
                await agent_orchestrator.investigate_incident(incident.id, bg_session)

        background_tasks.add_task(_run_bg)

    return incident


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: str, session: AsyncSession = Depends(get_db)):
    """Retrieve details for a specific incident."""
    result = await session.execute(
        select(IncidentModel).where(IncidentModel.id == incident_id)
    )
    inc = result.scalars().first()
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return inc


@router.patch("/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: str,
    payload: IncidentUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update incident status, title, root cause, or resolution."""
    result = await session.execute(
        select(IncidentModel).where(IncidentModel.id == incident_id)
    )
    inc = result.scalars().first()
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    data = payload.model_dump(exclude_unset=True)
    for field, val in data.items():
        setattr(inc, field, val)

    if payload.status == "RESOLVED" and not inc.resolved_at:
        inc.resolved_at = utc_now()

    await session.commit()
    await session.refresh(inc)
    return inc


@router.post("/{incident_id}/investigate", response_model=AgentRunRead)
async def start_investigation(
    incident_id: str,
    payload: Optional[AgentRunCreate] = None,
    session: AsyncSession = Depends(get_db),
):
    """Trigger an autonomous AI agent run to investigate this incident."""
    result = await session.execute(
        select(IncidentModel).where(IncidentModel.id == incident_id)
    )
    inc = result.scalars().first()
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    model_name = payload.model_name if payload else None
    agent_run = await agent_orchestrator.investigate_incident(
        incident_id=incident_id,
        session=session,
        model_name=model_name,
    )
    return agent_run


@router.get("/{incident_id}/runs", response_model=List[AgentRunRead])
async def get_incident_agent_runs(
    incident_id: str, session: AsyncSession = Depends(get_db)
):
    """Get all AI investigation runs for this incident."""
    result = await session.execute(
        select(AgentRunModel)
        .where(AgentRunModel.incident_id == incident_id)
        .order_by(AgentRunModel.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{incident_id}/hypotheses", response_model=List[HypothesisRead])
async def get_incident_hypotheses(
    incident_id: str, session: AsyncSession = Depends(get_db)
):
    """Get hypothesis graph nodes formed during investigation."""
    result = await session.execute(
        select(HypothesisModel)
        .where(HypothesisModel.incident_id == incident_id)
        .order_by(HypothesisModel.created_at.asc())
    )
    return list(result.scalars().all())


@router.get("/{incident_id}/patches", response_model=List[PatchRead])
async def get_incident_patches(
    incident_id: str, session: AsyncSession = Depends(get_db)
):
    """Get code or config remediation patches suggested for this incident."""
    result = await session.execute(
        select(PatchModel)
        .where(PatchModel.incident_id == incident_id)
        .order_by(PatchModel.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{incident_id}/evaluations", response_model=List[EvaluationRead])
async def get_incident_evaluations(
    incident_id: str, session: AsyncSession = Depends(get_db)
):
    """Get automated benchmark evaluation metrics for this incident's agent runs."""
    result = await session.execute(
        select(EvaluationModel)
        .where(EvaluationModel.incident_id == incident_id)
        .order_by(EvaluationModel.created_at.desc())
    )
    return list(result.scalars().all())
