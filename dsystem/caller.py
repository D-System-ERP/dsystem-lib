from contextvars import ContextVar
from typing import Any

_caller: ContextVar[Any] = ContextVar("caller", default=None)


def current_caller() -> Any:
    """The signed-in user of the request (`TokenPayload`), or None for a service call or a consumer."""
    return _caller.get()


def set_caller(user: Any) -> None:
    _caller.set(user)
