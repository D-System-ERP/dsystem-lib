import asyncio
import socket

import pytest

from dsystem import health
from dsystem.events import connection, consumer, outbox, publisher


class FakeQueue:
    async def bind(self, *args, **kwargs):
        return None

    async def consume(self, callback):
        return "consumer-tag"


class FakeChannel:
    is_closed = False

    async def set_qos(self, **kwargs):
        return None

    async def declare_exchange(self, *args, **kwargs):
        return object()

    async def declare_queue(self, *args, **kwargs):
        return FakeQueue()


class FakeConnection:
    def __init__(self):
        self.closed = False

    async def channel(self):
        return FakeChannel()

    async def close(self):
        self.closed = True


class BrokerComingUp:
    """``connect_robust`` that fails like a Swarm DNS name not there yet, then succeeds."""

    def __init__(self, failures: int):
        self.failures = failures
        self.attempts = 0

    async def __call__(self, url):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise socket.gaierror(-2, "Name or service not known")
        return FakeConnection()


@pytest.fixture(autouse=True)
async def _fresh_publisher(monkeypatch):
    monkeypatch.setattr(connection, "RETRY_INITIAL_S", 0.01)
    monkeypatch.setattr(connection, "RETRY_MAX_S", 0.02)
    yield
    await publisher.disconnect()


async def _until(predicate, timeout=2.0):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.005)


async def _ready_report():
    return await health.readiness({"rabbitmq": health.rabbitmq_check})


async def test_a_broker_not_up_at_startup_is_picked_up_without_a_restart(monkeypatch):
    broker = BrokerComingUp(failures=3)
    monkeypatch.setattr(publisher.aio_pika, "connect_robust", broker)

    await publisher.connect("amqp://guest:guest@rabbitmq/")

    assert not publisher.is_ready() and not outbox._publisher_ready()
    assert await _ready_report() == ({"status": "degraded", "rabbitmq": "unavailable"}, 503)

    await _until(publisher.is_ready)

    assert broker.attempts == 4
    assert outbox._publisher_ready()
    assert await _ready_report() == ({"status": "ok", "rabbitmq": "ok"}, 200)


async def test_shutdown_stops_the_background_retry(monkeypatch):
    broker = BrokerComingUp(failures=10**6)
    monkeypatch.setattr(publisher.aio_pika, "connect_robust", broker)

    await publisher.connect("amqp://guest:guest@rabbitmq/")
    task = publisher._retry_task
    await _until(lambda: broker.attempts >= 3)
    await publisher.disconnect()

    assert task.done()
    attempts = broker.attempts
    await asyncio.sleep(0.05)
    assert broker.attempts == attempts and not publisher.is_ready()


async def test_a_half_open_connection_is_closed_before_the_retry(monkeypatch):
    opened: list[FakeConnection] = []

    class ChannelFails(FakeConnection):
        async def channel(self):
            raise ConnectionError("channel refused")

    async def connect_robust(url):
        conn = ChannelFails() if not opened else FakeConnection()
        opened.append(conn)
        return conn

    monkeypatch.setattr(publisher.aio_pika, "connect_robust", connect_robust)

    await publisher.connect("amqp://guest:guest@rabbitmq/")
    await _until(publisher.is_ready)

    assert opened[0].closed and not opened[1].closed


async def test_a_consumer_waits_for_the_broker_instead_of_dying(monkeypatch):
    broker = BrokerComingUp(failures=2)
    monkeypatch.setattr(consumer.aio_pika, "connect_robust", broker)

    conn = await asyncio.wait_for(
        consumer.start_consumer("amqp://guest:guest@rabbitmq/", "crm-user-sync", ["user.created"], _noop), 2
    )

    assert isinstance(conn, FakeConnection) and broker.attempts == 3


async def _noop(routing_key, body):
    return None
