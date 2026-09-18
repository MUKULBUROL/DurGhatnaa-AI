from typing import List, Optional
from fastapi import APIRouter, Query
from backend.app.schemas.schemas import LogEntry, MetricSeries, TraceQueryResult
from backend.app.services.telemetry_service import telemetry_service

router = APIRouter(prefix="/telemetry", tags=["Telemetry Query Layer"])


@router.get("/metrics", response_model=MetricSeries)
async def get_metrics(
    service: str = Query(..., description="Service name"),
    metric_name: str = Query("http_latency_p95", description="Metric identifier"),
    minutes_back: int = Query(30, ge=1, le=1440, description="History window in minutes"),
):
    """Query time-series telemetry metrics for a microservice."""
    return await telemetry_service.query_metrics(
        service=service,
        metric_name=metric_name,
        minutes_back=minutes_back,
    )


@router.get("/logs", response_model=List[LogEntry])
async def get_logs(
    service: str = Query(..., description="Service name"),
    query: Optional[str] = Query(None, description="Log message text search"),
    level: Optional[str] = Query(None, description="Log severity (INFO, WARN, ERROR)"),
    trace_id: Optional[str] = Query(None, description="Correlated trace ID"),
    limit: int = Query(50, ge=1, le=200, description="Max logs to return"),
):
    """Query structured logs and stack traces."""
    return await telemetry_service.query_logs(
        service=service,
        query=query,
        level=level,
        trace_id=trace_id,
        limit=limit,
    )


@router.get("/traces", response_model=List[TraceQueryResult])
async def get_traces(
    service: str = Query("api-gateway", description="Root or target service name"),
    error_only: bool = Query(False, description="Filter for traces with errors/timeouts"),
    min_duration_ms: float = Query(0.0, description="Minimum span latency in ms"),
    limit: int = Query(5, ge=1, le=50, description="Number of traces to fetch"),
):
    """Query distributed trace waterfalls across services."""
    return await telemetry_service.query_traces(
        service=service,
        error_only=error_only,
        min_duration_ms=min_duration_ms,
        limit=limit,
    )
