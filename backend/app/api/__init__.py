"""API routers package."""
from backend.app.api.incidents import router as incidents_router
from backend.app.api.services_api import router as services_router
from backend.app.api.chaos_api import router as chaos_router
from backend.app.api.telemetry_api import router as telemetry_router
from backend.app.api.websocket_api import router as websocket_router

__all__ = [
    "incidents_router",
    "services_router",
    "chaos_router",
    "telemetry_router",
    "websocket_router",
]
