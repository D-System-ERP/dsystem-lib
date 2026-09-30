import inspect
from collections.abc import Callable, Mapping
from typing import Any

from fastapi import Depends
from fastapi.datastructures import DefaultPlaceholder
from fastapi.dependencies.utils import get_typed_return_annotation, get_typed_signature
from fastapi.routing import APIRoute
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from dsystem.schemas.refs import has_inline, resolve_inline

_SESSION_PARAM = "inline_refs_session"


def _validated(result) -> bool:
    if isinstance(result, BaseModel):
        return True
    return isinstance(result, (list, tuple)) and all(isinstance(item, BaseModel) for item in result)


def _wrap(endpoint: Callable, model: Any, get_db: Callable, sources: Mapping) -> Callable:
    signature = get_typed_signature(endpoint)
    adapter = TypeAdapter(model)

    async def wrapper(*args, **kwargs):
        session: AsyncSession = kwargs.pop(_SESSION_PARAM)
        result = endpoint(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        if not _validated(result):
            result = adapter.validate_python(result, from_attributes=True)
        return await resolve_inline(session, result, sources)

    session_param = inspect.Parameter(
        _SESSION_PARAM, inspect.Parameter.KEYWORD_ONLY, default=Depends(get_db), annotation=AsyncSession
    )
    params = list(signature.parameters.values())
    wrapper.__signature__ = inspect.Signature(params + [session_param], return_annotation=model)
    wrapper.__name__ = endpoint.__name__
    wrapper.__qualname__ = endpoint.__qualname__
    wrapper.__doc__ = endpoint.__doc__
    wrapper.__module__ = endpoint.__module__
    wrapper.inline_refs = True
    return wrapper


def inline_route(get_db: Callable, sources: Mapping | None = None) -> type[APIRoute]:
    """An ``APIRoute`` whose responses carry ``Inline`` objects, read with the request's own session."""

    resolved = dict(sources or {})

    class InlineRoute(APIRoute):
        def __init__(self, path: str, endpoint: Callable, **kwargs) -> None:
            model = kwargs.get("response_model")
            if model is None or isinstance(model, DefaultPlaceholder):
                model = get_typed_return_annotation(endpoint)
            if model is not None and not getattr(endpoint, "inline_refs", False) and has_inline(model):
                endpoint = _wrap(endpoint, model, get_db, resolved)
            super().__init__(path, endpoint, **kwargs)

    return InlineRoute
