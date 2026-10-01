from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from dsystem.models.base import Base


class ProcessedEvent(Base):
    """One row per event a consumer has applied, written in the same transaction as the event's effect."""

    __tablename__ = "processed_events"

    consumer: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
