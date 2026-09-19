from dsystem.clients.service import ServiceClient
from dsystem.dependencies.service_auth import set_service_secret


def test_client_uses_the_secret_the_process_was_started_with(monkeypatch):
    monkeypatch.delenv("SERVICE_SECRET_KEY", raising=False)
    set_service_secret("from-settings")
    try:
        assert ServiceClient("http://auth")._headers()["X-Service-Secret"] == "from-settings"
    finally:
        set_service_secret("")


def test_environment_still_wins_for_scripts(monkeypatch):
    monkeypatch.setenv("SERVICE_SECRET_KEY", "from-env")
    set_service_secret("from-settings")
    try:
        assert ServiceClient("http://auth")._headers()["X-Service-Secret"] == "from-env"
    finally:
        set_service_secret("")


def test_explicit_secret_beats_both(monkeypatch):
    monkeypatch.setenv("SERVICE_SECRET_KEY", "from-env")
    set_service_secret("from-settings")
    try:
        assert ServiceClient("http://auth", service_secret="explicit")._headers()["X-Service-Secret"] == "explicit"
    finally:
        set_service_secret("")


def test_missing_secret_is_empty_not_a_crash(monkeypatch):
    monkeypatch.delenv("SERVICE_SECRET_KEY", raising=False)
    set_service_secret("")
    assert ServiceClient("http://auth")._headers()["X-Service-Secret"] == ""
