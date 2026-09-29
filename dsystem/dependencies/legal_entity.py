from typing import Annotated

from fastapi import Depends

from dsystem.dependencies.auth import TokenPayload, get_current_user
from dsystem.legal_entity_scope import (
    SEES_EVERY_LEGAL_ENTITY,
    UNRESTRICTED,
    LegalEntityScope,
    current_legal_entity_scope,
    scope_for,
    unrestricted,
)

__all__ = [
    "SEES_EVERY_LEGAL_ENTITY",
    "UNRESTRICTED",
    "LegalEntities",
    "LegalEntityScope",
    "current_legal_entity_scope",
    "legal_entity_scope",
    "require_every_legal_entity",
    "scope_for",
    "unrestricted",
]


async def legal_entity_scope(user: Annotated[TokenPayload, Depends(get_current_user)]) -> LegalEntityScope:
    return scope_for(user)


LegalEntities = Annotated[LegalEntityScope, Depends(legal_entity_scope)]


async def require_every_legal_entity(scope: LegalEntities) -> None:
    """Guard for organization-wide settings — taxes, units, catalogues — that no single legal entity owns."""
    scope.require_everything()
