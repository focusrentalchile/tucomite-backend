"""Platform client endpoints for the super admin."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_client_service, require_permission
from app.core.database import get_db
from app.domain.access import DuplicateEmail
from app.repositories.access_repository import SqlAccessRepository
from app.schemas.clients import ClientListResponse, ClientResponse, CreateClientRequest
from app.services.client_service import ClientService, DuplicateClientName

router = APIRouter(prefix="/clients", tags=["clients"])


def _client_response(client, admin_email: str) -> ClientResponse:
    return ClientResponse(
        id=client.id,
        name=client.name,
        admin_user_id=client.admin_user_id,
        admin_email=admin_email,
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
        client, admin = service.create_client(body.name, body.email, body.password)
    except DuplicateClientName:
        raise HTTPException(status_code=409, detail="Client name already exists.") from None
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already registered.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _client_response(client, admin.email)
