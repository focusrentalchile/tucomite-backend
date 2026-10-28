"""MySQL tables for modules, roles, permissions, and users."""

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ModuleModel(Base):
    """A product module shown as one row in the permission matrix."""

    __tablename__ = "modules"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    sort_order: Mapped[int] = mapped_column()
    functionalities: Mapped[list["FunctionalityModel"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="FunctionalityModel.sort_order",
    )


class FunctionalityModel(Base):
    """One checkbox belonging to a module."""

    __tablename__ = "functionalities"

    module_key: Mapped[str] = mapped_column(ForeignKey("modules.key", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    sort_order: Mapped[int] = mapped_column()
    module: Mapped[ModuleModel] = relationship(back_populates="functionalities")


class RoleModel(Base):
    """A role created by a super admin, or the seeded system role."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    permissions: Mapped[list["RolePermissionModel"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )


class RolePermissionModel(Base):
    """A granted checkbox for one role."""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "module_key", "functionality_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    module_key: Mapped[str] = mapped_column(String(64))
    functionality_key: Mapped[str] = mapped_column(String(64))
    role: Mapped[RoleModel] = relationship(back_populates="permissions")


class ClientModel(Base):
    """A paying client (building) created by the platform super admin."""

    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    admin_user_id: Mapped[str] = mapped_column(String(36))
    license_starts_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    license_ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class UserModel(Base):
    """A person assigned to one role."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"))
    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    period_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("periods.id"), nullable=True, index=True)
