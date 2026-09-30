from types import SimpleNamespace
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from fastapi_pagination import Page

from dsystem.models.partner_replica import PartnerReplica
from dsystem.models.user_replica import UserReplica
from dsystem.routes.inline import inline_route
from dsystem.schemas.base import AppSchema
from dsystem.schemas.refs import (
    Inline,
    InlineName,
    PartnerBrief,
    UserBrief,
    has_inline,
    resolve_inline,
    stored_fields,
)


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.queries: list[str] = []

    async def scalars(self, statement):
        table = statement.get_final_froms()[0].name
        self.queries.append(table)
        return [row for row in self.rows if row.table == table]


def partner(pid, name="Acme", *, deleted=False):
    return SimpleNamespace(table=PartnerReplica.__tablename__, id=pid, code="P1", name=name, is_deleted=deleted)


def user(uid, first="Ali"):
    return SimpleNamespace(
        table=UserReplica.__tablename__, id=uid, first_name=first, last_name=None, email="a@x.uz", picture_url=None
    )


class LineRead(AppSchema):
    vendor_id: UUID | None
    vendor: Annotated[PartnerBrief | None, Inline("vendor_id")] = None


class NodeRead(AppSchema):
    partner_id: UUID | None
    partner: Annotated[PartnerBrief | None, Inline("partner_id")] = None
    children: list["NodeRead"] = []


class DocRead(AppSchema):
    partner_id: UUID | None
    partner: Annotated[PartnerBrief | None, Inline("partner_id")] = None
    created_by_id: UUID | None
    created_by: Annotated[UserBrief | None, Inline("created_by_id")] = None
    assignee_ids: list[UUID]
    assignees: Annotated[list[UserBrief], Inline("assignee_ids")] = []
    lines: list[LineRead] = []


class Plain(AppSchema):
    id: UUID


async def test_one_query_per_table_across_rows_and_nested_lines():
    p1, p2, u1, u2 = uuid4(), uuid4(), uuid4(), uuid4()
    session = FakeSession([partner(p1), partner(p2, "Beta"), user(u1), user(u2, "Vali")])
    docs = [
        DocRead(partner_id=p1, created_by_id=u1, assignee_ids=[u1, u2], lines=[LineRead(vendor_id=p2)]),
        DocRead(partner_id=p2, created_by_id=None, assignee_ids=[u2], lines=[LineRead(vendor_id=None)]),
    ]
    await resolve_inline(session, docs)
    assert sorted(session.queries) == ["partner_replicas", "user_replicas"]
    assert docs[0].partner.name == "Acme"
    assert docs[0].lines[0].vendor.name == "Beta"
    assert [a.first_name for a in docs[0].assignees] == ["Ali", "Vali"]
    assert docs[1].created_by is None
    assert docs[1].lines[0].vendor is None


async def test_soft_deleted_partner_still_resolves_and_deleted_user_drops_out():
    p1, gone = uuid4(), uuid4()
    session = FakeSession([partner(p1, deleted=True)])
    doc = DocRead(partner_id=p1, created_by_id=gone, assignee_ids=[gone])
    await resolve_inline(session, doc)
    assert doc.partner.id == p1
    assert doc.created_by is None
    assert doc.assignees == []


async def test_no_ids_means_no_query():
    session = FakeSession([])
    doc = DocRead(partner_id=None, created_by_id=None, assignee_ids=[])
    await resolve_inline(session, doc)
    assert session.queries == []
    assert doc.partner is None


async def test_recursive_tree_is_walked():
    p1, p2 = uuid4(), uuid4()
    session = FakeSession([partner(p1), partner(p2, "Beta")])
    tree = NodeRead(partner_id=p1, children=[NodeRead(partner_id=p2)])
    await resolve_inline(session, tree)
    assert session.queries == ["partner_replicas"]
    assert tree.children[0].partner.name == "Beta"


def test_has_inline():
    assert has_inline(DocRead)
    assert has_inline(Page[DocRead])
    assert has_inline(list[NodeRead])
    assert not has_inline(Plain)


def _app(session):
    async def get_db():
        yield session

    router = APIRouter(route_class=inline_route(get_db))

    @router.get("/docs/{pid}")
    async def read(pid: UUID, db: Annotated[object, Depends(get_db)]) -> DocRead:
        assert db is session
        return DocRead(partner_id=pid, created_by_id=None, assignee_ids=[])

    @router.get("/rows")
    async def rows() -> list[LineRead]:
        return [SimpleNamespace(vendor_id=pid) for pid in session.vendor_ids]

    @router.get("/plain")
    async def plain() -> Plain:
        return Plain(id=uuid4())

    parent = APIRouter(prefix="/api")
    parent.include_router(router)
    app = FastAPI()
    app.include_router(parent)
    return app


def test_route_fills_objects_with_the_request_session():
    pid = uuid4()
    session = FakeSession([partner(pid)])
    session.vendor_ids = [pid]
    client = TestClient(_app(session))
    body = client.get(f"/api/docs/{pid}").json()
    assert body["partner"] == {"id": str(pid), "code": "P1", "name": "Acme"}
    assert body["partner_id"] == str(pid)
    rows = client.get("/api/rows").json()
    assert rows[0]["vendor"]["name"] == "Acme"
    assert client.get("/api/plain").status_code == 200


def test_openapi_shows_objects_and_hides_the_session():
    session = FakeSession([])
    schema = TestClient(_app(session)).get("/openapi.json").json()
    params = schema["paths"]["/api/docs/{pid}"]["get"]["parameters"]
    assert [p["name"] for p in params] == ["pid"]
    doc = schema["components"]["schemas"]["DocRead"]["properties"]
    assert "partner" in doc and "assignees" in doc


def test_stored_fields_leave_out_inline_objects():
    assert stored_fields(DocRead) == ["partner_id", "created_by_id", "assignee_ids", "lines"]


class LinkRead(AppSchema):
    target_type: str
    target_id: UUID
    target_name: Annotated[
        str | None,
        InlineName(
            "target_id", by="target_type", briefs={"partner": (PartnerBrief, "name"), "user": (UserBrief, "email")}
        ),
    ] = None


async def test_a_polymorphic_link_is_named_by_its_type():
    p1, u1 = uuid4(), uuid4()
    session = FakeSession([partner(p1), user(u1)])
    links = [
        LinkRead(target_type="partner", target_id=p1),
        LinkRead(target_type="user", target_id=u1),
        LinkRead(target_type="document", target_id=uuid4()),
        LinkRead(target_type="partner", target_id=uuid4()),
    ]
    await resolve_inline(session, links)
    assert [link.target_name for link in links] == ["Acme", "a@x.uz", None, None]
    assert sorted(session.queries) == ["partner_replicas", "user_replicas"]
    assert stored_fields(LinkRead) == ["target_type", "target_id"]
