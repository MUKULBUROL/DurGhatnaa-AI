from datetime import datetime, timedelta, timezone
import random
import uuid
from typing import Any, Dict, List, Optional
import httpx
from backend.app.core.config import settings
from backend.app.schemas.schemas import (
    LogEntry,
    MetricPoint,
    MetricSeries,
    TraceQueryResult,
    TraceSpan,
)
from backend.app.services.chaos_service import chaos_service


class TelemetryService:
    """Unified Telemetry Query Layer for Metrics, Logs, and Distributed Traces."""

    def __init__(self):
        self.mode = settings.TELEMETRY_MODE

    # ---------------- Metrics Query ----------------
    async def query_metrics(
        self,
        service: str,
        metric_name: str = "http_latency_p95",
        minutes_back: int = 30,
    ) -> MetricSeries:
        """Query time-series metrics for a service."""
        if self.mode == "live":
            try:
                return await self._query_live_prometheus(service, metric_name, minutes_back)
            except Exception:
                # Gracefully fall back to synthetic
                pass

        return self._generate_synthetic_metrics(service, metric_name, minutes_back)

    def _generate_synthetic_metrics(
        self, service: str, metric_name: str, minutes_back: int
    ) -> MetricSeries:
        points: List[MetricPoint] = []
        now = datetime.now(timezone.utc)
        active_fault = chaos_service.get_service_active_faults(service)

        # Baseline definitions
        baselines = {
            "http_latency_p95": 45.0,  # ms
            "error_rate_percent": 0.2,  # %
            "db_connections_active": 8.0,
            "cpu_usage_percent": 18.0,
        }
        baseline = baselines.get(metric_name, 50.0)

        step_minutes = max(1, minutes_back // 30)
        num_points = minutes_back // step_minutes

        for i in range(num_points, -1, -1):
            point_time = now - timedelta(minutes=i * step_minutes)
            # Add normal natural jitter
            jitter = (random.random() - 0.5) * (baseline * 0.15)
            val = max(0.0, baseline + jitter)

            # If there's an active fault and we are in the last 15 minutes of the timeline
            if active_fault and i <= 15:
                f_type = active_fault["fault_type"]
                f_params = active_fault.get("parameters", {})

                if f_type == "LATENCY" and metric_name == "http_latency_p95":
                    added = f_params.get("delay_ms", 1200.0)
                    val += added + (random.random() * 150)
                elif f_type == "ERROR_SPIKE" and metric_name == "error_rate_percent":
                    val = f_params.get("error_rate", 55.0) + (random.random() * 5.0)
                elif f_type == "DB_STARVATION" and metric_name == "db_connections_active":
                    val = 98.0 + (random.random() * 2.0)  # Maxed pool
                elif f_type == "CPU_LEAK" and metric_name == "cpu_usage_percent":
                    val = 94.0 + (random.random() * 5.0)

            points.append(MetricPoint(timestamp=point_time, value=round(val, 2)))

        return MetricSeries(metric_name=metric_name, service=service, points=points)

    async def _query_live_prometheus(
        self, service: str, metric_name: str, minutes_back: int
    ) -> MetricSeries:
        query_map = {
            "http_latency_p95": f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) by (le)) * 1000',
            "error_rate_percent": f'sum(rate(http_requests_total{{service="{service}", status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service}"}}[5m])) * 100',
            "cpu_usage_percent": f'sum(rate(container_cpu_usage_seconds_total{{container_name=~".*{service}.*"}}[5m])) * 100',
        }
        prom_query = query_map.get(metric_name, f'{metric_name}{{service="{service}"}}')
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.PROMETHEUS_URL}/api/v1/query_range",
                params={
                    "query": prom_query,
                    "start": (datetime.now(timezone.utc) - timedelta(minutes=minutes_back)).timestamp(),
                    "end": datetime.now(timezone.utc).timestamp(),
                    "step": "60s",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", {}).get("result", [])
            points = []
            if results and "values" in results[0]:
                for ts, val in results[0]["values"]:
                    points.append(
                        MetricPoint(
                            timestamp=datetime.fromtimestamp(float(ts), timezone.utc),
                            value=float(val),
                        )
                    )
            return MetricSeries(metric_name=metric_name, service=service, points=points)

    # ---------------- Logs Query ----------------
    async def query_logs(
        self,
        service: str,
        query: Optional[str] = None,
        level: Optional[str] = None,
        trace_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[LogEntry]:
        """Query application logs for a given service."""
        now = datetime.now(timezone.utc)
        active_fault = chaos_service.get_service_active_faults(service)

        logs: List[LogEntry] = []

        # Baseline info logs
        for i in range(min(limit, 10)):
            t_id = trace_id or f"tr-{uuid.uuid4().hex[:10]}"
            logs.append(
                LogEntry(
                    timestamp=now - timedelta(seconds=i * 25),
                    service=service,
                    level="INFO",
                    trace_id=t_id,
                    message=f"Request processed successfully for route /v1/{service.split('-')[0]}",
                    metadata={"status": 200, "duration_ms": round(25 + random.random() * 20, 1)},
                )
            )

        # Inject error logs if chaos is present
        if active_fault:
            f_type = active_fault["fault_type"]
            for j in range(12):
                t_id = trace_id or f"tr-err-{uuid.uuid4().hex[:8]}"
                if f_type == "LATENCY":
                    msg = f"HTTP 504 Gateway Timeout: Downstream call timed out after 3000ms"
                    meta = {"error": "TimeoutError", "status": 504, "target": "payment-gateway"}
                elif f_type == "ERROR_SPIKE":
                    msg = f"InternalServerError 500: Database transaction deadlocked on row lock"
                    meta = {"error": "DeadlockDetected", "status": 500}
                elif f_type == "DB_STARVATION":
                    msg = f"PoolTimeoutError: Connection pool exhausted (max 50 connections in use)"
                    meta = {"error": "PoolTimeout", "pool_size": 50, "waiting_threads": 34}
                else:
                    msg = f"ResourceExhausted: Out of memory buffer allocation failed"
                    meta = {"error": "OOMError"}

                logs.insert(
                    0,
                    LogEntry(
                        timestamp=now - timedelta(seconds=j * 5),
                        service=service,
                        level="ERROR",
                        trace_id=t_id,
                        message=msg,
                        metadata=meta,
                    ),
                )

        # Filter by level and query
        if level:
            logs = [l for l in logs if l.level.upper() == level.upper()]
        if query:
            logs = [l for l in logs if query.lower() in l.message.lower()]

        return logs[:limit]

    # ---------------- Traces Query ----------------
    async def query_traces(
        self,
        service: str,
        min_duration_ms: float = 0.0,
        error_only: bool = False,
        limit: int = 10,
    ) -> List[TraceQueryResult]:
        """Query distributed trace waterfalls across services."""
        results: List[TraceQueryResult] = []
        active_fault = chaos_service.get_service_active_faults(service)

        for i in range(limit):
            t_id = f"trace-{uuid.uuid4().hex[:12]}"
            is_anomaly = active_fault is not None and i < (limit * 0.7)

            gateway_span_id = f"span-gw-{i}"
            order_span_id = f"span-ord-{i}"
            payment_span_id = f"span-pay-{i}"

            if is_anomaly and active_fault:
                f_type = active_fault["fault_type"]
                pay_dur = 2850.0 if f_type == "LATENCY" else 150.0
                pay_err = True
                pay_code = 504 if f_type == "LATENCY" else 500
                total_dur = pay_dur + 180.0
            else:
                pay_dur = 85.0
                pay_err = False
                pay_code = 200
                total_dur = 140.0

            if error_only and not pay_err:
                continue
            if total_dur < min_duration_ms:
                continue

            spans = [
                TraceSpan(
                    span_id=gateway_span_id,
                    trace_id=t_id,
                    service="api-gateway",
                    operation="POST /api/v1/checkout",
                    duration_ms=total_dur,
                    status_code=pay_code,
                    error=pay_err,
                    attributes={"http.method": "POST", "http.target": "/api/v1/checkout"},
                ),
                TraceSpan(
                    span_id=order_span_id,
                    parent_span_id=gateway_span_id,
                    trace_id=t_id,
                    service="order-service",
                    operation="POST /orders/process",
                    duration_ms=total_dur - 30.0,
                    status_code=pay_code,
                    error=pay_err,
                    attributes={"component": "order-processor"},
                ),
                TraceSpan(
                    span_id=payment_span_id,
                    parent_span_id=order_span_id,
                    trace_id=t_id,
                    service="payment-service",
                    operation="POST /payments/authorize",
                    duration_ms=pay_dur,
                    status_code=pay_code,
                    error=pay_err,
                    attributes={"payment.provider": "stripe-direct", "error.reason": "timeout" if pay_err else ""},
                ),
            ]

            results.append(
                TraceQueryResult(
                    trace_id=t_id,
                    root_service="api-gateway",
                    total_duration_ms=total_dur,
                    has_error=pay_err,
                    spans=spans,
                )
            )

        return results


telemetry_service = TelemetryService()
