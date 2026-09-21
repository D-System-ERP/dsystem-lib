from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from dsystem.exceptions import AppException
from dsystem.handlers import register_handlers


class Line(BaseModel):
    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., ge=0, le=100)


def _app() -> FastAPI:
    app = FastAPI()
    register_handlers(app)

    @app.post("/lines")
    async def create(line: Line) -> dict:
        return {}

    @app.get("/boom")
    async def boom() -> dict:
        raise AppException(409, code="x.y", key="x.y", params={"amount": Decimal("1.50"), "id": uuid4()})

    return app


@pytest.mark.asyncio
async def test_decimal_constraints_render_as_422_with_limits():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as client:
        response = await client.post("/lines", json={"quantity": "0", "price": "150"})
    assert response.status_code == 422
    params = {item["loc"]: item["params"] for item in response.json()["errors"]}
    assert params["quantity"]["limit"] == "0"
    assert params["price"]["limit"] == "100"


@pytest.mark.asyncio
async def test_app_exception_params_are_json_safe():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as client:
        response = await client.get("/boom")
    assert response.status_code == 409
    assert response.json()["params"]["amount"] == "1.50"
