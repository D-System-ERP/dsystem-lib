import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

service_secret_header = APIKeyHeader(name="X-Service-Secret", auto_error=False)

_service_secret: str = ""


def set_service_secret(secret: str):
    global _service_secret
    _service_secret = secret


def get_service_secret() -> str:
    """The secret this process was started with — outbound clients reuse it.

    Services load configuration through pydantic-settings, which never writes to
    ``os.environ``, so a client that reads the environment directly would send an
    empty secret and be refused with 403.
    """
    return _service_secret


async def verify_service_auth(secret: str | None = Depends(service_secret_header)):
    if not _service_secret or not secret or not hmac.compare_digest(secret, _service_secret):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid service secret")
