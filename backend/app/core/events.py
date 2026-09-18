import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Set
import redis.asyncio as aioredis
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class EventBus:
    """Hybrid Event Bus supporting both Redis Pub/Sub and in-memory fallback."""

    def __init__(self):
        self._redis_client = None
        self._redis_available = False
        self._local_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        try:
            self._redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.0,
            )
            # Test ping
            await self._redis_client.ping()
            self._redis_available = True
            logger.info("EventBus connected to Redis Pub/Sub.")
        except Exception as err:
            self._redis_available = False
            logger.warning(
                f"Redis unavailable ({err}). Using in-memory event bus fallback."
            )
        self._initialized = True

    async def broadcast(self, channel: str, payload: dict):
        """Broadcast an event payload to a channel (e.g., incident_id)."""
        if not self._initialized:
            await self.initialize()

        data_str = json.dumps(payload)

        # 1. Publish to Redis if available
        if self._redis_available and self._redis_client:
            try:
                await self._redis_client.publish(channel, data_str)
            except Exception as err:
                logger.warning(f"Failed to publish to Redis: {err}")

        # 2. Publish to local subscribers
        if channel in self._local_subscribers:
            for q in list(self._local_subscribers[channel]):
                try:
                    await q.put(payload)
                except Exception as err:
                    logger.debug(f"Subscriber queue error: {err}")

    async def subscribe(self, channel: str) -> AsyncGenerator[dict, None]:
        """Subscribe to events on a specific channel."""
        if not self._initialized:
            await self.initialize()

        local_queue: asyncio.Queue = asyncio.Queue()
        if channel not in self._local_subscribers:
            self._local_subscribers[channel] = set()
        self._local_subscribers[channel].add(local_queue)

        try:
            while True:
                item = await local_queue.get()
                yield item
        finally:
            if channel in self._local_subscribers:
                self._local_subscribers[channel].discard(local_queue)
                if not self._local_subscribers[channel]:
                    del self._local_subscribers[channel]


event_bus = EventBus()
