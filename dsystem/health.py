"""``/health/live`` and ``/health/ready`` for every service.

Liveness only proves the process answers; readiness checks the dependencies a
request actually needs (Postgres, Redis, RabbitMQ) and returns 503 with the
failing component named so Swarm stops routing to the replica.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

Check = Callable[[], Awaitable[bool]]


def db_check(session_factory: async_sessionmaker) -> Check:
    async def _check() -> bool:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True

    return _check


async def redis_check() -> bool:
    from dsystem.dependencies._settings import get_redis

    redis = await get_redis()
    return bool(await redis.ping())


async def rabbitmq_check() -> bool:
    from dsystem.events import publisher

    channel = publisher._channel
    return channel is not None and not channel.is_closed


async def readiness(checks: dict[str, Check]) -> tuple[dict, int]:
    report: dict[str, str] = {}
    healthy = True
    for name, check in checks.items():
        try:
            ok = await check()
        except Exception as exc:
            logger.warning("readiness check %s failed: %s", name, exc)
            ok = False
        report[name] = "ok" if ok else "unavailable"
        healthy = healthy and ok
    body = {"status": "ok" if healthy else "degraded", **report}
    return body, status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE


def health_router(session_factory: async_sessionmaker, *, redis: bool = True, rabbitmq: bool = True) -> APIRouter:
    router = APIRouter(tags=["health"])
    checks: dict[str, Check] = {"db": db_check(session_factory)}
    if redis:
        checks["redis"] = redis_check
    if rabbitmq:
        checks["rabbitmq"] = rabbitmq_check

    @router.get("/health/live", include_in_schema=False)
    async def liveness():
        return JSONResponse({"status": "alive"}, status_code=status.HTTP_200_OK)

    @router.get("/health/ready", include_in_schema=False)
    async def ready():
        body, code = await readiness(checks)
        return JSONResponse(body, status_code=code)

    @router.get("/health", include_in_schema=False)
    async def health():
        body, code = await readiness({"db": checks["db"]})
        return JSONResponse(body, status_code=code)

    return router
