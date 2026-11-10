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
    from app.models import contact as contact_models  # noqa: F401
    from app.models import committee as committee_models  # noqa: F401
    from app.models import periods as period_models  # noqa: F401
    from app.models import projects as project_models  # noqa: F401
    from app.models import legal as legal_models  # noqa: F401
    from app.models import management as management_models  # noqa: F401
    from app.models import messages as message_models  # noqa: F401
    from app.models import notifications as notification_models  # noqa: F401
    from app.models import support as support_models  # noqa: F401
    from app.models import building_wall as building_wall_models  # noqa: F401
    from app.models import email_templates as email_template_models  # noqa: F401
    from app.models import topics as topic_models  # noqa: F401
    from app.models import client_settings as client_settings_models  # noqa: F401
    from app.models import account as account_models  # noqa: F401
    from app.models import platform_settings as platform_settings_models  # noqa: F401
    from app.repositories.access_repository import SqlAccessRepository
    from app.repositories.message_repository import SqlMessageRepository
    from app.repositories.support_repository import SqlSupportRepository
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
            for column, ddl in (
                ("address", "ALTER TABLE `clients` ADD COLUMN `address` VARCHAR(255) NOT NULL DEFAULT ''"),
                (
                    "responsible_name",
                    "ALTER TABLE `clients` ADD COLUMN `responsible_name` VARCHAR(160) NOT NULL DEFAULT ''",
                ),
            ):
                has_column = connection.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() "
                        f"AND TABLE_NAME = 'clients' AND COLUMN_NAME = '{column}'"
                    ),
                ).scalar()
                if not has_column:
                    connection.execute(text(ddl))
        blog_exist = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'blog_posts'"
            ),
        ).scalar()
        if blog_exist:
            description_type = connection.execute(
                text(
                    "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'blog_posts' AND COLUMN_NAME = 'description'"
                ),
            ).scalar()
            if description_type and str(description_type).lower() != "text":
                connection.execute(text("ALTER TABLE `blog_posts` MODIFY COLUMN `description` TEXT NOT NULL"))
            cover_type = connection.execute(
                text(
                    "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'blog_posts' AND COLUMN_NAME = 'cover_image'"
                ),
            ).scalar()
            if cover_type and str(cover_type).lower() != "mediumtext":
                connection.execute(
                    text("ALTER TABLE `blog_posts` MODIFY COLUMN `cover_image` MEDIUMTEXT NOT NULL"),
                )
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
            has_apartment = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'users' AND COLUMN_NAME = 'apartment_number'"
                ),
            ).scalar()
            if not has_apartment:
                connection.execute(
                    text("ALTER TABLE `users` ADD COLUMN `apartment_number` VARCHAR(40) NULL"),
                )
            has_floor = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'users' AND COLUMN_NAME = 'floor_number'"
                ),
            ).scalar()
            if not has_floor:
                connection.execute(
                    text("ALTER TABLE `users` ADD COLUMN `floor_number` VARCHAR(40) NULL"),
                )
            has_account_closed = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'users' AND COLUMN_NAME = 'account_closed_at'"
                ),
            ).scalar()
            if not has_account_closed:
                connection.execute(
                    text("ALTER TABLE `users` ADD COLUMN `account_closed_at` DATETIME NULL"),
                )
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
            for column_name, ddl in (
                ("client_id", "ALTER TABLE `topics` ADD COLUMN `client_id` VARCHAR(36) NULL"),
                ("voting_starts_at", "ALTER TABLE `topics` ADD COLUMN `voting_starts_at` DATETIME NULL"),
                ("voting_ends_at", "ALTER TABLE `topics` ADD COLUMN `voting_ends_at` DATETIME NULL"),
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
            has_topic_client_index = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'topics' AND INDEX_NAME = 'ix_topics_client_id'"
                ),
            ).scalar()
            if not has_topic_client_index:
                connection.execute(text("CREATE INDEX `ix_topics_client_id` ON `topics` (`client_id`)"))
            if periods_exist:
                # Backfill: topics created before the column belong to their period's building.
                connection.execute(
                    text(
                        "UPDATE `topics` t INNER JOIN `periods` p ON p.id = t.period_id "
                        "SET t.client_id = p.client_id "
                        "WHERE t.client_id IS NULL AND p.client_id IS NOT NULL"
                    ),
                )
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
        support_repo = SqlSupportRepository(session)
        support_repo.ensure_default_types()
        support_repo.ensure_default_statuses()
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
