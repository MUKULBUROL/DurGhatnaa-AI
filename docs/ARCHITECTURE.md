# IncidentAI Architecture Documentation

IncidentAI is an autonomous SRE incident response platform designed to ingest alerts, isolate root causes across distributed microservices, construct dynamic hypothesis graphs, propose code or config remediations, and validate fixes in real time.

---

## System Architecture

```
                         INCIDENTAI
                             │
             ┌───────────────┴───────────────┐
             │                               │
             │         USER / ENGINEER       │
             │                               │
             └───────────────┬───────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   Next.js Frontend  │
                  │                     │
                  │ Dashboard           │
                  │ Incidents           │
                  │ Chaos Lab           │
                  │ Investigation       │
                  │ Hypothesis Graph    │
                  │ Fix Validation      │
                  └──────────┬──────────┘
                             │
                       REST / WebSocket
                             │
                             ▼
              ┌─────────────────────────────┐
              │       CENTRAL BACKEND       │
              │          FastAPI            │
              │                             │
              │ Incident Service            │
              │ Service Registry            │
              │ Telemetry Query Layer       │
              │ Chaos Controller            │
              │ AI Orchestrator             │
              │ GitHub Integration          │
              │ Sandbox Controller          │
              │ Evaluation Service          │
              └───────┬──────────┬──────────┘
                      │          │
                  PostgreSQL    Redis
                      │          │
                      │          ├── Cache
                      │          ├── Jobs
                      │          └── Live state
                      │
                      ├── incidents
                      ├── agent_runs
                      ├── hypotheses
                      ├── tool_calls
                      ├── deployments
                      ├── patches
                      └── evaluations
```

---

## Build Sequence (Order of Construction)

