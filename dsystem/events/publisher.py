import asyncio
import contextlib
import json
import logging

import aio_pika

from dsystem.events import connection
from dsystem.observability import record_event_published

logger = logging.getLogger(__name__)

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_retry_task: asyncio.Task | None = None


async def _open(rabbitmq_url: str):
    global _connection, _channel
    conn = await aio_pika.connect_robust(rabbitmq_url)
    try:
        channel = await conn.channel()
        await channel.declare_exchange("dsystem.events", aio_pika.ExchangeType.TOPIC, durable=True)
        await channel.declare_exchange("dsystem.rpc", aio_pika.ExchangeType.DIRECT, durable=True)
    except BaseException:
        await conn.close()
        raise
    _connection, _channel = conn, channel
    logger.info("RabbitMQ connected")


async def _open_when_up(rabbitmq_url: str):
    await asyncio.sleep(connection.RETRY_INITIAL_S)
    await connection.retry_until_connected(lambda: _open(rabbitmq_url), "events publisher")


async def connect(rabbitmq_url: str):
    """Connect, or keep trying in the background so startup is never blocked on the broker.

    Once connected, the robust connection restores itself after a broker restart; this only
    covers a first attempt that fails, which ``connect_robust`` does not retry on its own.
    """
    global _retry_task
    try:
        await _open(rabbitmq_url)
    except Exception as e:
        logger.warning("RabbitMQ not available: %s. Events paused, retrying in the background.", e)
        _retry_task = asyncio.create_task(_open_when_up(rabbitmq_url))


async def disconnect():
    global _connection, _channel, _retry_task
    if _retry_task:
        _retry_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _retry_task
    if _connection:
        await _connection.close()
    _connection = None
    _channel = None
    _retry_task = None
    logger.info("RabbitMQ disconnected")


def is_ready() -> bool:
    """Whether a publish would go out now — false while connecting or while the robust channel reconnects."""
    return _channel is not None and not _channel.is_closed


async def publish(routing_key: str, body: dict, exchange: str = "dsystem.events"):
    if not _channel:
        logger.warning("RabbitMQ not connected, skipping publish: %s", routing_key)
        return

    ex = await _channel.get_exchange(exchange)
    await ex.publish(
        aio_pika.Message(
            body=json.dumps(body, default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
    )
    record_event_published(routing_key)
