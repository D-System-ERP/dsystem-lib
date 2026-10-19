"""Opening a RabbitMQ connection when the broker may not be up yet.

``aio_pika.connect_robust`` only reconnects a connection that was made once: a
first attempt that fails (the broker container still starting, its Swarm DNS
name not there yet) raises and leaves nothing behind to retry. After a node or
docker restart every service starts at the same moment as RabbitMQ, so the
first attempt is retried here with a capped backoff until it lands.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRY_INITIAL_S = 1.0
RETRY_MAX_S = 10.0


async def retry_until_connected(attempt: Callable[[], Awaitable[T]], what: str) -> T:
    """Await ``attempt()`` until it succeeds, sleeping 1s, 2s, 4s, 8s, then every 10s."""
    delay = RETRY_INITIAL_S
    while True:
        try:
            return await attempt()
        except Exception as exc:
            logger.warning("RabbitMQ not available for %s: %s. Retrying in %.0fs.", what, exc, delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, RETRY_MAX_S)
