from __future__ import annotations

import asyncio
import logging
import os

_log = logging.getLogger(__name__)
_initialized = False


def init_sentry() -> bool:
    global _initialized
    if _initialized:
        return True

    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
    except ImportError:
        _log.warning("SENTRY_DSN is set but sentry-sdk is not installed; error tracking disabled")
        return False

    integrations = []
    try:
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        integrations.extend([StarletteIntegration(), FastApiIntegration()])
    except Exception:
        pass
    try:
        from sentry_sdk.integrations.celery import CeleryIntegration

        integrations.append(CeleryIntegration(monitor_beat_tasks=False, propagate_traces=False))
    except Exception:
        pass

    service = os.environ.get("SERVICE_NAME", "unknown")
    environment = os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or "production"

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        server_name=service,
        release=os.environ.get("RELEASE_SHA") or None,
        integrations=integrations,
        traces_sample_rate=0.0,
        send_default_pii=False,
        max_request_body_size="small",
        before_send=_enrich_event,
    )
    _initialized = True
    _log.info("Sentry error tracking initialised (service=%s env=%s)", service, environment)
    return True


_METRICS_ENDPOINT = "/metrics"
_UNINSTRUMENTED = ["/metrics", "/health/live", "/health/ready"]

_instrumented = False
_events_published = None
_events_consumed = None
_outbox_pending = None


def _domain_metrics() -> None:
    """Create the ``dsystem_*`` collectors once, on the first service that asks.

    Registering them at import time would double-register under Celery's fork,
    where the module is re-imported into a process that already inherited the
    parent's default registry.
    """
    global _events_published, _events_consumed, _outbox_pending
    if _events_published is not None:
        return
    try:
        from prometheus_client import Counter, Gauge
    except ImportError:
        return
    _events_published = Counter("dsystem_events_published_total", "Domain events handed to RabbitMQ", ["event_type"])
    _events_consumed = Counter(
        "dsystem_events_consumed_total", "Domain events processed by a consumer", ["event_type", "status"]
    )
    _outbox_pending = Gauge("dsystem_outbox_pending", "Outbox rows still waiting for the relay")


def setup_metrics(app) -> bool:
    """Expose ``/metrics`` in the shape ``infra/monitoring`` scrapes.

    Status codes stay ungrouped: the 5xx alert matches ``status=~"5.."``, which a
    grouped ``5xx`` label would never satisfy.

    The HTTP collectors are installed once per process. A service that builds a
    second app — a Celery worker importing ``app.main``, a test suite — would
    otherwise re-register them and die on ``DuplicateTimeseries`` at import time;
    the later app still gets the endpoint, serving the same registry.
    """
    global _instrumented
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:
        _log.warning("prometheus-fastapi-instrumentator is not installed; %s disabled", _METRICS_ENDPOINT)
        return False

    _domain_metrics()
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=_UNINSTRUMENTED,
        inprogress_name="http_requests_inprogress",
        should_instrument_requests_inprogress=True,
        inprogress_labels=False,
    )
    if not _instrumented:
        instrumentator.instrument(app)
        _instrumented = True
    instrumentator.expose(app, endpoint=_METRICS_ENDPOINT, include_in_schema=False)
    _log.info("Prometheus metrics exposed at %s", _METRICS_ENDPOINT)
    return True


def record_event_published(routing_key: str) -> None:
    if _events_published is not None:
        _events_published.labels(event_type=routing_key).inc()


def record_event_consumed(routing_key: str, status: str) -> None:
    if _events_consumed is not None:
        _events_consumed.labels(event_type=routing_key, status=status).inc()


def set_outbox_pending(count: int) -> None:
    if _outbox_pending is not None:
        _outbox_pending.set(count)


def _is_cancellation(exc: BaseException | None) -> bool:
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, asyncio.CancelledError):
            return True
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return False


def _enrich_event(event: dict, hint: dict) -> dict | None:
    hint = hint or {}
    record = hint.get("log_record")
    if record is not None and not record.exc_info:
        return None

    exc_info = hint.get("exc_info") or (record.exc_info if record is not None else None)
    if exc_info and _is_cancellation(exc_info[1]):
        return None
    try:
        from dsystem.context import get_audit_context

        ctx = get_audit_context()
        tags = event.setdefault("tags", {})
        tags.setdefault("service", os.environ.get("SERVICE_NAME", "unknown"))
        if ctx.organization_id:
            tags["organization_id"] = str(ctx.organization_id)
        if ctx.request_id:
            tags["request_id"] = str(ctx.request_id)
        if ctx.user and (ctx.user.id or ctx.user.email):
            user = event.setdefault("user", {})
            if ctx.user.id:
                user.setdefault("id", str(ctx.user.id))
            if ctx.user.email:
                user.setdefault("email", ctx.user.email)
    except Exception:
        pass
    return event


def capture_exception(exc: BaseException) -> None:
    if not _initialized:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        pass


def install_celery_signals() -> bool:
    try:
        from celery.signals import worker_process_init
    except ImportError:
        return False

    def _init_in_worker(**_kwargs) -> None:
        global _initialized
        _initialized = False
        init_sentry()

    worker_process_init.connect(_init_in_worker, weak=False)
    return True
