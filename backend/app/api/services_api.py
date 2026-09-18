from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.schemas.schemas import ServiceCreate, ServiceRead
from backend.app.services.service_registry import service_registry
from backend.app.models.models import ServiceModel

router = APIRouter(prefix="/services", tags=["Services Registry"])


@router.get("", response_model=List[ServiceRead])
async def list_services(session: AsyncSession = Depends(get_db)):
    """Retrieve all microservices in the catalog with health status and SLOs."""
    await service_registry.ensure_defaults(session)
    return await service_registry.list_services(session)


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def register_service(
    payload: ServiceCreate, session: AsyncSession = Depends(get_db)
):
    """Register a new service into the catalog."""
    existing = await service_registry.get_service_by_name(session, payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service '{payload.name}' is already registered",
        )
    svc = ServiceModel(**payload.model_dump())
    session.add(svc)
    await session.commit()
    await session.refresh(svc)
    return svc


@router.get("/{name}", response_model=ServiceRead)
async def get_service(name: str, session: AsyncSession = Depends(get_db)):
    """Get metadata for a specific service by name."""
    svc = await service_registry.get_service_by_name(session, name)
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{name}' not found",
        )
    return svc


@router.get("/{name}/topology")
async def get_service_topology(name: str, session: AsyncSession = Depends(get_db)):
    """Retrieve upstream and downstream service dependencies."""
    svc = await service_registry.get_service_by_name(session, name)
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{name}' not found",
        )
    return await service_registry.get_dependency_tree(session, name)
