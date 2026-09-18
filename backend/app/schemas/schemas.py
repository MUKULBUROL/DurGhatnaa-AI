from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# Base Config
class CoreModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- Services ----------------
class ServiceBase(BaseModel):
    name: str
    tier: str = "tier-1"
    owner_team: str = "core-platform"
    repo_url: str = ""
    health_status: str = "HEALTHY"
    dependencies: List[str] = Field(default_factory=list)
    slo_target_latency_ms: float = 200.0


class ServiceCreate(ServiceBase):
    pass


class ServiceRead(ServiceBase, CoreModel):
    id: str
    created_at: datetime


# ---------------- Incidents ----------------
class IncidentBase(BaseModel):
    title: str
    severity: str = "P2"
    status: str = "TRIGGERED"
    affected_service_id: Optional[str] = None
    summary: str = ""
    root_cause: str = ""
    suggested_remediation: str = ""


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    affected_service_id: Optional[str] = None
    summary: Optional[str] = None
    root_cause: Optional[str] = None
    suggested_remediation: Optional[str] = None
    resolved_at: Optional[datetime] = None


class IncidentRead(IncidentBase, CoreModel):
    id: str
    created_at: datetime
    resolved_at: Optional[datetime] = None


# ---------------- Hypotheses ----------------
class HypothesisBase(BaseModel):
    title: str
    description: str = ""
    confidence: float = 0.5
    status: str = "UNVERIFIED"
    supporting_evidence: List[Any] = Field(default_factory=list)
    refuting_evidence: List[Any] = Field(default_factory=list)


class HypothesisCreate(HypothesisBase):
    run_id: str
    incident_id: str


class HypothesisUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    supporting_evidence: Optional[List[Any]] = None
    refuting_evidence: Optional[List[Any]] = None


class HypothesisRead(HypothesisBase, CoreModel):
    id: str
    run_id: str
    incident_id: str
    created_at: datetime


# ---------------- Tool Calls ----------------
class ToolCallBase(BaseModel):
    tool_name: str
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    output_payload: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    status: str = "SUCCESS"


class ToolCallCreate(ToolCallBase):
    run_id: str


class ToolCallRead(ToolCallBase, CoreModel):
    id: str
    run_id: str
    created_at: datetime


# ---------------- Agent Runs ----------------
class AgentRunBase(BaseModel):
    incident_id: str
    status: str = "RUNNING"
    model_name: str = "mock-incident-gpt"
    steps_count: int = 0
    rca_summary: str = ""


class AgentRunCreate(BaseModel):
    model_name: Optional[str] = None


class AgentRunRead(AgentRunBase, CoreModel):
    id: str
    created_at: datetime
    finished_at: Optional[datetime] = None


class AgentRunDetail(AgentRunRead):
    hypotheses: List[HypothesisRead] = Field(default_factory=list)
    tool_calls: List[ToolCallRead] = Field(default_factory=list)


# ---------------- Deployments ----------------
class DeploymentBase(BaseModel):
    service_id: str
    version: str
    commit_hash: str = ""
    author: str = "sre-bot"
    diff_summary: str = ""


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentRead(DeploymentBase, CoreModel):
    id: str
    deployed_at: datetime


# ---------------- Patches ----------------
class PatchBase(BaseModel):
    service_id: str
    title: str
    diff_content: str
    validation_status: str = "PENDING"


class PatchCreate(PatchBase):
    incident_id: str


class PatchRead(PatchBase, CoreModel):
    id: str
    incident_id: str
    created_at: datetime


# ---------------- Chaos Experiments ----------------
class ChaosExperimentBase(BaseModel):
    service_id: str
    fault_type: str  # LATENCY, ERROR_SPIKE, DB_STARVATION, CPU_LEAK
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ChaosExperimentCreate(ChaosExperimentBase):
    pass


class ChaosExperimentRead(ChaosExperimentBase, CoreModel):
    id: str
    status: str
    started_at: datetime
    stopped_at: Optional[datetime] = None


# ---------------- Evaluations ----------------
class EvaluationRead(CoreModel):
    id: str
    run_id: str
    incident_id: str
    mtti_seconds: float
    mttr_seconds: float
    accuracy_score: float
    tool_efficiency_score: float
    hallucination_detected: bool
    notes: str
    created_at: datetime


# ---------------- Telemetry Schemas ----------------
class MetricPoint(BaseModel):
    timestamp: datetime
    value: float


class MetricSeries(BaseModel):
    metric_name: str
    service: str
    points: List[MetricPoint]


class MetricQueryRequest(BaseModel):
    service: str
    metric_name: str  # "http_latency_p95", "error_rate_percent", "db_connections_active"
    minutes_back: int = 30


class LogEntry(BaseModel):
    timestamp: datetime
    service: str
    level: str  # "INFO", "WARN", "ERROR"
    trace_id: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LogQueryRequest(BaseModel):
    service: str
    query: Optional[str] = None
    level: Optional[str] = None
    trace_id: Optional[str] = None
    limit: int = 50


class TraceSpan(BaseModel):
    span_id: str
    parent_span_id: Optional[str] = None
    trace_id: str
    service: str
    operation: str
    duration_ms: float
    status_code: int = 200
    error: bool = False
    attributes: Dict[str, Any] = Field(default_factory=dict)


class TraceQueryResult(BaseModel):
    trace_id: str
    root_service: str
    total_duration_ms: float
    has_error: bool
    spans: List[TraceSpan]


# ---------------- WebSocket Schemas ----------------
class WSEvent(BaseModel):
    event_type: str  # "AGENT_THINKING", "TOOL_CALLED", "HYPOTHESIS_UPDATED", "RCA_PRODUCED", "INCIDENT_STATUS"
    incident_id: str
    timestamp: datetime
    data: Dict[str, Any]
