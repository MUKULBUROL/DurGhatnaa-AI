from datetime import datetime, timezone
import uuid
from typing import List, Optional
from sqlalchemy import (
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid(prefix: str = "") -> str:
    short_id = uuid.uuid4().hex[:8]
    return f"{prefix}-{short_id}" if prefix else short_id


class ServiceModel(Base):
    """Represents a microservice in the production catalog."""
    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("svc"))
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), default="tier-1")  # tier-0, tier-1, tier-2
    owner_team: Mapped[str] = mapped_column(String(128), default="core-platform")
    repo_url: Mapped[str] = mapped_column(String(256), default="")
    health_status: Mapped[str] = mapped_column(String(32), default="HEALTHY")  # HEALTHY, DEGRADED, CRITICAL
    dependencies: Mapped[list] = mapped_column(JSON, default=list)  # List of service names
    slo_target_latency_ms: Mapped[float] = mapped_column(Float, default=200.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    incidents: Mapped[List["IncidentModel"]] = relationship("IncidentModel", back_populates="affected_service")
    deployments: Mapped[List["DeploymentModel"]] = relationship("DeploymentModel", back_populates="service")


class IncidentModel(Base):
    """Represents an active or resolved incident."""
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("inc"))
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="P2")  # P0, P1, P2, P3
    status: Mapped[str] = mapped_column(String(32), default="TRIGGERED")  # TRIGGERED, INVESTIGATING, IDENTIFIED, MITIGATED, RESOLVED
    affected_service_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("services.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    root_cause: Mapped[str] = mapped_column(Text, default="")
    suggested_remediation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    affected_service: Mapped[Optional["ServiceModel"]] = relationship("ServiceModel", back_populates="incidents")
    agent_runs: Mapped[List["AgentRunModel"]] = relationship("AgentRunModel", back_populates="incident", cascade="all, delete-orphan")
    hypotheses: Mapped[List["HypothesisModel"]] = relationship("HypothesisModel", back_populates="incident", cascade="all, delete-orphan")
    patches: Mapped[List["PatchModel"]] = relationship("PatchModel", back_populates="incident", cascade="all, delete-orphan")


class AgentRunModel(Base):
    """An autonomous investigation run triggered for an incident."""
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("run"))
    incident_id: Mapped[str] = mapped_column(String(64), ForeignKey("incidents.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")  # RUNNING, COMPLETED, FAILED
    model_name: Mapped[str] = mapped_column(String(64), default="mock-incident-gpt")
    steps_count: Mapped[int] = mapped_column(Integer, default=0)
    rca_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    incident: Mapped["IncidentModel"] = relationship("IncidentModel", back_populates="agent_runs")
    tool_calls: Mapped[List["ToolCallModel"]] = relationship("ToolCallModel", back_populates="agent_run", cascade="all, delete-orphan")
    hypotheses: Mapped[List["HypothesisModel"]] = relationship("HypothesisModel", back_populates="agent_run", cascade="all, delete-orphan")


class HypothesisModel(Base):
    """A working hypothesis formed by the AI agent."""
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("hyp"))
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("agent_runs.id"), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(64), ForeignKey("incidents.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)  # 0.0 to 1.0
    status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED")  # UNVERIFIED, CONFIRMED, REFUTED
    supporting_evidence: Mapped[list] = mapped_column(JSON, default=list)
    refuting_evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    incident: Mapped["IncidentModel"] = relationship("IncidentModel", back_populates="hypotheses")
    agent_run: Mapped["AgentRunModel"] = relationship("AgentRunModel", back_populates="hypotheses")


class ToolCallModel(Base):
    """Records an executed tool by the agent with inputs, outputs, and latency."""
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("tool"))
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("agent_runs.id"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # SUCCESS, ERROR
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    agent_run: Mapped["AgentRunModel"] = relationship("AgentRunModel", back_populates="tool_calls")


class DeploymentModel(Base):
    """Tracks code or config deployments across services."""
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("dep"))
    service_id: Mapped[str] = mapped_column(String(64), ForeignKey("services.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    commit_hash: Mapped[str] = mapped_column(String(64), default="")
    author: Mapped[str] = mapped_column(String(128), default="sre-bot")
    diff_summary: Mapped[str] = mapped_column(Text, default="")
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    service: Mapped["ServiceModel"] = relationship("ServiceModel", back_populates="deployments")


class PatchModel(Base):
    """Remediation code diff or config patch generated for an incident."""
    __tablename__ = "patches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("pat"))
    incident_id: Mapped[str] = mapped_column(String(64), ForeignKey("incidents.id"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), default="")
    diff_content: Mapped[str] = mapped_column(Text, default="")
    validation_status: Mapped[str] = mapped_column(String(32), default="PENDING")  # PENDING, PASSED, FAILED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    incident: Mapped["IncidentModel"] = relationship("IncidentModel", back_populates="patches")


class EvaluationModel(Base):
    """Benchmark evaluation of an AI investigation run."""
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("eval"))
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    incident_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mtti_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    mttr_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy_score: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 to 1.0
    tool_efficiency_score: Mapped[float] = mapped_column(Float, default=1.0)
    hallucination_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChaosExperimentModel(Base):
    """Fault injection experiment executed against services."""
    __tablename__ = "chaos_experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: generate_uuid("chaos"))
    service_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fault_type: Mapped[str] = mapped_column(String(64), nullable=False)  # LATENCY, ERROR_SPIKE, DB_STARVATION, CPU_LEAK
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")  # ACTIVE, STOPPED
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