The backend was constructed in 6 modular layers to guarantee zero circular dependencies, high testability, and immediate local execution:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Core & Environment (config, database, hybrid event bus)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Domain Models & Schemas (SQLAlchemy ORM + Pydantic v2)   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Service Registry & Telemetry Query Layer                 │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Chaos Controller & Fault Injection Simulator             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. AI Agent Orchestrator & Tool-Calling ReAct Engine        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. REST Routers, WebSocket Streamers, Seed & Test Suite     │
└─────────────────────────────────────────────────────────────┘
```

### Layer 1: Core Configuration & Event Bus
- **File**: `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/core/events.py`
- **Purpose**: Establishes settings with environment variable overrides. Provides an async SQLAlchemy session engine (SQLite local default, PostgreSQL production ready) and a hybrid `EventBus` that automatically routes real-time events over Redis Pub/Sub when connected, or falls back to an in-memory asynchronous bus when running locally without Redis.

### Layer 2: Domain Models & Schemas
- **File**: `backend/app/models/models.py`, `backend/app/schemas/schemas.py`
- **Purpose**: Defines database models with typed relationships:
  - `ServiceModel`: Service registry catalog, SLO thresholds, upstream/downstream dependencies.
  - `IncidentModel`: State tracking (`TRIGGERED`, `INVESTIGATING`, `IDENTIFIED`, `MITIGATED`, `RESOLVED`).
  - `AgentRunModel`: Autonomous investigation session metadata.
  - `HypothesisModel`: Working hypotheses formed during investigation.
  - `ToolCallModel`: Execution latency, inputs, and outputs of agent tools.
  - `ChaosExperimentModel`: Tracks injected faults and affected blast radius.
  - `DeploymentModel`: Service deployment history and commit diffs.
  - `PatchModel`: Suggested code or configuration fixes.
  - `EvaluationModel`: SRE benchmark metrics (MTTI, MTTR, accuracy score).

### Layer 3: Service Registry & Telemetry Query Layer
- **File**: `backend/app/services/service_registry.py`, `backend/app/services/telemetry_service.py`
- **Purpose**:
  - `ServiceRegistry`: In-memory and DB catalog of microservices (`api-gateway`, `user-service`, `order-service`, `payment-service`) with dependency graph traversal.
  - `TelemetryService`: Unified query engine supporting live Prometheus/Loki/Jaeger or high-fidelity synthetic telemetry that dynamically reacts to active chaos faults.

### Layer 4: Chaos Controller
- **File**: `backend/app/services/chaos_service.py`
- **Purpose**: Injects simulated production faults:
  - `LATENCY`: Injects delay (e.g. +1200ms) on target services.
  - `ERROR_SPIKE`: Injects HTTP 500 error bursts.
  - `DB_STARVATION`: Exhausts connection pools.
  - `CPU_LEAK`: Simulates runaway thread CPU saturation.
  - Emits real-time chaos events to subscribers over WebSockets.

### Layer 5: AI Agent Orchestrator & Tool System
- **File**: `backend/app/agent/tools.py`, `backend/app/agent/llm_client.py`, `backend/app/agent/orchestrator.py`
- **Purpose**: Implements the autonomous ReAct investigation cycle:
  1. Comprehends incident alert details and inspects topology.
  2. Formulates initial hypothesis node (status: `UNVERIFIED`).
  3. Dispatches tools: `query_metrics`, `query_logs`, `query_traces`, `get_recent_deployments`.
  4. Gathers evidence and updates hypothesis (status: `CONFIRMED` or `REFUTED`).
  5. Produces Root Cause Analysis (RCA), timeline, and suggested remediation patch.
  6. Automatically scores the run in `EvaluationModel` (MTTI, MTTR, accuracy).

### Layer 6: API Layer, WebSockets & Integration
- **File**: `backend/app/api/*`, `backend/app/main.py`, `backend/seed.py`
- **Purpose**:
  - REST endpoints for service catalog, incidents, chaos experiments, and telemetry queries.
  - WebSocket streaming `/ws/incidents/{incident_id}` broadcasting real-time thought streams, tool results, and hypothesis graph changes.
  - Seed script for instant demo data.

---

## Real-Time WebSocket Event Protocol

Connecting to `ws://localhost:8000/ws/incidents/{incident_id}` streams the following event types:

| Event Type | Description | Sample Payload |
|---|---|---|
| `CONNECTED` | Connection established | `{"message": "Connected to live stream..."}` |
| `INVESTIGATION_STARTED` | Investigation initiated | `{"incident_id": "...", "run_id": "..."}` |
| `AGENT_THINKING` | LLM reasoning step | `{"thought": "Inspecting latency on payment-service...", "iteration": 1}` |
| `TOOL_CALLED` | Agent invokes tool | `{"tool_name": "query_metrics", "arguments": {...}}` |
| `TOOL_RESULT` | Tool output returned | `{"tool_name": "query_metrics", "latency_ms": 12.4, "output": {...}}` |
| `HYPOTHESIS_CREATED` | New hypothesis node | `{"hypothesis_id": "...", "title": "...", "confidence": 0.65}` |
| `HYPOTHESIS_UPDATED` | Hypothesis confirmed/refuted | `{"hypothesis_id": "...", "status": "CONFIRMED", "confidence": 0.85}` |
| `RCA_PRODUCED` | Final RCA generated | `{"root_cause": "...", "remediation": "...", "mtti_seconds": 18.2}` |

---

## Directory Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── chaos_api.py
│   │   │   ├── incidents.py
│   │   │   ├── services_api.py
│   │   │   ├── telemetry_api.py
│   │   │   └── websocket_api.py
│   │   ├── agent/
│   │   │   ├── llm_client.py
│   │   │   ├── orchestrator.py
│   │   │   └── tools.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── events.py
│   │   ├── models/
│   │   │   └── models.py
│   │   ├── schemas/
│   │   │   └── schemas.py
│   │   ├── services/
│   │   │   ├── chaos_service.py
│   │   │   ├── service_registry.py
│   │   │   └── telemetry_service.py
│   │   └── main.py
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_api.py
│   ├── run.py
│   └── seed.py
├── docs/
│   └── ARCHITECTURE.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```
