from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.schemas.schemas import ChaosExperimentCreate, ChaosExperimentRead
from backend.app.services.chaos_service import chaos_service

router = APIRouter(prefix="/chaos", tags=["Chaos Lab & Fault Injection"])


@router.post("/inject", response_model=ChaosExperimentRead, status_code=status.HTTP_201_CREATED)
async def inject_fault(
    payload: ChaosExperimentCreate, session: AsyncSession = Depends(get_db)
):
    """Inject a fault (LATENCY, ERROR_SPIKE, DB_STARVATION, CPU_LEAK) into a service."""
    exp = await chaos_service.inject_fault(
        session=session,
        service_name=payload.service_id,
        fault_type=payload.fault_type,
        parameters=payload.parameters,
    )
    return exp


@router.post("/{experiment_id}/stop", response_model=ChaosExperimentRead)
async def stop_experiment(
    experiment_id: str, session: AsyncSession = Depends(get_db)
):
    """Stop an active chaos experiment and restore normal telemetry."""
    exp = await chaos_service.stop_fault(session, experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chaos experiment '{experiment_id}' not found",
        )
    return exp


@router.get("/active", response_model=List[ChaosExperimentRead])
async def list_active_experiments(session: AsyncSession = Depends(get_db)):
    """List all currently active chaos experiments."""
    return await chaos_service.list_active_experiments(session)
