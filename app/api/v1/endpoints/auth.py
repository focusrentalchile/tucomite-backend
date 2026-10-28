"""Session sign-in and sign-out."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import SESSION_USER_KEY, Actor, get_current_actor
from app.core.database import get_db
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.committee_repository import SqlCommitteeRepository
from app.schemas.auth import LoginRequest, LoginResponse
from app.utils.passwords import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


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
    request.session.clear()
    request.session[SESSION_USER_KEY] = user.id
    return LoginResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role_id=user.role_id,
        is_super_admin=role.system,
        client_id=user.client_id,
        is_committee_member=SqlCommitteeRepository(db).get_member(user.id) is not None,
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
    return LoginResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role_id=user.role_id,
        is_super_admin=actor.is_super_admin,
        client_id=user.client_id,
        is_committee_member=SqlCommitteeRepository(db).get_member(user.id) is not None,
    )
