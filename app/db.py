import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./watchmatch.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def run_migrations() -> None:
    """Idempotent ALTER TABLE migrations for columns added after initial deploy."""
    migrations = [
        "ALTER TABLE sessions ADD COLUMN content_type VARCHAR NOT NULL DEFAULT 'both'",
        "ALTER TABLE movies ADD COLUMN content_type VARCHAR NOT NULL DEFAULT 'movie'",
        "ALTER TABLE movies ADD COLUMN language VARCHAR NOT NULL DEFAULT 'en'",
        "ALTER TABLE queue_items ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN invite_token VARCHAR",
        "ALTER TABLE users ADD COLUMN theme VARCHAR NOT NULL DEFAULT 'dark'",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists — safe to ignore


def get_session():
    with Session(engine) as session:
        yield session
