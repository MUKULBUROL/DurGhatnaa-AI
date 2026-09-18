from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from backend.app.models.models import ChaosExperimentModel, ServiceModel, utc_now
from backend.app.core.events import event_bus


class ChaosService:
    """Controls simulated chaos experiments and fault injection across microservices."""

    def __init__(self):
        # In-memory map for fast telemetry lookup: service_name -> list of active faults
        self._active_faults: Dict[str, Dict[str, Any]] = {}

    def get_service_active_faults(self, service_name: str) -> Optional[Dict[str, Any]]:
        return self._active_faults.get(service_name)

    def get_all_active_faults(self) -> Dict[str, Dict[str, Any]]:
        return self._active_faults

    async def inject_fault(
        self,
        session: AsyncSession,
        service_name: str,
        fault_type: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ChaosExperimentModel:
        """Inject a fault into a service."""
        parameters = parameters or {}

        # Look up service id
        result = await session.execute(
            select(ServiceModel).where(ServiceModel.name == service_name)
        )
        service = result.scalars().first()
        service_id = service.id if service else service_name

        # Create experiment model
        exp = ChaosExperimentModel(
            service_id=service_id,
            fault_type=fault_type.upper(),
            parameters=parameters,
            status="ACTIVE",
            started_at=utc_now(),
        )
        session.add(exp)

        # Update service health to DEGRADED
        if service:
            service.health_status = "DEGRADED"

        await session.commit()
        await session.refresh(exp)

        # Register in-memory
        self._active_faults[service_name] = {
            "experiment_id": exp.id,
            "fault_type": fault_type.upper(),
            "parameters": parameters,
            "started_at": exp.started_at,
        }

        # Broadcast chaos injection event
        await event_bus.broadcast(
            "chaos_events",
            {
                "event_type": "CHAOS_INJECTED",
                "service": service_name,
                "fault_type": fault_type.upper(),
                "parameters": parameters,
                "experiment_id": exp.id,
                "timestamp": exp.started_at.isoformat(),
            },
        )

        return exp

    async def stop_fault(
        self, session: AsyncSession, experiment_id: str
    ) -> Optional[ChaosExperimentModel]:
        """Stop an active chaos experiment."""
        result = await session.execute(
            select(ChaosExperimentModel).where(ChaosExperimentModel.id == experiment_id)
        )
        exp = result.scalars().first()
        if not exp:
            return None

        exp.status = "STOPPED"
        exp.stopped_at = utc_now()

        # Remove from in-memory cache
        for s_name, f_data in list(self._active_faults.items()):
            if f_data.get("experiment_id") == experiment_id:
                del self._active_faults[s_name]

                # Reset service health to HEALTHY if no other faults
                svc_res = await session.execute(
                    select(ServiceModel).where(ServiceModel.id == exp.service_id)
                )
                svc = svc_res.scalars().first()
                if svc:
                    svc.health_status = "HEALTHY"

        await session.commit()
        await session.refresh(exp)

        # Broadcast chaos stopped event
        await event_bus.broadcast(
            "chaos_events",
            {
                "event_type": "CHAOS_STOPPED",
                "experiment_id": experiment_id,
                "timestamp": exp.stopped_at.isoformat(),
            },
        )

        return exp

    async def list_active_experiments(
        self, session: AsyncSession
    ) -> List[ChaosExperimentModel]:
        result = await session.execute(
            select(ChaosExperimentModel)
            .where(ChaosExperimentModel.status == "ACTIVE")
            .order_by(ChaosExperimentModel.started_at.desc())
        )
        return list(result.scalars().all())


chaos_service = ChaosService()
