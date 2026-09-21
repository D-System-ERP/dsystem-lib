import pytest

from dsystem.dependencies import _settings


@pytest.fixture
def unconfigured(monkeypatch):
    monkeypatch.setattr(_settings, "_jwt_secret", None)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)


def test_missing_jwt_secret_refuses_to_fall_back(unconfigured):
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _settings.get_jwt_secret()


def test_empty_jwt_secret_env_is_not_a_secret(unconfigured, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _settings.get_jwt_secret()


def test_jwt_secret_comes_from_env(unconfigured, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "from-env")
    assert _settings.get_jwt_secret() == "from-env"


def test_set_jwt_secret_wins_over_env(unconfigured, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "from-env")
    _settings.set_jwt_secret("configured")
    assert _settings.get_jwt_secret() == "configured"
