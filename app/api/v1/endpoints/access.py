"""Access endpoints: catalog, roles, and users."""

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, get_role_service, get_user_service, require_permission
from app.core.database import get_db
from app.domain.access import (
    DuplicateEmail,
    DuplicateRoleName,
    ProtectedRole,
    ProtectedUser,
    RoleNotFound,
    RoleRecord,
    UnknownPermission,
    UnknownRole,
    UserNotFound,
    UserRecord,
)
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.committee_repository import SqlCommitteeRepository
from app.schemas.access import (
    CatalogModule,
    CatalogResponse,
    CreateRoleRequest,
    CreateUserRequest,
    MeResponse,
    RoleListResponse,
    RoleResponse,
    SetPermissionRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from app.services.access_service import RoleService, UserService

router = APIRouter(tags=["access"])


def _role_response(role: RoleRecord) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        system=role.system,
        permissions=sorted(role.permissions),
    )


def _user_response(user: UserRecord) -> UserResponse:
    return UserResponse(id=user.id, full_name=user.full_name, email=user.email, role_id=user.role_id)


@router.get("/access/me", response_model=MeResponse)
def read_me(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> MeResponse:
    """Return the person performing the request until sign-in selects another actor."""
    access = SqlAccessRepository(db)
    user = next((item for item in access.list_users() if item.id == actor.user_id), None)
    if user is None:
        raise HTTPException(status_code=503, detail="Current user is not available.")
    return MeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role_id=user.role_id,
        is_committee_member=SqlCommitteeRepository(db).get_member(user.id) is not None,
    )


@router.get("/access/catalog", response_model=CatalogResponse)
def read_catalog(
    service: RoleService = Depends(get_role_service),
    _: object = Depends(require_permission("roles", "view")),
) -> CatalogResponse:
    """Return the modules and functionalities stored from the code registry."""
    modules = service.list_catalog()
    return CatalogResponse(
        modules=[CatalogModule(key=module.key, functionalities=list(module.functionalities)) for module in modules],
    )


@router.get("/roles", response_model=RoleListResponse)
def read_roles(
    service: RoleService = Depends(get_role_service),
    _: object = Depends(require_permission("roles", "view")),
) -> RoleListResponse:
    """Return every role."""
    return RoleListResponse(items=[_role_response(role) for role in service.list_roles()])


@router.post("/roles", response_model=RoleResponse, status_code=201)
def create_role(
    body: CreateRoleRequest,
    service: RoleService = Depends(get_role_service),
    _: object = Depends(require_permission("roles", "create")),
) -> RoleResponse:
    """Create a role with no permissions."""
    try:
        role = service.create_role(body.name)
    except DuplicateRoleName:
        raise HTTPException(status_code=409, detail="Role name already exists.") from None
    return _role_response(role)


@router.patch("/roles/{role_id}/permissions", response_model=RoleResponse)
def set_permission(
    role_id: str,
    body: SetPermissionRequest,
    service: RoleService = Depends(get_role_service),
    _: object = Depends(require_permission("roles", "update")),
) -> RoleResponse:
    """Grant or remove one permission. The checkbox is the whole action."""
    try:
        role = service.set_permission(role_id, body.module_key, body.functionality_key, body.granted)
    except RoleNotFound:
        raise HTTPException(status_code=404, detail="Role not found.") from None
    except ProtectedRole:
        raise HTTPException(status_code=409, detail="The system role keeps every permission.") from None
    except UnknownPermission:
        raise HTTPException(status_code=422, detail="Unknown permission.") from None
    return _role_response(role)


@router.get("/users", response_model=UserListResponse)
def read_users(
    service: UserService = Depends(get_user_service),
    _: object = Depends(require_permission("users", "view")),
) -> UserListResponse:
    """Return every user."""
    return UserListResponse(items=[_user_response(user) for user in service.list_users()])


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: CreateUserRequest,
    service: UserService = Depends(get_user_service),
    _: object = Depends(require_permission("users", "create")),
) -> UserResponse:
    """Create a user and assign a role."""
    try:
        user = service.create_user(body.full_name, body.email, body.password, body.role_id)
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already exists.") from None
    except UnknownRole:
        raise HTTPException(status_code=422, detail="Role not found.") from None
    return _user_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    body: UpdateUserRequest,
    service: UserService = Depends(get_user_service),
    _: object = Depends(require_permission("users", "create")),
) -> UserResponse:
    """Update a user's name, email, and optional password."""
    try:
        user = service.update_user(user_id, body.full_name, body.email, body.password)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found.") from None
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already exists.") from None
    return _user_response(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
    _: object = Depends(require_permission("users", "create")),
) -> None:
    """Delete a user that is not the seeded super admin."""
    try:
        service.delete_user(user_id)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found.") from None
    except ProtectedUser:
        raise HTTPException(status_code=409, detail="The super admin cannot be deleted.") from None
