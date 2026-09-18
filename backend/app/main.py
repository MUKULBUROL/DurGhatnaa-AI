from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.core.events import event_bus
from backend.app.services.service_registry import service_registry
from backend.app.api.incidents import router as incidents_router
from backend.app.api.services_api import router as services_router
from backend.app.api.chaos_api import router as chaos_router
from backend.app.api.telemetry_api import router as telemetry_router
from backend.app.api.websocket_api import router as websocket_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("incidentai.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting IncidentAI Central Backend...")
    # 1. Initialize DB schema
    await init_db()

    # 2. Seed initial service registry catalog
    async with AsyncSessionLocal() as session:
        await service_registry.ensure_defaults(session)

    # 3. Initialize Event Bus
    await event_bus.initialize()
    logger.info("IncidentAI Central Backend ready.")

    yield

    logger.info("Shutting down IncidentAI Central Backend.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "IncidentAI Central Backend: Autonomous SRE incident response platform with "
        "telemetry query layer, chaos controller, AI agent orchestrator, and real-time streaming."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(services_router, prefix=settings.API_V1_STR)
app.include_router(incidents_router, prefix=settings.API_V1_STR)
app.include_router(chaos_router, prefix=settings.API_V1_STR)
app.include_router(telemetry_router, prefix=settings.API_V1_STR)
app.include_router(websocket_router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "ONLINE",
        "docs": "/docs",
        "api_v1": settings.API_V1_STR,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }
