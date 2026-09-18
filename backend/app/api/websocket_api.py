import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.app.core.events import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Real-time Streaming WebSockets"])


@router.websocket("/ws/incidents/{incident_id}")
async def websocket_incident_stream(websocket: WebSocket, incident_id: str):
    """WebSocket stream for real-time AI reasoning, tool calls, and hypothesis updates."""
    await websocket.accept()
    logger.info(f"WebSocket client connected for incident: {incident_id}")

    # Send initial connection confirmation
    await websocket.send_json({
        "event_type": "CONNECTED",
        "incident_id": incident_id,
        "message": f"Connected to live stream for incident {incident_id}",
    })

    subscriber_task = None
    try:
        async def _stream_events():
            async for event in event_bus.subscribe(incident_id):
                await websocket.send_json(event)

        subscriber_task = asyncio.create_task(_stream_events())

        # Keep connection open and handle incoming pings/messages from client
        while True:
            data = await websocket.receive_text()
            # Respond to client ping or acknowledge
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await websocket.send_json({"type": "PONG"})
            except Exception:
                pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for incident: {incident_id}")
    except Exception as err:
        logger.warning(f"WebSocket error for incident {incident_id}: {err}")
    finally:
        if subscriber_task and not subscriber_task.done():
            subscriber_task.cancel()


@router.websocket("/ws/chaos")
async def websocket_chaos_stream(websocket: WebSocket):
    """WebSocket stream for real-time chaos injection and remediation events."""
    await websocket.accept()
    subscriber_task = None
    try:
        async def _stream_chaos():
            async for event in event_bus.subscribe("chaos_events"):
                await websocket.send_json(event)

        subscriber_task = asyncio.create_task(_stream_chaos())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as err:
        logger.warning(f"Chaos WebSocket error: {err}")
    finally:
        if subscriber_task and not subscriber_task.done():
            subscriber_task.cancel()
