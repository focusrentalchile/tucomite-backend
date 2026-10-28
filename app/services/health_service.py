"""Health-check business logic."""

from app.schemas.health import HealthStatus

SERVICE_NAME = "tu-comite-api"


def get_health_status() -> HealthStatus:
    """Return the current process health without touching persistence."""
    return HealthStatus(status="ok", service=SERVICE_NAME)
