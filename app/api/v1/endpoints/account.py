"""Account endpoints. Only the building owner (client role) may close the account."""

import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_account_service, get_current_actor
from app.core.database import get_db
from app.domain.account import AccountAlreadyClosed, AccountNotClient, InvalidAccountPassword
from app.schemas.account import (
    AccountProfileResponse,
    CloseAccountRequest,
    UpdateAccountProfileRequest,
)
from app.services.account_service import AccountService

router = APIRouter(prefix="/account", tags=["account"])


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _profile_response(full_name: str, email: str, avatar_url: str = "") -> AccountProfileResponse:
    first_name, last_name = _split_name(full_name)
    return AccountProfileResponse(
        first_name=first_name,
        last_name=last_name,
        full_name=full_name.strip(),
        email=email,
        avatar_url=avatar_url or "",
    )


@router.patch("/profile", response_model=AccountProfileResponse)
def update_account_profile(
    body: UpdateAccountProfileRequest,
    service: AccountService = Depends(get_account_service),
    actor: Actor = Depends(get_current_actor),
) -> AccountProfileResponse:
    """Update the signed-in person's name and optional avatar."""
    try:
        user = service.update_profile(
            actor.user_id,
            first_name=body.first_name,
            last_name=body.last_name,
            avatar_url=body.avatar_url,
        )
    except AccountAlreadyClosed as error:
        raise HTTPException(status_code=409, detail="Account already closed.") from error
    except AccountNotClient as error:
        raise HTTPException(status_code=404, detail="User not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _profile_response(user.full_name, user.email, user.avatar_url)


@router.post("/close", response_class=StreamingResponse)
def close_account(
    body: CloseAccountRequest,
    request: Request,
    service: AccountService = Depends(get_account_service),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Verify the password, return a ZIP with the building's data, then close the account.

    The response is ``application/zip`` with folders ``agreements/``, ``topics/``,
    ``documents/``, ``users/``, and ``messages/``. The account is only closed after the ZIP
    was built, and the session ends with it.
    """
    try:
        export = service.close_account(actor.user_id, body.reason, body.password)
    except AccountNotClient as error:
        raise HTTPException(status_code=403, detail="Only the building owner can close the account.") from error
    except AccountAlreadyClosed as error:
        raise HTTPException(status_code=409, detail="Account already closed.") from error
    except InvalidAccountPassword as error:
        raise HTTPException(status_code=403, detail="Invalid password.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    # Persist the closure before the download starts, whatever order dependencies unwind in.
    db.commit()
    request.session.clear()
    return StreamingResponse(
        io.BytesIO(export.content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{export.filename}"',
            "Content-Length": str(len(export.content)),
        },
    )
