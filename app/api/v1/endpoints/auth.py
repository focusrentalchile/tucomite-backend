"""Session sign-in and sign-out."""

from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import SESSION_USER_KEY, Actor, get_current_actor
from app.core.database import get_db
from app.domain.access import UserRecord
from app.domain.license import evaluate_license
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse
from app.services.committee_access import ensure_committee_access, is_listed_committee_member
from app.utils.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_response(
    *,
    user: UserRecord,
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
        floor_number=user.floor_number,
        apartment_number=user.apartment_number,
        license_status=None if license is None else license.status,
        license_starts_at=None if license is None else license.starts_at,
        license_ends_at=None if license is None else license.ends_at,
        license_days_remaining=None if license is None else license.days_remaining,
        must_change_password=bool(user.must_change_password),
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    """Validate credentials and store the user id in the signed session cookie."""
    access = SqlAccessRepository(db)
    user = access.get_user_by_email(body.email.strip().lower())
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if user.account_closed_at:
        raise HTTPException(status_code=403, detail="account_closed")
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
    if not role.system:
        ensure_committee_access(db, user.id, role.name, role.permissions)
    return _login_response(
        user=user,
        role_key=role_key,
        permissions=permissions,
        is_super_admin=role.system,
        is_committee_member=is_listed_committee_member(db, user.id),
        client=client,
    )


@router.post("/logout", status_code=204)
def logout(request: Request) -> None:
    """Clear the session cookie."""
    request.session.clear()


@router.post("/change-password", response_model=LoginResponse)
def change_password(
    body: ChangePasswordRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Replace a temporary password and clear the first-login change flag."""
    if body.password != body.password_confirm:
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    access = SqlAccessRepository(db)
    user = access.get_user(actor.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    updated = replace(
        user,
        password_hash=hash_password(body.password),
        must_change_password=False,
    )
    access.save_user(updated)
    client = SqlClientRepository(db).get_client(updated.client_id) if updated.client_id else None
    access_role = access.get_role(updated.role_id)
    role_name = access_role.name if access_role is not None else ""
    role_key = "super_admin" if actor.is_super_admin else role_name
    permissions = sorted(actor.permissions)
    if not actor.is_super_admin:
        ensure_committee_access(db, updated.id, role_name, actor.permissions)
    return _login_response(
        user=updated,
        role_key=role_key,
        permissions=permissions,
        is_super_admin=actor.is_super_admin,
        is_committee_member=is_listed_committee_member(db, updated.id),
        client=client,
    )


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
    if not actor.is_super_admin:
        ensure_committee_access(db, user.id, role_name, actor.permissions)
    return _login_response(
        user=user,
        role_key=role_key,
        permissions=permissions,
        is_super_admin=actor.is_super_admin,
        is_committee_member=is_listed_committee_member(db, user.id),
        client=client,
    )
