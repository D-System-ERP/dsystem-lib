import asyncio

import pytest

from dsystem import health


@pytest.mark.asyncio
async def test_a_hanging_dependency_is_reported_instead_of_hanging_readiness(monkeypatch):
    monkeypatch.setattr(health, "CHECK_TIMEOUT_S", 0.05)

    async def hangs() -> bool:
        await asyncio.sleep(10)
        return True

    async def fine() -> bool:
        return True

    body, status_code = await asyncio.wait_for(health.readiness({"db": hangs, "redis": fine}), 1)

    assert status_code == 503 and body == {"status": "degraded", "db": "unavailable", "redis": "ok"}
