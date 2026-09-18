from typing import Annotated

from pydantic import BeforeValidator

from dsystem.utils.phone import normalize_phone

Phone = Annotated[str | None, BeforeValidator(normalize_phone)]
