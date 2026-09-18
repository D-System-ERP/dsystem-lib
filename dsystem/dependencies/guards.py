from __future__ import annotations

from typing import TypeVar

from fastapi import HTTPException

from dsystem.exceptions import ConflictException, NotFoundException

T = TypeVar("T")


def or_400(obj: T | None, message: str = "Not found", *, status_code: int = 400) -> T:
    if obj is None:
        raise HTTPException(status_code, message)
    return obj


def or_404(
    obj: T | None, key: str = "common.not_found", *, message: str = "Not found", params: dict | None = None
) -> T:
    """Raise the standard ``404`` envelope when ``obj`` is missing.

    ``key`` doubles as the machine-readable ``code`` (``partner.not_found``) and the
    i18n lookup key, so every service reports missing rows the same way.
    """
    if obj is None:
        raise NotFoundException(code=key, key=key, message=message, params=params)
    return obj


def check_version(obj, expected: int | None, *, resource: str = "document") -> None:
    """Optimistic-lock guard: ``409 <resource>.version_conflict`` when the client's copy is stale.

    ``expected`` is the ``If-Match`` header or body ``version``; ``None`` skips the
    check for clients that do not send one.
    """
    if expected is None:
        return
    current = getattr(obj, "version", None)
    if current is not None and int(current) != int(expected):
        raise ConflictException(
            code=f"{resource}.version_conflict",
            key=f"{resource}.version_conflict",
            message="The record was modified by someone else; reload and retry",
            params={"current": current, "expected": int(expected)},
        )
