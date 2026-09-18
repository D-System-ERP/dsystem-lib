import json
import logging
from collections.abc import Callable
from typing import Any

import aio_pika

logger = logging.getLogger(__name__)

EVENTS_EXCHANGE = "dsystem.events"
DLQ_EXCHANGE = "dsystem.events.dlq"


async def start_consumer(
    rabbitmq_url: str,
    queue_name: str,
    routing_keys: list[str],
    handler: Callable[[str, dict[str, Any]], Any],
    exchange: str = EVENTS_EXCHANGE,
    requeue_failed: bool = True,
    dead_letter: bool = True,
    prefetch_count: int = 10,
):
    """Consume an exchange's events, acknowledging each one the handler survives.

    Delivery is at-least-once: a handler that raises sends the message back once
    (``requeue_failed``), and a second failure routes it to ``<queue_name>-dlq``
    on the ``dsystem.events.dlq`` exchange (``dead_letter``) instead of dropping
    it, so nothing is lost silently and the admin panel can replay it. Handlers
    therefore must be idempotent — dedupe by ``event_id`` with ``claim_once``.
    """
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=prefetch_count)

    ex = await channel.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC, durable=True)

    arguments: dict[str, Any] = {}
    if dead_letter:
        dlx = await channel.declare_exchange(DLQ_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        dlq = await channel.declare_queue(f"{queue_name}-dlq", durable=True)
        await dlq.bind(dlx, routing_key="#")
        arguments["x-dead-letter-exchange"] = DLQ_EXCHANGE

    queue = await channel.declare_queue(queue_name, durable=True, arguments=arguments or None)

    for key in routing_keys:
        await queue.bind(ex, routing_key=key)

    async def _process(message: aio_pika.abc.AbstractIncomingMessage):
        try:
            body = json.loads(message.body.decode())
            await handler(message.routing_key, body)
        except Exception:
            logger.exception("Failed to process message: %s", message.routing_key)
            if requeue_failed and not message.redelivered:
                await message.reject(requeue=True)
                return
            if dead_letter:
                await message.reject(requeue=False)
                return
            await message.ack()
            return
        await message.ack()

    await queue.consume(_process)
    logger.info("Consumer started: queue=%s, keys=%s, dlq=%s", queue_name, routing_keys, dead_letter)
    return connection
