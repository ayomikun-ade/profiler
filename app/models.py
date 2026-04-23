from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.uuid7 import uuid7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    gender_probability: Mapped[float] = mapped_column(Float, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    age_group: Mapped[str] = mapped_column(String(16), nullable=False)
    country_id: Mapped[str] = mapped_column(String(2), nullable=False)
    country_name: Mapped[str] = mapped_column(String(128), nullable=False)
    country_probability: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_profiles_gender", "gender"),
        Index("ix_profiles_country_id", "country_id"),
        Index("ix_profiles_age_group", "age_group"),
        Index("ix_profiles_age", "age"),
        Index("ix_profiles_created_at", "created_at"),
        Index("ix_profiles_gender_probability", "gender_probability"),
        Index("ix_profiles_country_probability", "country_probability"),
    )
