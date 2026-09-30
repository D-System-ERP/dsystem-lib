from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from dsystem.exceptions import ForbiddenException, NotFoundException

SEES_EVERY_LEGAL_ENTITY = ("legal_entity", "view", "all")


@dataclass(frozen=True)
class LegalEntityScope:
    """Which legal entities of the organization the caller may see and write.

    ``everything`` belongs to platform staff and to roles whose ``legal_entity.view``
    scope is ``all`` (the organization's Admin by default). Everyone else gets the
    ids minted into the token as ``les``; an empty tuple is a real answer — an
    account nobody put on a legal entity sees nothing.

    ``active_id`` is the legal entity the caller switched to (token claim ``act``):
    lists narrow to it and new rows default to it. ``None`` means "all of mine".
    """

    everything: bool
    legal_entity_ids: tuple[UUID, ...] = ()
    default_id: UUID | None = None
    active_id: UUID | None = None

    @property
    def sees_nothing(self) -> bool:
        return not self.everything and not self.legal_entity_ids

    def allows(self, legal_entity_id: UUID | None) -> bool:
        return self.everything or (legal_entity_id is not None and legal_entity_id in self.legal_entity_ids)

    def as_filter(self) -> list[UUID] | None:
        """What lists show: the active legal entity when one is picked, else every permitted one."""
        if self.active_id is not None:
            return [self.active_id]
        return self.permitted_filter()

    def permitted_filter(self) -> list[UUID] | None:
        """Every legal entity the caller may see, ignoring the switcher — pickers and the legal entity registry."""
        return None if self.everything else list(self.legal_entity_ids)

    def ensure(self, legal_entity_id: UUID | None, key: str = "common.not_found") -> None:
        """Refuse a row of a legal entity the caller cannot see with the same 404 a missing row gives."""
        if not self.allows(legal_entity_id):
            raise NotFoundException(code=key, key=key)

    def resolve(self, requested: UUID | None, key: str = "legal_entity.not_found") -> UUID | None:
        """The legal entity a new row is written under: the requested one, else the caller's default."""
        chosen = requested if requested is not None else self.default_id
        if chosen is None and not self.everything and len(self.legal_entity_ids) == 1:
            chosen = self.legal_entity_ids[0]
        if chosen is not None:
            self.ensure(chosen, key)
        return chosen

    def require_everything(self) -> None:
        if not self.everything:
            raise ForbiddenException(
                code="legal_entity.scope_required", message="Requires access to every legal entity"
            )


UNRESTRICTED = LegalEntityScope(everything=True)


def scope_for(user) -> LegalEntityScope:
    resource, action, scope = SEES_EVERY_LEGAL_ENTITY
    active_id = getattr(user, "active_legal_entity_id", None)
    if user.is_superuser or user.permissions.get(resource, {}).get(action) == scope:
        return LegalEntityScope(
            everything=True, default_id=active_id or user.default_legal_entity_id, active_id=active_id
        )
    if active_id not in user.legal_entity_ids:
        active_id = None
    default_id = user.default_legal_entity_id if user.default_legal_entity_id in user.legal_entity_ids else None
    return LegalEntityScope(
        everything=False,
        legal_entity_ids=user.legal_entity_ids,
        default_id=active_id or default_id,
        active_id=active_id,
    )


_current: ContextVar[LegalEntityScope] = ContextVar("legal_entity_scope", default=UNRESTRICTED)


def current_legal_entity_scope() -> LegalEntityScope:
    return _current.get()


def set_legal_entity_scope(scope: LegalEntityScope) -> None:
    _current.set(scope)


@contextmanager
def unrestricted() -> Iterator[None]:
    """Work done on the organization's behalf inside a user request — a chain walk, a stock recount."""
    token = _current.set(UNRESTRICTED)
    try:
        yield
    finally:
        _current.reset(token)
