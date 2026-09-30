from __future__ import annotations

import types
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dsystem.models.legal_entity_replica import LegalEntityReplica
from dsystem.models.partner_replica import PartnerReplica
from dsystem.models.user_replica import UserReplica
from dsystem.schemas.base import AppSchema


class PartnerBrief(AppSchema):
    id: UUID
    code: str
    name: str


class UserBrief(AppSchema):
    id: UUID
    first_name: str | None
    last_name: str | None
    email: str
    picture_url: str | None


class LegalEntityBrief(AppSchema):
    id: UUID
    code: str
    name: str
    short_name: str | None


class LookupBrief(AppSchema):
    id: UUID
    name: str


@dataclass(frozen=True)
class Inline:
    source: str


@dataclass(frozen=True)
class InlineName:
    source: str
    by: str
    briefs: Mapping[str, tuple[type[BaseModel], str]]

    def __hash__(self) -> int:
        return hash((self.source, self.by, tuple(self.briefs)))


@dataclass(frozen=True)
class Source:
    model: Any
    options: tuple = ()
    build: Callable[[Any], BaseModel] | None = None


REPLICA_SOURCES: dict[type[BaseModel], Any] = {
    PartnerBrief: PartnerReplica,
    UserBrief: UserReplica,
    LegalEntityBrief: LegalEntityReplica,
}


@dataclass(frozen=True)
class _Slot:
    field: str
    source: str
    brief: type[BaseModel]
    many: bool


@dataclass(frozen=True)
class _NameSlot:
    field: str
    marker: InlineName


@dataclass(frozen=True)
class _Plan:
    slots: tuple[_Slot, ...]
    nested: tuple[str, ...]
    names: tuple[_NameSlot, ...] = ()


def _models_in(annotation) -> Iterable[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
        return
    for arg in typing.get_args(annotation):
        yield from _models_in(arg)


def _brief_of(annotation) -> tuple[type[BaseModel], bool]:
    origin = typing.get_origin(annotation)
    if origin in (list, tuple, set, Sequence):
        return _brief_of(typing.get_args(annotation)[0])[0], True
    if origin in (typing.Union, types.UnionType):
        inner = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        return _brief_of(inner[0])
    return annotation, False


@cache
def _plan(cls: type[BaseModel]) -> _Plan | None:
    return _build_plan(cls, frozenset())


def _build_plan(cls: type[BaseModel], seen: frozenset) -> _Plan | None:
    if cls in seen:
        return None
    seen = seen | {cls}
    slots: list[_Slot] = []
    names: list[_NameSlot] = []
    nested: list[str] = []
    recursive: list[str] = []
    for name, info in cls.model_fields.items():
        named = next((m for m in info.metadata if isinstance(m, InlineName)), None)
        if named is not None:
            names.append(_NameSlot(name, named))
            continue
        marker = next((m for m in info.metadata if isinstance(m, Inline)), None)
        if marker is not None:
            brief, many = _brief_of(info.annotation)
            slots.append(_Slot(name, marker.source, brief, many))
            continue
        children = list(_models_in(info.annotation))
        if cls in children:
            recursive.append(name)
        elif any(_build_plan(child, seen) is not None for child in children):
            nested.append(name)
    if not slots and not nested and not names:
        return None
    return _Plan(tuple(slots), tuple(nested + recursive), tuple(names))


def has_inline(annotation) -> bool:
    return any(_plan(model) is not None for model in _models_in(annotation))


def _walk(value, visit) -> None:
    if isinstance(value, BaseModel):
        plan = _plan(type(value))
        if plan is None:
            return
        visit(value, plan)
        for name in plan.nested:
            _walk(getattr(value, name), visit)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _walk(item, visit)
    elif isinstance(value, Mapping):
        for item in value.values():
            _walk(item, visit)


def _ids(value, slot: _Slot) -> list[UUID]:
    raw = getattr(value, slot.source, None)
    if raw is None:
        return []
    return [i for i in raw if i is not None] if slot.many else [raw]


def _named(item, slot: _NameSlot) -> tuple[type[BaseModel], str, UUID] | None:
    kind = getattr(item, slot.marker.by, None)
    kind = getattr(kind, "value", kind)
    target = getattr(item, slot.marker.source, None)
    if target is None or kind not in slot.marker.briefs:
        return None
    brief, attr = slot.marker.briefs[kind]
    return brief, attr, target


def _source(brief: type[BaseModel], sources: Mapping[type[BaseModel], Any]) -> Source:
    spec = sources.get(brief) or REPLICA_SOURCES.get(brief)
    if spec is None:
        raise LookupError(f"no source registered for {brief.__name__}")
    return spec if isinstance(spec, Source) else Source(spec)


async def resolve_inline(session: AsyncSession, value, sources: Mapping[type[BaseModel], Any] | None = None):
    sources = sources or {}
    wanted: dict[type[BaseModel], set[UUID]] = {}

    def collect(item, plan: _Plan) -> None:
        for slot in plan.slots:
            wanted.setdefault(slot.brief, set()).update(_ids(item, slot))
        for slot in plan.names:
            named = _named(item, slot)
            if named is not None:
                wanted.setdefault(named[0], set()).add(named[2])

    _walk(value, collect)
    if not any(wanted.values()):
        _walk(value, lambda item, plan: _fill(item, plan, {}))
        return value
    found: dict[type[BaseModel], dict[UUID, BaseModel]] = {}
    for brief, ids in wanted.items():
        if not ids:
            found[brief] = {}
            continue
        spec = _source(brief, sources)
        rows = await session.scalars(select(spec.model).where(spec.model.id.in_(ids)).options(*spec.options))
        build = spec.build or brief.model_validate
        found[brief] = {row.id: build(row) for row in rows}
    _walk(value, lambda item, plan: _fill(item, plan, found))
    return value


def _fill(item, plan: _Plan, found: dict[type[BaseModel], dict[UUID, BaseModel]]) -> None:
    for slot in plan.slots:
        by_id = found.get(slot.brief, {})
        ids = _ids(item, slot)
        if slot.many:
            setattr(item, slot.field, [by_id[i] for i in ids if i in by_id])
        else:
            setattr(item, slot.field, by_id.get(ids[0]) if ids else None)
    for slot in plan.names:
        named = _named(item, slot)
        brief = found.get(named[0], {}).get(named[2]) if named else None
        setattr(item, slot.field, getattr(brief, named[1]) if brief is not None else None)


def stored_fields(cls: type[BaseModel]) -> list[str]:
    return [
        name
        for name, info in cls.model_fields.items()
        if not any(isinstance(m, (Inline, InlineName)) for m in info.metadata)
    ]
