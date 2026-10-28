"""MySQL table for building projects."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectModel(Base):
    """A project managed by the committee inside one period."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    period_id: Mapped[str] = mapped_column(String(36), ForeignKey("periods.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    photo_names: Mapped[str] = mapped_column(String(1000), default="")
