import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from dsystem.handlers import register_handlers

ORIGIN = "https://demo.dsystem.uz"


def _app() -> FastAPI:
    app = FastAPI()
    register_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True, allow_methods=["*"])

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("unexpected")

    return app


@pytest.mark.asyncio
async def test_an_unhandled_error_is_a_500_envelope_the_browser_can_read():
    async with AsyncClient(transport=ASGITransport(app=_app(), raise_app_exceptions=False), base_url="http://t") as c:
        response = await c.get("/boom", headers={"Origin": ORIGIN})

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == ORIGIN
    assert response.json()["code"] == "INTERNAL_ERROR"
