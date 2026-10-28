"""Health endpoint."""

from fastapi import APIRouter

from app.schemas.health import HealthStatus
from app.services.health_service import get_health_status

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def read_health() -> HealthStatus:
    """Return a simple process health payload."""
    return get_health_status()
