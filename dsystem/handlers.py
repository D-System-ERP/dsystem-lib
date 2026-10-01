from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dsystem.clients.service import RemoteServiceError
from dsystem.exceptions import AppException
from dsystem.i18n import bind_locale_dir, get_language, translate
from dsystem.observability import capture_exception as _sentry_capture
from dsystem.observability import init_sentry

_log = logging.getLogger(__name__)

_MIRRORED_UPSTREAM_STATUSES = frozenset({400, 409, 422})

_INTEGRITY_CODES = {
    "23505": ("CONFLICT", "common.unique_violation", status.HTTP_409_CONFLICT, "Record already exists"),
    "23503": ("CONFLICT", "common.reference_in_use", status.HTTP_409_CONFLICT, "Record is referenced elsewhere"),
    "23514": (
        "VALIDATION_ERROR",
        "common.check_violation",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Value violates a rule",
    ),
}


def _json_safe(params: dict | None) -> dict:
    """Decimal / UUID / date values (constraint limits, ids) become strings instead of breaking the response."""
    return json.loads(json.dumps(params or {}, default=str))


def _envelope(code: str, key: str, lang: str, params: dict | None, fallback: str) -> dict:
    params = _json_safe(params)
    message = translate(key, lang, params) or fallback
    return {
        "code": code,
        "key": key,
        "message": message,
        "params": params,
        "detail": message,
    }


def _classify_validation_error(msg: str, typ: str, loc: str, ctx: dict) -> tuple[str, str, dict]:
    if msg in ("Field required", "Missing required field"):
        return "FIELD_REQUIRED", "validation.field_required", {"field": loc}
    lower = msg.lower()
    if "valid email" in lower:
        return "EMAIL_INVALID", "validation.email_invalid", {"field": loc}
    if "min_length" in typ:
        return "MIN_LENGTH", "validation.min_length", {"field": loc, "min": ctx.get("min_length")}
    if "max_length" in typ:
        return "MAX_LENGTH", "validation.max_length", {"field": loc, "max": ctx.get("max_length")}
    if "Value error" in msg:
        reason = msg.split("Value error, ")[-1] if "Value error, " in msg else msg
        return "VALUE_ERROR", "validation.value_error", {"field": loc, "reason": reason}
    if "pattern" in typ:
        return "PATTERN_MISMATCH", "validation.pattern_mismatch", {"field": loc}
    if "greater_than" in typ:
        return "TOO_SMALL", "validation.too_small", {"field": loc, "limit": ctx.get("gt", ctx.get("ge"))}
    if "less_than" in typ:
        return "TOO_LARGE", "validation.too_large", {"field": loc, "limit": ctx.get("lt", ctx.get("le"))}
    return "INVALID", "validation.invalid_value", {"field": loc, "reason": msg}


def _format_validation_errors(exc: RequestValidationError, lang: str) -> list[dict]:
    items = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        code, key, params = _classify_validation_error(
            err.get("msg", ""),
            err.get("type", "value_error"),
            loc,
            err.get("ctx") or {},
        )
        params = _json_safe(params)
        items.append(
            {
                "loc": loc,
                "code": code,
                "key": key,
                "message": translate(key, lang, params) or err.get("msg", "Invalid"),
                "params": params,
            }
        )
    return items


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    lang = get_language(request)
    envelope = _envelope(
        "VALIDATION_ERROR",
        "validation.multiple_errors",
        lang,
        {},
        "Validation failed",
    )
    envelope["errors"] = _format_validation_errors(exc, lang)
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=envelope)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    lang = get_language(request)
    fallback = exc.detail if isinstance(exc.detail, str) else exc.key
    envelope = _envelope(exc.code, exc.key, lang, exc.params, fallback)
    return JSONResponse(status_code=exc.status_code, content=envelope)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    lang = get_language(request)
    code = f"HTTP_{exc.status_code}"
    key = f"common.http_{exc.status_code}"
    if isinstance(exc.detail, dict):
        detail = exc.detail
        fallback = detail.get("detail") or detail.get("message") or detail.get("error") or "Error"
        params = {k: v for k, v in detail.items() if k not in ("detail", "message", "error")}
    else:
        fallback = exc.detail if isinstance(exc.detail, str) else "Error"
        params = {}
    envelope = _envelope(code, key, lang, params, fallback)
    return JSONResponse(status_code=exc.status_code, content=envelope)


def _upstream_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:500] or "Upstream request failed"
    if isinstance(body, dict):
        for field in ("message", "detail", "error"):
            value = body.get(field)
            if isinstance(value, str) and value:
                return value
    return str(body)[:500]


