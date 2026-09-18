from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Awaitable, Callable, TypeVar

from dsystem.dependencies._settings import get_redis

T = TypeVar("T")

log = logging.getLogger("dsystem.cache")


def _default_serialize(value: Any) -> str:
    return json.dumps(value, default=str)


def _default_deserialize(raw: str) -> Any:
    return json.loads(raw)


async def cache_aside(
    key: str,
    loader: Callable[[], Awaitable[T]],
    ttl: int = 300,
    *,
    serialize: Callable[[T], str] = _default_serialize,
    deserialize: Callable[[str], T] = _default_deserialize,
) -> T:
    try:
        redis = await get_redis()
        cached = await redis.get(key)
        if cached is not None:
            return deserialize(cached)
    except Exception as exc:
        log.warning("cache_get_failed key=%s err=%s", key, exc)

    value = await loader()

    try:
        redis = await get_redis()
        await redis.setex(key, ttl, serialize(value))
    except Exception as exc:
        log.warning("cache_set_failed key=%s err=%s", key, exc)

    return value


async def cache_invalidate(*keys: str) -> None:
    if not keys:
        return
    try:
        redis = await get_redis()
        await redis.delete(*keys)
    except Exception as exc:
        log.warning("cache_invalidate_failed keys=%s err=%s", keys, exc)


async def cache_set(
    key: str,
    value: Any,
    ttl: int = 300,
    *,
    serialize: Callable[[Any], str] = _default_serialize,
) -> None:
    try:
        redis = await get_redis()
        await redis.setex(key, ttl, serialize(value))
    except Exception as exc:
        log.warning("cache_set_failed key=%s err=%s", key, exc)


async def cache_set_many(
    entries: Mapping[str, Any],
    ttl: int = 300,
    *,
    serialize: Callable[[Any], str] = _default_serialize,
) -> None:
    """Write many keys in one round trip.

    A role reassignment stamps every touched user; issued one ``SETEX`` at a
    time that is one network round trip per user, inside the request.
    """
    if not entries:
        return
    try:
        redis = await get_redis()
        pipe = redis.pipeline(transaction=False)
        for key, value in entries.items():
            pipe.setex(key, ttl, serialize(value))
        await pipe.execute()
    except Exception as exc:
        log.warning("cache_set_many_failed keys=%d err=%s", len(entries), exc)


async def cache_get(key: str) -> str | None:
    try:
        redis = await get_redis()
        return await redis.get(key)
    except Exception:
        return None


async def claim_once(key: str, ttl: int = 7 * 24 * 3600, *, namespace: str = "evt") -> bool:
    """Atomically claim ``key`` for ``ttl`` seconds; ``False`` when it was already claimed.

    The event-consumer dedupe primitive: the outbox stamps every message with a
    stable ``event_id``, so the second delivery of the same event loses the
    claim and is dropped. Fails open (returns ``True``) when Redis is unreachable —
    a duplicate is safer than a lost event, and handlers are idempotent anyway.
    """
    try:
        redis = await get_redis()
        return bool(await redis.set(f"{namespace}:{key}", "1", nx=True, ex=ttl))
    except Exception as exc:
        log.warning("claim_once_failed key=%s err=%s", key, exc)
        return True


async def release_claim(key: str, *, namespace: str = "evt") -> None:
    """Give back a ``claim_once`` claim after the handler failed, so the redelivery (or DLQ replay) is processed."""
    await cache_invalidate(f"{namespace}:{key}")


async def run_claimed(key: str | None, namespace: str, handler, *args) -> None:
    """Run ``handler(*args)`` once per ``key``; a raising handler releases the claim before re-raising."""
    if key and not await claim_once(key, namespace=namespace):
        return
    try:
        await handler(*args)
    except Exception:
        if key:
            await release_claim(key, namespace=namespace)
        raise
