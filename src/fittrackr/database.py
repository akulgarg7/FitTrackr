import os
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Generator

from sqlalchemy import URL, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")
APP_ENV = os.getenv("FITTRACKR_ENV", "test").strip().lower()

if APP_ENV not in {"test", "personal"}:
    raise ValueError(
        "FITTRACKR_ENV must be either 'test' or 'personal'."
    )

DATABASE_PATH = DATA_DIR / f"fittrackr_{APP_ENV}.db"

DATABASE_URL = URL.create(
    drivername="sqlite",
    database=str(DATABASE_PATH),
)


engine: Engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


# foreign-key relationships.
@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection,
    connection_record,
):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a database session and safely close it."""
    session = SessionLocal()

    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
