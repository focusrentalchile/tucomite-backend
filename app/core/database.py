"""MySQL engine, sessions, and schema bootstrap.

Local connection uses user ``root`` with an empty password.
"""

import re

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_DATABASE_NAME = re.compile(r"^[A-Za-z0-9_]+$")


class Base(DeclarativeBase):
    """Declarative base for every MySQL model."""


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_database() -> None:
    """Create the application database when it does not exist yet."""
    database_name = settings.database_url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not _DATABASE_NAME.fullmatch(database_name):
        raise ValueError("Database name must contain only letters, numbers, and underscores.")
    server_url = settings.database_url.rsplit("/", 1)[0]
    server = create_engine(server_url, pool_pre_ping=True)
    with server.connect() as connection:
        connection.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            ),
        )
        connection.commit()
    server.dispose()


def init_database() -> None:
    """Create the database, tables, catalog rows, and the super admin."""
    from app.access import registration  # noqa: F401
    from app.core.access_catalog import access_catalog
    from app.models import access as access_models  # noqa: F401
    from app.models import committee as committee_models  # noqa: F401
    from app.models import periods as period_models  # noqa: F401
    from app.models import projects as project_models  # noqa: F401
    from app.models import support as support_models  # noqa: F401
    from app.models import topics as topic_models  # noqa: F401
    from app.repositories.access_repository import SqlAccessRepository
    from app.repositories.topic_repository import SqlTopicRepository
    from app.services.access_bootstrap import bootstrap_access
    from app.services.topic_service import ensure_topic_priorities, ensure_topic_statuses

    create_database()
    # Local schema catch-up when columns were added after the first create_all.
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS `projects`"))
        has_priority = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'topics' AND COLUMN_NAME = 'priority_id'"
            ),
        ).scalar()
        if not has_priority:
            connection.execute(text("DROP TABLE IF EXISTS `topic_votes`"))
            connection.execute(text("DROP TABLE IF EXISTS `topics`"))
        has_client_id = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'users' AND COLUMN_NAME = 'client_id'"
            ),
        ).scalar()
        if not has_client_id:
            users_exist = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users'"
                ),
            ).scalar()
            if users_exist:
                connection.execute(text("ALTER TABLE `users` ADD COLUMN `client_id` VARCHAR(36) NULL"))
        clients_exist = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'clients'"
            ),
        ).scalar()
        if clients_exist:
            has_license_start = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'clients' AND COLUMN_NAME = 'license_starts_at'"
                ),
            ).scalar()
            if not has_license_start:
                connection.execute(text("ALTER TABLE `clients` ADD COLUMN `license_starts_at` DATE NULL"))
                connection.execute(text("ALTER TABLE `clients` ADD COLUMN `license_ends_at` DATE NULL"))
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        from app.repositories.client_repository import SqlClientRepository

        bootstrap_access(SqlAccessRepository(session), access_catalog, SqlClientRepository(session))
        ensure_topic_statuses(SqlTopicRepository(session))
        ensure_topic_priorities(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """Yield a request-scoped session and commit when the request succeeds."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
