"""Platform client endpoints for the super admin."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_client_service, require_permission
from app.core.database import get_db
from app.domain.access import DuplicateEmail
from app.domain.license import evaluate_license
from app.repositories.access_repository import SqlAccessRepository
from app.schemas.clients import (
    ClientListResponse,
    ClientResponse,
    CreateClientRequest,
    UpdateClientRequest,
)
from app.services.client_service import ClientNotFound, ClientService, DuplicateClientName

router = APIRouter(prefix="/clients", tags=["clients"])


def _client_response(client, admin_email: str) -> ClientResponse:
    license = evaluate_license(client.license_starts_at, client.license_ends_at)
    return ClientResponse(
        id=client.id,
        name=client.name,
        admin_user_id=client.admin_user_id,
        admin_email=admin_email,
        license_starts_at=client.license_starts_at,
        license_ends_at=client.license_ends_at,
        license_status=license.status,
    )


@router.get("", response_model=ClientListResponse)
def list_clients(
    service: ClientService = Depends(get_client_service),
    db: Session = Depends(get_db),
    _: object = Depends(require_permission("clients", "view")),
) -> ClientListResponse:
    """Return every client for the platform super admin."""
    access = SqlAccessRepository(db)
    items: list[ClientResponse] = []
    for client in service.list_clients():
        admin = access.get_user(client.admin_user_id)
        items.append(_client_response(client, admin.email if admin else ""))
    return ClientListResponse(items=items)


@router.post("", response_model=ClientResponse, status_code=201)
def create_client(
    body: CreateClientRequest,
    service: ClientService = Depends(get_client_service),
    _: object = Depends(require_permission("clients", "create")),
) -> ClientResponse:
    """Create a client and its administrator account."""
    try:
        client, admin = service.create_client(
            body.name,
            body.email,
            body.password,
            body.license_starts_at,
            body.license_ends_at,
        )
    except DuplicateClientName:
        raise HTTPException(status_code=409, detail="Client name already exists.") from None
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already registered.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _client_response(client, admin.email)


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: str,
    body: UpdateClientRequest,
    service: ClientService = Depends(get_client_service),
    _: object = Depends(require_permission("clients", "update")),
) -> ClientResponse:
    """Update a client, license window, and administrator credentials."""
    try:
        client, admin = service.update_client(
            client_id,
            body.name,
            body.email,
            body.password,
            body.license_starts_at,
            body.license_ends_at,
        )
    except ClientNotFound:
        raise HTTPException(status_code=404, detail="Client not found.") from None
    except DuplicateClientName:
        raise HTTPException(status_code=409, detail="Client name already exists.") from None
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already registered.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _client_response(client, admin.email)


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: str,
    service: ClientService = Depends(get_client_service),
    _: object = Depends(require_permission("clients", "delete")),
) -> None:
    """Delete a client and every user that belongs to it."""
    try:
        service.delete_client(client_id)
    except ClientNotFound:
        raise HTTPException(status_code=404, detail="Client not found.") from None