def _upstream_target(exc: httpx.HTTPError) -> str:
    try:
        return exc.request.url.host
    except RuntimeError:
        return "upstream"


def _mirrored_envelope(status_code: int, body: dict | None, detail: str, lang: str) -> dict:
    if isinstance(body, dict) and isinstance(body.get("code"), str) and isinstance(body.get("key"), str):
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        upstream_message = body.get("message") if isinstance(body.get("message"), str) else detail
        envelope = _envelope(body["code"], body["key"], lang, params, upstream_message)
        if isinstance(body.get("errors"), list):
            envelope["errors"] = body["errors"]
        return envelope
    return _envelope(f"HTTP_{status_code}", f"common.http_{status_code}", lang, {}, detail)


def _response_body(response: httpx.Response) -> dict | None:
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


async def upstream_exception_handler(request: Request, exc: httpx.HTTPError) -> JSONResponse:
    lang = get_language(request)
    response = getattr(exc, "response", None)
    upstream_status = response.status_code if response is not None else None

    if upstream_status in _MIRRORED_UPSTREAM_STATUSES:
        envelope = _mirrored_envelope(upstream_status, _response_body(response), _upstream_detail(response), lang)
        return JSONResponse(status_code=upstream_status, content=envelope)

    _sentry_capture(exc)
    _log.error("Upstream call from %s %s failed: %s", request.method, request.url.path, exc)
    envelope = _envelope(
        "UPSTREAM_UNAVAILABLE",
        "common.upstream_unavailable",
        lang,
        {"service": _upstream_target(exc)},
        "Upstream service is unavailable",
    )
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=envelope)


async def remote_service_exception_handler(request: Request, exc: RemoteServiceError) -> JSONResponse:
    lang = get_language(request)
    if exc.status_code in _MIRRORED_UPSTREAM_STATUSES:
        envelope = _mirrored_envelope(exc.status_code, exc.body, exc.detail, lang)
        return JSONResponse(status_code=exc.status_code, content=envelope)
    _sentry_capture(exc)
    _log.error("Upstream call from %s %s failed: %s", request.method, request.url.path, exc)
    envelope = _envelope(
        "UPSTREAM_UNAVAILABLE",
        "common.upstream_unavailable",
        lang,
        {"service": exc.service},
        "Upstream service is unavailable",
    )
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=envelope)


def _constraint_name(exc: IntegrityError) -> str | None:
    origin = getattr(exc, "orig", None)
    for attr in ("constraint_name",):
        value = getattr(origin, attr, None)
        if value:
            return str(value)
    cause = getattr(origin, "__cause__", None)
    value = getattr(cause, "constraint_name", None)
    return str(value) if value else None


async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    origin = getattr(exc, "orig", None)
    pgcode = getattr(origin, "pgcode", None) or getattr(origin, "sqlstate", None)
    mapping = _INTEGRITY_CODES.get(str(pgcode)) if pgcode else None
    if mapping is None:
        return await fallback_handler(request, exc)
    code, key, http_status, fallback = mapping
    lang = get_language(request)
    params = {"constraint": _constraint_name(exc)}
    _log.warning("Integrity error on %s %s: %s", request.method, request.url.path, params["constraint"])
    return JSONResponse(status_code=http_status, content=_envelope(code, key, lang, params, fallback))


async def fallback_handler(request: Request, exc: Exception) -> JSONResponse:
    _sentry_capture(exc)
    _log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    lang = get_language(request)
    envelope = _envelope(
        "INTERNAL_ERROR",
        "common.internal_error",
        lang,
        {},
        "Internal server error",
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=envelope)


class UnhandledErrorMiddleware:
    """Answers an unhandled exception inside the middleware stack, so CORS and the request id still wrap the 500.

    Starlette runs the ``Exception`` handler in ``ServerErrorMiddleware``, outside every user middleware: that
    500 leaves without ``Access-Control-Allow-Origin`` and the browser reports a network failure instead.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            if started:
                raise
            response = await fallback_handler(Request(scope), exc)
            await response(scope, receive, send)


def register_handlers(app: FastAPI, locale_dir: Path | str | None = None) -> None:
    init_sentry()
    if locale_dir is not None:
        bind_locale_dir(locale_dir)
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(httpx.HTTPError, upstream_exception_handler)
    app.add_exception_handler(RemoteServiceError, remote_service_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_exception_handler)
    app.add_exception_handler(Exception, fallback_handler)
