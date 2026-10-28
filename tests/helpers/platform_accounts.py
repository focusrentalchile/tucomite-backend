"""Test-only platform accounts written into the MySQL test database."""

from app.core.access_catalog import access_catalog
from app.core.database import SessionLocal
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.services.access_bootstrap import bootstrap_access, upsert_platform_accounts

SUPER_ADMIN_EMAIL = "superadmin@tucomite.cl"
DEMO_ADMIN_EMAIL = "admin@tucomite.cl"
SEED_PASSWORD = "1234567"


def ensure_test_platform_accounts() -> None:
    """Insert or refresh the accounts used by API tests."""
    session = SessionLocal()
    try:
        access = SqlAccessRepository(session)
        clients = SqlClientRepository(session)
        bootstrap_access(access, access_catalog, clients)
        upsert_platform_accounts(
            access,
            clients,
            super_admin_email=SUPER_ADMIN_EMAIL,
            super_admin_password=SEED_PASSWORD,
            demo_admin_email=DEMO_ADMIN_EMAIL,
            demo_admin_password=SEED_PASSWORD,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
