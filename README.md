# IncidentAI Central Backend

IncidentAI is an autonomous SRE incident response platform with an AI-driven investigation loop, dynamic hypothesis graph, telemetry query engine, chaos lab, and real-time WebSocket event streaming.

---

## Quickstart

### 1. Prerequisites
- Python 3.12+ (or Docker)
- Optional: PostgreSQL & Redis (the backend defaults to local SQLite + in-memory pub/sub if they are not running)

### 2. Setup Environment
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Seed Demo Data
Populates demo services (`api-gateway`, `user-service`, `order-service`, `payment-service`), deployment history, and an active incident:
```bash
python3 backend/seed.py
```

### 4. Run the Backend Server
```bash
python3 backend/run.py
```
Or directly with uvicorn:
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative Redoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Running with Docker Compose (PostgreSQL + Redis + Backend)

To launch the full production-ready stack:
```bash
docker compose up --build
```

---

## Running the Automated Test Suite

```bash
pytest backend/tests
```
All tests run with an isolated in-memory database and test ASGI client.

---

## Core API Endpoints

### 1. Services Registry
- `GET /api/v1/services`: List all registered services with health status and SLOs.
- `GET /api/v1/services/{name}/topology`: Get upstream and downstream dependency relations.
- `POST /api/v1/services`: Register a new microservice.

### 2. Incidents & AI Agent Investigation
- `GET /api/v1/incidents`: List incidents (filterable by status and severity).
- `POST /api/v1/incidents`: Ingest new incident or webhook alert.
- `GET /api/v1/incidents/{id}`: Detailed incident information.
- `POST /api/v1/incidents/{id}/investigate`: Trigger autonomous AI agent investigation loop.
- `GET /api/v1/incidents/{id}/hypotheses`: Retrieve hypothesis graph nodes (unverified, confirmed, refuted).
- `GET /api/v1/incidents/{id}/patches`: Suggested code/configuration remediation patches.
- `GET /api/v1/incidents/{id}/evaluations`: Benchmark evaluation metrics (MTTI, MTTR, accuracy).

### 3. Chaos Lab (Fault Injection)
- `POST /api/v1/chaos/inject`: Inject fault (`LATENCY`, `ERROR_SPIKE`, `DB_STARVATION`, `CPU_LEAK`).
- `POST /api/v1/chaos/{experiment_id}/stop`: Stop active chaos experiment.
- `GET /api/v1/chaos/active`: List currently active experiments.

### 4. Telemetry Query Engine
- `GET /api/v1/telemetry/metrics`: Query time-series metric points (p95 latency, error rate, connections).
- `GET /api/v1/telemetry/logs`: Query structured logs and stack traces.
- `GET /api/v1/telemetry/traces`: Query distributed trace waterfalls across services.

### 5. Real-Time WebSocket Streaming
- `WS /ws/incidents/{incident_id}`: Streams live AI agent thoughts, tool execution results, and hypothesis graph changes.
- `WS /ws/chaos`: Streams real-time chaos injection events.

---

## Architecture Reference

For detailed sequence diagrams, component interaction, and design rationale, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
