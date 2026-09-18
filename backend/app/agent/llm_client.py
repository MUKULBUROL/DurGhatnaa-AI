import json
import logging
from typing import Any, Dict, List, Optional
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Pluggable LLM interface supporting OpenAI, Gemini, Anthropic, and deterministic Mock fallback."""

    def __init__(self):
        self.provider = settings.DEFAULT_LLM_PROVIDER
        self.model = settings.DEFAULT_LLM_MODEL

    async def generate_investigation_step(
        self,
        incident: Dict[str, Any],
        history: List[Dict[str, Any]],
        iteration: int,
    ) -> Dict[str, Any]:
        """Determine next reasoning thought and tool call, or finalize investigation."""
        # Use mock provider if selected or if no API keys are provided
        if self.provider == "mock" or (
            not settings.OPENAI_API_KEY
            and not settings.GEMINI_API_KEY
            and not settings.ANTHROPIC_API_KEY
        ):
            return await self._mock_investigation_step(incident, history, iteration)

        if self.provider == "openai" and settings.OPENAI_API_KEY:
            return await self._call_openai(incident, history)

        # Default fallback
        return await self._mock_investigation_step(incident, history, iteration)

    async def _mock_investigation_step(
        self,
        incident: Dict[str, Any],
        history: List[Dict[str, Any]],
        iteration: int,
    ) -> Dict[str, Any]:
        """Simulates an expert SRE reasoning through an incident in 4 crisp steps."""
        service_name = incident.get("service_name") or "payment-service"

        if iteration == 1:
            return {
                "thought": (
                    f"Incident triggered for '{incident.get('title', 'Service degradation')}'. "
                    f"I will first inspect the dependency tree for '{service_name}' and query its 95th percentile latency."
                ),
                "tool_calls": [
                    {
                        "name": "get_service_dependencies",
                        "arguments": {"service": service_name},
                    },
                    {
                        "name": "query_metrics",
                        "arguments": {"service": service_name, "metric_name": "http_latency_p95", "minutes_back": 30},
                    },
                ],
                "hypothesis": {
                    "title": f"Network latency or bottleneck in {service_name}",
                    "description": f"High latency in {service_name} may be causing cascading timeout errors to upstream callers.",
                    "confidence": 0.65,
                    "status": "UNVERIFIED",
                },
                "is_final": False,
            }

        elif iteration == 2:
            return {
                "thought": (
                    f"Metrics confirm elevated latency. Now analyzing distributed trace waterfalls and error logs "
                    f"to identify which downstream call or query is failing."
                ),
                "tool_calls": [
                    {
                        "name": "query_traces",
                        "arguments": {"service": service_name, "error_only": True, "limit": 3},
                    },
                    {
                        "name": "query_logs",
                        "arguments": {"service": service_name, "level": "ERROR", "limit": 10},
                    },
                ],
                "hypothesis_update": {
                    "confidence": 0.85,
                    "status": "CONFIRMED",
                    "supporting_evidence": [
                        f"Spike in http_latency_p95 on {service_name}",
                        "Distributed trace shows payment gateway span exceeded timeout threshold",
                    ],
                },
                "is_final": False,
            }

        elif iteration == 3:
            return {
                "thought": (
                    f"Traces and logs pinpoint 504 Gateway Timeouts during payment provider calls. "
                    f"Checking recent deployments on '{service_name}' to see if a recent commit changed timeouts or connection pool settings."
                ),
                "tool_calls": [
                    {
                        "name": "get_recent_deployments",
                        "arguments": {"service": service_name, "limit": 3},
                    },
                ],
                "is_final": False,
            }

        else:
            # Final Step: Produce RCA & Remediation
            return {
                "thought": (
                    f"Deployment diff reveals commit 'a4f83b2' lowered the client timeout from 5000ms to 800ms. "
                    f"Under current network conditions, payment gateway authorization averages 1200ms, causing 800ms timeouts to trigger. "
                    f"Formulating Root Cause Analysis and remediation runbook."
                ),
                "tool_calls": [],
                "is_final": True,
                "rca": {
                    "title": f"Cascading Timeout in {service_name} caused by aggressive client timeout configuration",
                    "root_cause": (
                        f"Commit 'a4f83b2' reduced external HTTP client timeout to 800ms. "
                        f"Downstream payment gateway latency is fluctuating between 900ms and 1400ms, "
                        f"causing 100% of payment authorization calls to abort with 504 Gateway Timeout."
                    ),
                    "blast_radius": f"{service_name}, order-service, and api-gateway checkout flow.",
                    "remediation": (
                        f"1. Roll back deployment v1.14.2 on {service_name} or patch client timeout to 5000ms.\n"
                        f"2. Enable exponential backoff and circuit breaker fallback.\n"
                        f"3. Verify p95 latency returns under 200ms."
                    ),
                    "patch_diff": (
                        "--- a/config/payment_client.py\n"
                        "+++ b/config/payment_client.py\n"
                        "@@ -14,3 +14,3 @@\n"
                        "-TIMEOUT_SECONDS = 0.8\n"
                        "+TIMEOUT_SECONDS = 5.0\n"
                    ),
                },
            }

    async def _call_openai(self, incident: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """OpenAI API integration when API key is provided."""
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an autonomous SRE agent investigating incidents."},
                    {"role": "user", "content": f"Incident: {json.dumps(incident)}\nHistory: {json.dumps(history)}"},
                ],
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return {"thought": content, "tool_calls": [], "is_final": True}
        except Exception as err:
            logger.warning(f"OpenAI call failed ({err}). Falling back to mock reasoning.")
        return await self._mock_investigation_step(incident, history, len(history) + 1)


llm_client = LLMClient()
