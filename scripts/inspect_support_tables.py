"""Print support-related table FK targets for local debugging."""

from sqlalchemy import create_engine, text

from app.core.config import settings


def main() -> None:
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        tables = connection.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND (TABLE_NAME LIKE '%support%' OR TABLE_NAME LIKE '%gestion%') "
                "ORDER BY TABLE_NAME"
            ),
        ).scalars().all()
        print("tables", tables)
        fks = connection.execute(
            text(
                "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME "
                "FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME LIKE '%support%' "
                "AND REFERENCED_TABLE_NAME IS NOT NULL"
            ),
        ).all()
        print("fks", fks)


if __name__ == "__main__":
    main()
