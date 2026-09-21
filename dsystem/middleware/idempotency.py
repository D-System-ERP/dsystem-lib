"""``Idempotency-Key`` middleware — a retried mutation returns the first response, not a second effect.

The client sends a unique key per logical operation; the first request runs and
its response (status, headers, body) is cached in Redis for ``ttl_seconds``. A
repeat with the same key and the same body returns that cached response; the
same key with a different body is refused (``422 idempotency.key_reused``).
Keys are scoped to the caller's token (org + user) so tenants cannot collide.
"""

from __future__ import annotations

import hashlib
import json
import logging

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from dsystem.dependencies._settings import get_jwt_secret
from dsystem.i18n import get_language, translate

logger = logging.getLogger(__name__)

HEADER = "Idempotency-Key"
_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_LOCK_TTL = 30
_KEY_REUSED = "idempotency.key_reused"
_KEY_REUSED_MESSAGE = "Idempotency-Key was already used with a different payload"
_IN_PROGRESS = "idempotency.in_progress"
_IN_PROGRESS_MESSAGE = "The same request is still being processed"


def _error(request: Request, status_code: int, key: str, fallback: str) -> JSONResponse:
    """Answer in the caller's language: middleware runs before the app's handlers can translate."""
    message = translate(key, get_language(request)) or fallback
    return JSONResponse(
        status_code=status_code,
        content={"code": key, "key": key, "message": message, "params": {}, "detail": message},
    )


def _caller_scope(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return "anon"
    try:
        payload = jwt.decode(auth[7:], get_jwt_secret(), algorithms=["HS256"])
    except (jwt.PyJWTError, RuntimeError):
        return "anon"
    return f"{payload.get('org_id')}:{payload.get('user_id')}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, ttl_seconds: int = 86400, prefix: str = "idem"):
        super().__init__(app)
        self.ttl = ttl_seconds
        self.prefix = prefix

    async def dispatch(self, request: Request, call_next):
        key = request.headers.get(HEADER)
        if not key or request.method not in _METHODS:
            return await call_next(request)

        body = await request.body()
        body_hash = hashlib.sha256(body).hexdigest()
        redis_key = f"{self.prefix}:{_caller_scope(request)}:{request.method}:{request.url.path}:{key}"

        try:
            from dsystem.dependencies._settings import get_redis

            redis = await get_redis()
            cached = await redis.get(redis_key)
        except Exception as exc:
            logger.warning("idempotency lookup failed, running request: %s", exc)
            return await call_next(request)

        if cached:
            record = json.loads(cached)
            if record.get("body_hash") != body_hash:
                return _error(request, 422, _KEY_REUSED, _KEY_REUSED_MESSAGE)
            if record.get("status") == "in_progress":
                return _error(request, 409, _IN_PROGRESS, _IN_PROGRESS_MESSAGE)
            headers = dict(record.get("headers") or {})
            headers["Idempotent-Replayed"] = "true"
            return Response(
                content=record.get("body", ""),
                status_code=int(record.get("status_code", 200)),
                headers=headers,
                media_type=record.get("media_type"),
            )

        claimed = await redis.set(
            redis_key, json.dumps({"status": "in_progress", "body_hash": body_hash}), nx=True, ex=_LOCK_TTL
        )
        if not claimed:
            return _error(request, 409, _IN_PROGRESS, _IN_PROGRESS_MESSAGE)

        response = await call_next(request)
        chunks = [chunk async for chunk in response.body_iterator]
        payload = b"".join(chunks)

        if 200 <= response.status_code < 500:
            record = {
                "status": "done",
                "body_hash": body_hash,
                "status_code": response.status_code,
                "headers": {k: v for k, v in response.headers.items() if k.lower() not in ("content-length",)},
                "media_type": response.media_type,
                "body": payload.decode("utf-8", errors="replace"),
            }
            try:
                await redis.set(redis_key, json.dumps(record), ex=self.ttl)
            except Exception as exc:
                logger.warning("idempotency store failed: %s", exc)
        else:
            try:
                await redis.delete(redis_key)
            except Exception:
                pass

        return Response(
            content=payload,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
