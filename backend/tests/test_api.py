import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_service_registry_endpoints(client: AsyncClient):
    # List services (seeds default topology)
    resp = await client.get("/api/v1/services")
    assert resp.status_code == 200
    services = resp.json()
    assert len(services) >= 4
    names = [s["name"] for s in services]
    assert "api-gateway" in names
    assert "payment-service" in names

    # Get specific service topology
    resp_top = await client.get("/api/v1/services/order-service/topology")
    assert resp_top.status_code == 200
    top = resp_top.json()
    assert "payment-service" in top["downstream"]


@pytest.mark.asyncio
async def test_chaos_injection_lifecycle(client: AsyncClient):
    # Inject latency fault into payment-service
    payload = {
        "service_id": "payment-service",
        "fault_type": "LATENCY",
        "parameters": {"delay_ms": 1500},
    }
    resp = await client.post("/api/v1/chaos/inject", json=payload)
    assert resp.status_code == 201
    exp = resp.json()
    assert exp["status"] == "ACTIVE"
    exp_id = exp["id"]

    # Verify active list
    resp_active = await client.get("/api/v1/chaos/active")
    assert resp_active.status_code == 200
    active_list = resp_active.json()
    assert any(e["id"] == exp_id for e in active_list)

    # Stop fault
    resp_stop = await client.post(f"/api/v1/chaos/{exp_id}/stop")
    assert resp_stop.status_code == 200
    stopped = resp_stop.json()
    assert stopped["status"] == "STOPPED"


@pytest.mark.asyncio
async def test_telemetry_queries(client: AsyncClient):
    # Query metrics
    resp_m = await client.get(
        "/api/v1/telemetry/metrics",
        params={"service": "payment-service", "metric_name": "http_latency_p95"},
    )
    assert resp_m.status_code == 200
    metrics = resp_m.json()
    assert metrics["service"] == "payment-service"
    assert len(metrics["points"]) > 0

    # Query logs
    resp_l = await client.get(
        "/api/v1/telemetry/logs",
        params={"service": "payment-service", "limit": 10},
    )
    assert resp_l.status_code == 200
    logs = resp_l.json()
    assert len(logs) > 0

    # Query traces
    resp_t = await client.get(
        "/api/v1/telemetry/traces",
        params={"service": "payment-service", "limit": 3},
    )
    assert resp_t.status_code == 200
    traces = resp_t.json()
    assert len(traces) > 0


@pytest.mark.asyncio
async def test_incident_and_ai_investigation_flow(client: AsyncClient):
    # 1. Create Incident
    inc_payload = {
        "title": "P1: Payment service elevated error rate",
        "severity": "P1",
        "status": "TRIGGERED",
        "summary": "Elevated 504 errors on payment transactions",
    }
    resp = await client.post("/api/v1/incidents", json=inc_payload)
    assert resp.status_code == 201
    inc = resp.json()
    inc_id = inc["id"]

    # 2. Trigger AI Investigation
    resp_inv = await client.post(f"/api/v1/incidents/{inc_id}/investigate")
    assert resp_inv.status_code == 200
    agent_run = resp_inv.json()
    assert agent_run["status"] == "COMPLETED"
    assert agent_run["steps_count"] > 0
    assert len(agent_run["rca_summary"]) > 0

    # 3. Check generated hypotheses
    resp_hyp = await client.get(f"/api/v1/incidents/{inc_id}/hypotheses")
    assert resp_hyp.status_code == 200
    hypotheses = resp_hyp.json()
    assert len(hypotheses) > 0
    assert any(h["status"] == "CONFIRMED" for h in hypotheses)

    # 4. Check generated patches
    resp_pat = await client.get(f"/api/v1/incidents/{inc_id}/patches")
    assert resp_pat.status_code == 200
    patches = resp_pat.json()
    assert len(patches) > 0
    assert "TIMEOUT_SECONDS" in patches[0]["diff_content"]

    # 5. Check evaluation score
    resp_eval = await client.get(f"/api/v1/incidents/{inc_id}/evaluations")
    assert resp_eval.status_code == 200
    evals = resp_eval.json()
    assert len(evals) > 0
    assert evals[0]["accuracy_score"] > 0.8
