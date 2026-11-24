"""SQLAlchemy engine / session / Base."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Imported models must be loaded before calling."""
    import models  # noqa: F401

    # a fresh clone has no database folder yet (*.db is not in Git)
    if settings.database_url.startswith("sqlite") and engine.url.database:
        Path(engine.url.database).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """Tiny idempotent column adds for existing SQLite databases."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        cols = {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(devices)").fetchall()}
        if "services" not in cols:
            conn.exec_driver_sql("ALTER TABLE devices ADD COLUMN services VARCHAR(128)")