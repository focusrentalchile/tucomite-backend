"""MySQL table for management periods."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.periods import PERIOD_STATUS_CLOSED


class PeriodModel(Base):
    """A period that the committee opens before managing projects."""

    __tablename__ = "periods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default=PERIOD_STATUS_CLOSED)
