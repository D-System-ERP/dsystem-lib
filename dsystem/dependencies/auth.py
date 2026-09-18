from dataclasses import dataclass, field
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

SCOPE_MAP = {"a": "all", "o": "own", "t": "team", "_": None}
ACTIONS = ["view", "create", "update", "delete"]


@dataclass(frozen=True)
class TokenPayload:
    user_id: UUID
    org_id: UUID
    role_id: UUID | None
    is_superuser: bool
    team_id: UUID | None
    permissions: dict
    # {resource: {action: tuple(stages) or None}}. None = no restriction (all stages).
    stage_filters: dict = field(default_factory=dict)
    # Snapshot of role.permission_version at mint time; compared against Redis on
    # every request so a stale token is rejected with 401 token_stale.
    role_version: int = 0
    session_id: str | None = None
    # Effective IANA timezone at mint time: user.timezone or the organization's.
    tz: str | None = None
    # The organization's own IANA timezone.
    otz: str | None = None
    # The legal entity documents default to (users.default_legal_entity_id).
    default_legal_entity_id: UUID | None = None
    email: str | None = None


@dataclass(frozen=True)
class Scope:
    scope: str
    user_id: UUID
    team_id: UUID | None = None
    # Tuple of allowed stages (e.g. ("offer", "order")). None = no restriction.
    allowed_stages: tuple[str, ...] | None = None

    @property
    def is_all(self) -> bool:
        return self.scope == "all"

    @property
    def is_own(self) -> bool:
        return self.scope == "own"

    @property
    def is_team(self) -> bool:
        return self.scope == "team"

    def check_stage(self, stage: str | None) -> None:
        if self.allowed_stages is None:
            return
        if stage is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "stage_forbidden",
                    "message": "Stage-restricted role cannot perform cross-stage operation",
                    "allowed": list(self.allowed_stages),
                },
            )
        if stage not in self.allowed_stages:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "stage_forbidden",
                    "message": f"Stage '{stage}' not permitted by this role",
                    "allowed": list(self.allowed_stages),
                },
            )


def _decode_permissions(raw: dict) -> dict:
    result = {}
    for resource_key, scope_str in raw.items():
        result[resource_key] = {ACTIONS[i]: SCOPE_MAP.get(ch) for i, ch in enumerate(scope_str[:4])}
    return result


def _decode_stage_filters(raw: dict) -> dict:
    result: dict = {}
    for resource, actions in (raw or {}).items():
        result[resource] = {}
        for action, stages in (actions or {}).items():
            result[resource][action] = tuple(stages) if stages else None
    return result


def _get_secret_key():
    from dsystem.dependencies._settings import get_jwt_secret

    return get_jwt_secret()


def _uuid_or_none(value) -> UUID | None:
    return UUID(value) if value else None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    try:
        payload = jwt.decode(credentials.credentials, _get_secret_key(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    if payload.get("type") != "access" or payload.get("aud"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user = TokenPayload(
        user_id=UUID(payload["user_id"]),
        org_id=UUID(payload["org_id"]),
        role_id=_uuid_or_none(payload.get("role_id")),
        is_superuser=payload.get("is_superuser", False),
        team_id=_uuid_or_none(payload.get("team_id")),
        permissions=_decode_permissions(payload.get("p", {})),
        stage_filters=_decode_stage_filters(payload.get("ps", {})),
        role_version=payload.get("rv", 0),
        session_id=payload.get("sid"),
        tz=payload.get("tz"),
        otz=payload.get("otz"),
        default_legal_entity_id=_uuid_or_none(payload.get("le")),
        email=payload.get("email"),
    )

    await _enforce_token_state(user, payload.get("iat"))

    return user


def role_version_key(role_id) -> str:
    return f"role:{role_id}:version"


def user_revocation_key(user_id) -> str:
    return f"user:{user_id}:revoked_at"


def active_sessions_key(user_id) -> str:
    return f"user:{user_id}:sids"


async def _token_state(user: "TokenPayload", check_role: bool) -> list:
    from dsystem.dependencies._settings import get_redis

    try:
        redis = await get_redis()
        pipe = redis.pipeline(transaction=False)
        pipe.get(user_revocation_key(user.user_id))
        pipe.zcard(active_sessions_key(user.user_id))
        pipe.zscore(active_sessions_key(user.user_id), user.session_id or "")
        if check_role:
            pipe.get(role_version_key(user.role_id))
        return await pipe.execute()
    except Exception:
        return [None, 0, None, None]


async def _enforce_token_state(user: "TokenPayload", issued_at) -> None:
    """Kill a stateless token early — fails OPEN when Redis is unavailable.

    ``token_revoked``: the user's sessions were revoked after this token was minted.
    ``session_superseded``: the account's device limit evicted this session.
    ``token_stale``: the role's permission set changed; a refresh re-mints it.
    """
    check_role = bool(user.role_id) and not user.is_superuser

    values = await _token_state(user, check_role)
    revoked_at, session_count, session_member = values[0], values[1], values[2]
    live_role_version = values[3] if check_role else None

    if revoked_at is not None and issued_at is not None and int(issued_at) < int(revoked_at):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_revoked", "message": "Session revoked; please sign in again"},
        )

    if user.session_id and session_count and session_member is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "session_superseded", "message": "Signed in on another device; this session was closed"},
        )

    if live_role_version is not None and int(live_role_version) != int(user.role_version):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_stale", "message": "Role permissions changed; please refresh your session"},
        )


async def get_org_id(user: TokenPayload = Depends(get_current_user)) -> UUID:
    return user.org_id


class Requires:
    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action

    async def __call__(self, user: TokenPayload = Depends(get_current_user)) -> Scope:
        if user.is_superuser:
            return Scope(scope="all", user_id=user.user_id, team_id=user.team_id)

        perm = user.permissions.get(self.resource, {})
        scope = perm.get(self.action)

        if scope is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"code": "permission_denied", "message": "Permission denied", "resource": self.resource},
            )

        allowed_stages = user.stage_filters.get(self.resource, {}).get(self.action)

        return Scope(
            scope=scope,
            user_id=user.user_id,
            team_id=user.team_id,
            allowed_stages=allowed_stages,
        )


ADMIN_AUDIENCE = "admin-console"


@dataclass(frozen=True)
class AdminPayload:
    user_id: UUID
    email: str | None = None
    name: str | None = None


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AdminPayload:
    try:
        payload = jwt.decode(
            credentials.credentials,
            _get_secret_key(),
            algorithms=["HS256"],
            audience=ADMIN_AUDIENCE,
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    return AdminPayload(
        user_id=UUID(payload["sub"]),
        email=payload.get("email"),
        name=payload.get("name"),
    )
