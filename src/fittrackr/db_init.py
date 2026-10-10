
"""Initialize the FitTrackr database."""

from fittrackr import models  # Register all SQLAlchemy models
from fittrackr.database import Base, DATABASE_PATH, engine


def initialize_database() -> None:
    """Create database tables that do not already exist."""
    Base.metadata.create_all(bind=engine)

    print(f"Database initialized: {DATABASE_PATH}")
    print("Tables created or verified:")
    for table_name in sorted(Base.metadata.tables):
        print(f"- {table_name}")


if __name__ == "__main__":
    initialize_database()
