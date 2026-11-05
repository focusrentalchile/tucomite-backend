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
    from app.models import blog as blog_models  # noqa: F401
    from app.models import committee as committee_models  # noqa: F401
    from app.models import periods as period_models  # noqa: F401
    from app.models import projects as project_models  # noqa: F401
    from app.models import legal as legal_models  # noqa: F401
    from app.models import management as management_models  # noqa: F401
    from app.models import messages as message_models  # noqa: F401
    from app.models import notifications as notification_models  # noqa: F401
    from app.models import topics as topic_models  # noqa: F401
    from app.repositories.access_repository import SqlAccessRepository
    from app.repositories.message_repository import SqlMessageRepository
    from app.repositories.topic_repository import SqlTopicRepository
    from app.services.access_bootstrap import bootstrap_access
    from app.services.topic_service import ensure_topic_priorities, ensure_topic_statuses

    create_database()
        # Local schema catch-up when columns were added after the first create_all.
    with engine.begin() as connection:
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
        topics_exist = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'topics'"
            ),
        ).scalar()
        if topics_exist:
            for column, ddl in (
                ("assignee_user_id", "ALTER TABLE `topics` ADD COLUMN `assignee_user_id` VARCHAR(36) NULL"),
                ("start_date", "ALTER TABLE `topics` ADD COLUMN `start_date` DATE NULL"),
                ("due_date", "ALTER TABLE `topics` ADD COLUMN `due_date` DATE NULL"),
                ("created_at", "ALTER TABLE `topics` ADD COLUMN `created_at` DATETIME NULL"),
                ("closed_at", "ALTER TABLE `topics` ADD COLUMN `closed_at` DATETIME NULL"),
                ("period_id", "ALTER TABLE `topics` ADD COLUMN `period_id` VARCHAR(36) NULL"),
                ("completion_note", "ALTER TABLE `topics` ADD COLUMN `completion_note` VARCHAR(500) NULL"),
                (
                    "completion_submitted_at",
                    "ALTER TABLE `topics` ADD COLUMN `completion_submitted_at` DATETIME NULL",
                ),
            ):
                has_column = connection.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() "
                        f"AND TABLE_NAME = 'topics' AND COLUMN_NAME = '{column}'"
                    ),
                ).scalar()
                if not has_column:
                    connection.execute(text(ddl))
        users_exist_for_period = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users'"
            ),
        ).scalar()
        if users_exist_for_period:
            has_user_period = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'users' AND COLUMN_NAME = 'period_id'"
                ),
            ).scalar()
            if not has_user_period:
                connection.execute(text("ALTER TABLE `users` ADD COLUMN `period_id` VARCHAR(36) NULL"))
        from app.repositories.management_repository import ensure_management_schema

        ensure_management_schema(connection)
        projects_exist = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'projects'"
            ),
        ).scalar()
        if projects_exist:
            has_project_created = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'projects' AND COLUMN_NAME = 'created_at'"
                ),
            ).scalar()
            if not has_project_created:
                connection.execute(
                    text("ALTER TABLE `projects` ADD COLUMN `created_at` DATETIME NULL"),
                )
                connection.execute(
                    text("UPDATE `projects` SET `created_at` = UTC_TIMESTAMP() WHERE `created_at` IS NULL"),
                )
            has_project_due = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'projects' AND COLUMN_NAME = 'due_date'"
                ),
            ).scalar()
            if not has_project_due:
                connection.execute(text("ALTER TABLE `projects` ADD COLUMN `due_date` DATE NULL"))
        periods_exist = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'periods'"
            ),
        ).scalar()
        if periods_exist:
            has_period_client = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'periods' AND COLUMN_NAME = 'client_id'"
                ),
            ).scalar()
            if not has_period_client:
                connection.execute(
                    text("ALTER TABLE `periods` ADD COLUMN `client_id` VARCHAR(36) NULL"),
                )
            has_period_client_index = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'periods' AND INDEX_NAME = 'ix_periods_client_id'"
                ),
            ).scalar()
            if not has_period_client_index:
                connection.execute(
                    text("CREATE INDEX `ix_periods_client_id` ON `periods` (`client_id`)"),
                )
        legal_cases_exist = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'legal_cases'"
            ),
        ).scalar()
        if legal_cases_exist:
            has_legal_status = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'legal_cases' AND COLUMN_NAME = 'status'"
                ),
            ).scalar()
            if not has_legal_status:
                connection.execute(
                    text(
                        "ALTER TABLE `legal_cases` "
                        "ADD COLUMN `status` VARCHAR(32) NOT NULL DEFAULT 'waiting'"
                    ),
                )
                connection.execute(
                    text("CREATE INDEX `ix_legal_cases_status` ON `legal_cases` (`status`)"),
                )
        topics_exist = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'topics'"
            ),
        ).scalar()
        if topics_exist:
            for column_name, ddl in (
                (
                    "vote_type",
                    "ALTER TABLE `topics` ADD COLUMN `vote_type` VARCHAR(16) NOT NULL DEFAULT 'yes_no'",
                ),
                (
                    "vote_options_json",
                    "ALTER TABLE `topics` ADD COLUMN `vote_options_json` TEXT NULL",
                ),
            ):
                has_column = connection.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() "
                        f"AND TABLE_NAME = 'topics' AND COLUMN_NAME = '{column_name}'"
                    ),
                ).scalar()
                if not has_column:
                    connection.execute(text(ddl))
            vote_choice_len = connection.execute(
                text(
                    "SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'topic_votes' AND COLUMN_NAME = 'choice'"
                ),
            ).scalar()
            if vote_choice_len is not None and int(vote_choice_len) < 36:
                connection.execute(
                    text("ALTER TABLE `topic_votes` MODIFY COLUMN `choice` VARCHAR(36) NOT NULL"),
                )
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        from app.repositories.client_repository import SqlClientRepository

        bootstrap_access(SqlAccessRepository(session), access_catalog, SqlClientRepository(session))
        ensure_topic_statuses(SqlTopicRepository(session))
        ensure_topic_priorities(session)
        SqlMessageRepository(session).ensure_default_types()
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
