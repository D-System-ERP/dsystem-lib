from uuid import UUID, uuid4

import pytest

from dsystem.dependencies.auth import TokenPayload
from dsystem.dependencies.legal_entity import UNRESTRICTED, LegalEntityScope, scope_for
from dsystem.exceptions import ForbiddenException, NotFoundException
from dsystem.role_templates import TEMPLATES

A, B, C = uuid4(), uuid4(), uuid4()


def _user(*, view: str | None = None, les: tuple = (), le=None, superuser: bool = False) -> TokenPayload:
    permissions = {"legal_entity": {"view": view}} if view else {}
    return TokenPayload(
        user_id=uuid4(),
        org_id=uuid4(),
        role_id=uuid4(),
        is_superuser=superuser,
        team_id=None,
        permissions=permissions,
        default_legal_entity_id=le,
        legal_entity_ids=les,
    )


def test_view_all_sees_everything():
    scope = scope_for(_user(view="all", le=A))
    assert scope.everything and scope.as_filter() is None
    assert scope.allows(C)
    scope.require_everything()


def test_superuser_sees_everything():
    assert scope_for(_user(superuser=True)).everything


def test_member_sees_only_assigned():
    scope = scope_for(_user(view="own", les=(A, B), le=A))
    assert not scope.everything
    assert scope.as_filter() == [A, B]
    assert scope.allows(A) and not scope.allows(C) and not scope.allows(None)


def test_unassigned_sees_nothing():
    scope = scope_for(_user(view="own"))
    assert scope.sees_nothing
    assert scope.as_filter() == []
    assert scope_for(_user()).sees_nothing


def test_ensure_answers_like_a_missing_row():
    scope = scope_for(_user(view="own", les=(A,)))
    scope.ensure(A, "document.not_found")
    with pytest.raises(NotFoundException) as exc:
        scope.ensure(B, "document.not_found")
    assert exc.value.status_code == 404
    assert exc.value.key == "document.not_found"


def test_require_everything_is_forbidden_for_members():
    with pytest.raises(ForbiddenException) as exc:
        scope_for(_user(view="own", les=(A,))).require_everything()
    assert exc.value.code == "legal_entity.scope_required"


def test_resolve_defaults_and_checks():
    scope = scope_for(_user(view="own", les=(A, B), le=B))
    assert scope.resolve(None) == B
    assert scope.resolve(A) == A
    with pytest.raises(NotFoundException):
        scope.resolve(C)


def test_resolve_ignores_a_default_outside_the_scope():
    scope = scope_for(_user(view="own", les=(A,), le=C))
    assert scope.default_id is None
    assert scope.resolve(None) == A
    assert LegalEntityScope(everything=False, legal_entity_ids=(A, B)).resolve(None) is None


def test_unrestricted_is_for_service_work():
    assert UNRESTRICTED.everything and UNRESTRICTED.allows(uuid4())


def test_only_admin_template_sees_every_legal_entity():
    for name, template in TEMPLATES.items():
        sees_all = template.get("legal_entity.view") == "all"
        assert sees_all == (name == "Admin"), name


def test_repository_scopes_only_when_it_declares_a_column():
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    from dsystem.legal_entity_scope import set_legal_entity_scope, unrestricted
    from dsystem.repositories.base import TenantRepository

    class Base(DeclarativeBase):
        pass

    class Row(Base):
        __tablename__ = "scoped_rows"
        id: Mapped[UUID] = mapped_column(primary_key=True)
        organization_id: Mapped[UUID]
        legal_entity_id: Mapped[UUID | None]

    class Scoped(TenantRepository):
        model = Row
        legal_entity_column = "legal_entity_id"

    class Open(TenantRepository):
        model = Row

    set_legal_entity_scope(LegalEntityScope(everything=False, legal_entity_ids=(A,)))
    try:
        assert "legal_entity_id IN" in str(Scoped(None, uuid4())._base_query())
        assert "legal_entity_id" not in str(Open(None, uuid4())._base_query().whereclause)
        with unrestricted():
            assert "legal_entity_id IN" not in str(Scoped(None, uuid4())._base_query())
    finally:
        set_legal_entity_scope(UNRESTRICTED)


@pytest.mark.asyncio
async def test_get_current_user_installs_the_callers_scope(monkeypatch):
    import jwt
    from fastapi.security import HTTPAuthorizationCredentials

    from dsystem.dependencies import auth
    from dsystem.legal_entity_scope import current_legal_entity_scope, set_legal_entity_scope

    async def _fresh(user, issued_at):
        return None

    monkeypatch.setattr(auth, "_get_secret_key", lambda: "secret")
    monkeypatch.setattr(auth, "_enforce_token_state", _fresh)
    token = jwt.encode(
        {
            "user_id": str(uuid4()),
            "org_id": str(uuid4()),
            "type": "access",
            "p": {"legal_entity": "o___"},
            "les": [str(A)],
        },
        "secret",
        algorithm="HS256",
    )
    try:
        user = await auth.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))
        assert user.legal_entity_ids == (A,)
        assert current_legal_entity_scope().as_filter() == [A]
    finally:
        set_legal_entity_scope(UNRESTRICTED)
