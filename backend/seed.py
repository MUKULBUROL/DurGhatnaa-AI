import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.models.models import DeploymentModel, IncidentModel, ServiceModel, utc_now
from backend.app.services.service_registry import DEFAULT_TOPOLOGY


async def seed():
    print("Initializing database...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # 1. Seed Services
        services_map = {}
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
            services_map[item["name"]] = svc

        await session.commit()
        for svc in services_map.values():
            await session.refresh(svc)
        print(f"Seeded {len(services_map)} services.")

        # 2. Seed Deployments
        payment_svc = services_map.get("payment-service")
        if payment_svc:
            dep1 = DeploymentModel(
                service_id=payment_svc.id,
                version="v1.14.2",
                commit_hash="a4f83b2",
                author="dev-alice",
                diff_summary="Optimize client network calls: set payment gateway timeout to 800ms",
                deployed_at=utc_now() - timedelta(minutes=22),
            )
            dep2 = DeploymentModel(
                service_id=payment_svc.id,
                version="v1.14.1",
                commit_hash="f1e98cd",
                author="dev-bob",
                diff_summary="Add retry backoff metric logging and update dependencies",
                deployed_at=utc_now() - timedelta(hours=36),
            )
            session.add_all([dep1, dep2])

        # 3. Seed an active Incident
        incident = IncidentModel(
            title="P1: Cascading HTTP 504 Timeouts in Checkout Gateway",
            severity="P1",
            status="TRIGGERED",
            affected_service_id=payment_svc.id if payment_svc else None,
            summary=(
                "AlertManager triggered 'CheckoutLatencyDegraded'. Over 35% of checkout requests "
                "are timing out at api-gateway with HTTP 504. Upstream order-service reports timeout "
                "calling payment-service."
            ),
        )
        session.add(incident)
        await session.commit()
        await session.refresh(incident)

        print(f"Seeded active incident: {incident.id} - '{incident.title}'")
        print("\nSeed completed successfully!")
        print(f"You can start investigation using: POST /api/v1/incidents/{incident.id}/investigate")


if __name__ == "__main__":
    asyncio.run(seed())
