"""SQLite database engine and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from jobsentry.config import get_settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.ensure_dirs()
        db_path = settings.get_db_path()
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine())
    return _session_factory


def get_session() -> Session:
    return get_session_factory()()


def init_db():
    """Create all tables if they don't exist, and migrate schema."""
    from sqlalchemy import inspect, text
    from jobsentry.db.tables import Base

    engine = get_engine()
    Base.metadata.create_all(engine)

    # Add new columns if missing (no alembic, so manual migration)
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("jobs")]
    with engine.begin() as conn:
        if "notified_at" not in columns:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN notified_at DATETIME"))
        if "applied_at" not in columns:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN applied_at DATETIME"))
