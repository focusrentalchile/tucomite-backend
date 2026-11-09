"""Widen blog_posts.cover_image to MEDIUMTEXT for data-URL covers."""

from sqlalchemy import create_engine, text

from app.core.config import settings


def main() -> None:
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        cover_type = connection.execute(
            text(
                "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'blog_posts' AND COLUMN_NAME = 'cover_image'"
            ),
        ).scalar()
        print(f"before={cover_type}")
        if cover_type and str(cover_type).lower() != "mediumtext":
            connection.execute(
                text("ALTER TABLE `blog_posts` MODIFY COLUMN `cover_image` MEDIUMTEXT NOT NULL"),
            )
        after = connection.execute(
            text(
                "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'blog_posts' AND COLUMN_NAME = 'cover_image'"
            ),
        ).scalar()
        print(f"after={after}")


if __name__ == "__main__":
    main()
