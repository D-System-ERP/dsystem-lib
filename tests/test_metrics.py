import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from dsystem.observability import record_event_consumed, record_event_published, set_outbox_pending, setup_metrics


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict:
        return {"ok": True}

    @app.get("/health/live")
    async def live() -> dict:
        return {"status": "ok"}

    @app.get("/conflict")
    async def conflict() -> dict:
        raise HTTPException(status_code=409)

    assert setup_metrics(app) is True
    return app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(_app())


@pytest.fixture(scope="module")
def scrape(client) -> str:
    client.get("/ping")
    client.get("/conflict")
    client.get("/missing")
    client.get("/health/live")
    record_event_published("partner.created")
    record_event_consumed("partner.created", "ok")
    record_event_consumed("partner.created", "error")
    set_outbox_pending(7)
    return client.get("/metrics").text


def test_exposes_the_names_the_dashboards_query(scrape):
    assert 'http_requests_total{handler="/ping",method="GET",status="200"}' in scrape
    assert "http_request_duration_seconds_bucket" in scrape
    assert "http_requests_inprogress" in scrape


def test_status_codes_stay_ungrouped_so_the_5xx_alert_can_match(scrape):
    assert 'status="4xx"' not in scrape
    assert 'status="409"' in scrape


def test_untemplated_paths_are_dropped_instead_of_growing_the_label_set(scrape):
    assert "/missing" not in scrape


def test_health_and_metrics_are_not_instrumented(scrape):
    assert "/health/live" not in scrape
    assert 'handler="/metrics"' not in scrape


def test_metrics_endpoint_is_hidden_from_the_openapi_schema(client):
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]


def test_domain_counters_are_exported(scrape):
    assert 'dsystem_events_published_total{event_type="partner.created"} 1.0' in scrape
    assert 'dsystem_events_consumed_total{event_type="partner.created",status="ok"} 1.0' in scrape
    assert 'dsystem_events_consumed_total{event_type="partner.created",status="error"} 1.0' in scrape
    assert "dsystem_outbox_pending 7.0" in scrape


def test_a_second_app_in_the_same_process_still_gets_the_endpoint():
    second = TestClient(_app())

    assert "http_requests_total" in second.get("/metrics").text
