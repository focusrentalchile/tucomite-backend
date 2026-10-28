"""HTTP schemas for roles, users, and the permission catalog."""

from pydantic import BaseModel, Field


class CatalogModule(BaseModel):
    """One module row and the functionality keys shown beside it."""

    key: str
    functionalities: list[str]


class CatalogResponse(BaseModel):
    """Modules currently registered in the product."""

    modules: list[CatalogModule]


class RoleResponse(BaseModel):
    """A role and the permission keys it holds."""

    id: str
    name: str
    system: bool
    permissions: list[str]


class RoleListResponse(BaseModel):
    """Role collection."""

    items: list[RoleResponse]


class CreateRoleRequest(BaseModel):
    """Name for a new role."""

    name: str = Field(min_length=1, max_length=80)


class SetPermissionRequest(BaseModel):
    """One checkbox change. It is applied immediately."""

    module_key: str = Field(min_length=1, max_length=64)
    functionality_key: str = Field(min_length=1, max_length=64)
    granted: bool


class UserResponse(BaseModel):
    """A user without the password hash."""

    id: str
    full_name: str
    email: str
    role_id: str
    protected: bool = False


class MeResponse(UserResponse):
    """The current actor, including committee membership and scope."""

    is_committee_member: bool
    is_super_admin: bool = False
    client_id: str | None = None


class UserListResponse(BaseModel):
    """User collection."""

    items: list[UserResponse]


class CreateUserRequest(BaseModel):
    """Fields required to create a user. Role is assigned by the server when omitted."""

    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    role_id: str | None = Field(default=None, max_length=36)


class UpdateUserRequest(BaseModel):
    """Editable user fields. Password stays unchanged when omitted."""

    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=6, max_length=128)
