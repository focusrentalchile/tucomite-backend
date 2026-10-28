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
    RoleInUse,
    RoleNotFound,
    RoleRecord,
    UnknownPermission,
    UnknownRole,
    UserNotFound,
    UserRecord,
)
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
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
from app.services.access_service import PermissionPolicy, RoleService, UserService
from app.services.committee_access import ensure_committee_access

router = APIRouter(tags=["access"])


def _role_response(role: RoleRecord) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        system=role.system,
        permissions=sorted(role.permissions),
    )


def _user_response(user: UserRecord, *, protected: bool = False) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role_id=user.role_id,
        protected=protected,
    )


def _client_admin_id(db: Session, client_id: str | None) -> str | None:
    if not client_id:
        return None
    client = SqlClientRepository(db).get_client(client_id)
    return None if client is None else client.admin_user_id


def _scoped_users(
    service: UserService,
    actor: Actor,
    db: Session,
) -> tuple[list[UserRecord], frozenset[str]]:
    """Return users visible to the actor and the set of protected user ids."""
    access = SqlAccessRepository(db)
    roles = {role.id: role for role in access.list_roles()}
    admin_id = _client_admin_id(db, actor.client_id)
    protected_ids = frozenset({admin_id} if admin_id else ())
    users: list[UserRecord] = []
    for user in service.list_users():
        role = roles.get(user.role_id)
        if role is not None and role.system:
            continue
        if actor.is_super_admin:
            users.append(user)
            continue
        if actor.client_id and user.client_id == actor.client_id:
            users.append(user)
    return users, protected_ids


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
    role = access.get_role(user.role_id)
    role_name = role.name if role is not None else ""
    role_key = "super_admin" if actor.is_super_admin else role_name
    return MeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role_id=user.role_id,
        role_key=role_key,
        permissions=sorted(actor.permissions),
        is_committee_member=ensure_committee_access(
            db,
            user.id,
            role_name,
            actor.permissions,
        ),
        is_super_admin=actor.is_super_admin,
        client_id=user.client_id,
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
    actor: Actor = Depends(get_current_actor),
) -> RoleListResponse:
    """Return every assignable role. Needs roles.view or users.create/view."""
    policy = PermissionPolicy()
    allowed = (
        actor.is_super_admin
        or policy.allows(actor.permissions, "roles", "view")
        or policy.allows(actor.permissions, "users", "view")
        or policy.allows(actor.permissions, "users", "create")
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Forbidden.")
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


@router.delete("/roles/{role_id}", status_code=204)
def remove_role(
    role_id: str,
    service: RoleService = Depends(get_role_service),
    _: object = Depends(require_permission("roles", "delete")),
) -> None:
    """Delete a custom role. Starter and system roles stay."""
    try:
        service.delete_role(role_id)
    except RoleNotFound as error:
        raise HTTPException(status_code=404, detail="Role not found.") from error
    except ProtectedRole as error:
        raise HTTPException(status_code=409, detail="This role cannot be removed.") from error
    except RoleInUse as error:
        raise HTTPException(status_code=409, detail="This role still has users.") from error


@router.get("/users", response_model=UserListResponse)
def read_users(
    service: UserService = Depends(get_user_service),
    actor: Actor = Depends(require_permission("users", "view")),
    db: Session = Depends(get_db),
) -> UserListResponse:
    """Return users in the actor's building. The building admin is marked protected."""
    users, protected_ids = _scoped_users(service, actor, db)
    return UserListResponse(
        items=[_user_response(user, protected=user.id in protected_ids) for user in users],
    )


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: CreateUserRequest,
    service: UserService = Depends(get_user_service),
    actor: Actor = Depends(require_permission("users", "create")),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Create a user in the actor's building and assign a non-system role."""
    if not actor.is_super_admin and not actor.client_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        user = service.create_user(
            body.full_name,
            body.email,
            body.password,
            body.role_id,
            client_id=None if actor.is_super_admin else actor.client_id,
        )
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already exists.") from None
    except UnknownRole:
        raise HTTPException(status_code=422, detail="Role not found.") from None
    admin_id = _client_admin_id(db, actor.client_id)
    return _user_response(user, protected=user.id == admin_id)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    body: UpdateUserRequest,
    service: UserService = Depends(get_user_service),
    actor: Actor = Depends(require_permission("users", "create")),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update a user's name, email, optional password, and optional role."""
    _, protected_ids = _scoped_users(service, actor, db)
    try:
        user = service.update_user(
            user_id,
            body.full_name,
            body.email,
            body.password,
            body.role_id,
            protected_user_ids=protected_ids,
        )
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found.") from None
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already exists.") from None
    except ProtectedUser:
        raise HTTPException(status_code=409, detail="The building admin cannot be changed.") from None
    except UnknownRole:
        raise HTTPException(status_code=422, detail="Role not found.") from None
    return _user_response(user, protected=user.id in protected_ids)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
    actor: Actor = Depends(require_permission("users", "create")),
    db: Session = Depends(get_db),
) -> None:
    """Delete a user that is not the building admin or a system account."""
    _, protected_ids = _scoped_users(service, actor, db)
    try:
        service.delete_user(user_id, protected_user_ids=protected_ids)
    except UserNotFound:
        raise HTTPException(status_code=404, detail="User not found.") from None
    except ProtectedUser:
        raise HTTPException(status_code=409, detail="The building admin cannot be deleted.") from None
