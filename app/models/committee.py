"""MySQL table for committee members."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CommitteeMemberModel(Base):
    """Links one user to the building committee."""

    __tablename__ = "committee_members"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
