"""Session sign-in and sign-out."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import SESSION_USER_KEY, Actor, get_current_actor
from app.core.database import get_db
from app.domain.license import evaluate_license
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.committee_access import ensure_committee_access
from app.utils.passwords import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_response(
    *,
    user,
    role_key: str,
    permissions: list[str],
    is_super_admin: bool,
    is_committee_member: bool,
    client,
) -> LoginResponse:
    license = (
        None
        if is_super_admin or client is None
        else evaluate_license(client.license_starts_at, client.license_ends_at)
    )
    return LoginResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role_id=user.role_id,
        role_key=role_key,
        permissions=permissions,
        is_super_admin=is_super_admin,
        client_id=user.client_id,
        is_committee_member=is_committee_member,
        license_status=None if license is None else license.status,
        license_starts_at=None if license is None else license.starts_at,
        license_ends_at=None if license is None else license.ends_at,
        license_days_remaining=None if license is None else license.days_remaining,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    """Validate credentials and store the user id in the signed session cookie."""
    access = SqlAccessRepository(db)
    user = access.get_user_by_email(body.email.strip().lower())
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    role = access.get_role(user.role_id)
    if role is None:
        raise HTTPException(status_code=503, detail="Role is not available.")

    client = SqlClientRepository(db).get_client(user.client_id) if user.client_id else None
    if not role.system and user.client_id:
        if client is None:
            raise HTTPException(status_code=403, detail="license_inactive")
        license = evaluate_license(client.license_starts_at, client.license_ends_at)
        if license.status == "inactive":
            raise HTTPException(status_code=403, detail="license_inactive")

    request.session.clear()
    request.session[SESSION_USER_KEY] = user.id
    role_key = "super_admin" if role.system else role.name
    permissions = sorted(role.permissions)
    return _login_response(
        user=user,
        role_key=role_key,
        permissions=permissions,
        is_super_admin=role.system,
        is_committee_member=ensure_committee_access(
            db,
            user.id,
            role.name,
            frozenset(role.permissions),
        ),
        client=client,
    )


@router.post("/logout", status_code=204)
def logout(request: Request) -> None:
    """Clear the session cookie."""
    request.session.clear()


@router.get("/session", response_model=LoginResponse)
def read_session(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Return the signed-in person when the session cookie is valid."""
    access = SqlAccessRepository(db)
    user = access.get_user(actor.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    client = SqlClientRepository(db).get_client(user.client_id) if user.client_id else None
    if not actor.is_super_admin and user.client_id:
        if client is None:
            raise HTTPException(status_code=403, detail="license_inactive")
        license = evaluate_license(client.license_starts_at, client.license_ends_at)
        if license.status == "inactive":
            raise HTTPException(status_code=403, detail="license_inactive")
    access_role = access.get_role(user.role_id)
    role_name = access_role.name if access_role is not None else ""
    role_key = "super_admin" if actor.is_super_admin else role_name
    permissions = sorted(actor.permissions)
    return _login_response(
        user=user,
        role_key=role_key,
        permissions=permissions,
        is_super_admin=actor.is_super_admin,
        is_committee_member=ensure_committee_access(
            db,
            user.id,
            role_name,
            actor.permissions,
        ),
        client=client,
    )
