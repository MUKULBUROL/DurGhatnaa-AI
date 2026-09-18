from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.models import ServiceModel


DEFAULT_TOPOLOGY = [
    {
        "name": "api-gateway",
        "tier": "tier-0",
        "owner_team": "traffic-edge",
        "repo_url": "https://github.com/incidentai-demo/api-gateway",
        "health_status": "HEALTHY",
        "dependencies": ["user-service", "order-service"],
        "slo_target_latency_ms": 150.0,
    },
    {
        "name": "user-service",
        "tier": "tier-1",
        "owner_team": "auth-identity",
        "repo_url": "https://github.com/incidentai-demo/user-service",
        "health_status": "HEALTHY",
        "dependencies": [],
        "slo_target_latency_ms": 100.0,
    },
    {
        "name": "order-service",
        "tier": "tier-1",
        "owner_team": "checkout-core",
        "repo_url": "https://github.com/incidentai-demo/order-service",
        "health_status": "HEALTHY",
        "dependencies": ["user-service", "payment-service"],
        "slo_target_latency_ms": 250.0,
    },
    {
        "name": "payment-service",
        "tier": "tier-1",
        "owner_team": "payments-fintech",
        "repo_url": "https://github.com/incidentai-demo/payment-service",
        "health_status": "HEALTHY",
        "dependencies": [],
        "slo_target_latency_ms": 300.0,
    },
]


class ServiceRegistry:
    """Manages service catalog, metadata, and runtime health."""

    async def ensure_defaults(self, session: AsyncSession):
        """Seed default service topology if table is empty."""
        result = await session.execute(select(ServiceModel))
        existing = result.scalars().all()
        if not existing:
            for item in DEFAULT_TOPOLOGY:
                svc = ServiceModel(
                    name=item["name"],
                    tier=item["tier"],
                    owner_team=item["owner_team"],
                    repo_url=item["repo_url"],
                    health_status=item["health_status"],
                    dependencies=item["dependencies"],
                    slo_target_latency_ms=item["slo_target_latency_ms"],
                )
                session.add(svc)
            await session.commit()

    async def get_service_by_name(self, session: AsyncSession, name: str) -> Optional[ServiceModel]:
        result = await session.execute(select(ServiceModel).where(ServiceModel.name == name))
        return result.scalars().first()

    async def get_service_by_id(self, session: AsyncSession, service_id: str) -> Optional[ServiceModel]:
        result = await session.execute(select(ServiceModel).where(ServiceModel.id == service_id))
        return result.scalars().first()

    async def list_services(self, session: AsyncSession) -> List[ServiceModel]:
        result = await session.execute(select(ServiceModel).order_by(ServiceModel.name))
        return list(result.scalars().all())

    async def get_dependency_tree(self, session: AsyncSession, service_name: str) -> Dict[str, List[str]]:
        """Return downstream (services this calls) and upstream (services calling this)."""
        services = await self.list_services(session)
        service_map = {s.name: s for s in services}
        
        downstream = []
        if service_name in service_map:
            downstream = service_map[service_name].dependencies or []

        upstream = []
        for s in services:
            if s.dependencies and service_name in s.dependencies:
                upstream.append(s.name)

        return {
            "service": service_name,
            "downstream": downstream,
            "upstream": upstream,
        }


service_registry = ServiceRegistry()
