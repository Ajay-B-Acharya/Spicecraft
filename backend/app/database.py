import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Create SQLAlchemy engine
# For PostgreSQL: postgresql://user:password@host:port/database
if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using them
        pool_size=5,  # Number of connections to maintain
        max_overflow=10,  # Max overflow connections
        echo=False,  # Set to True for SQL query logging in development
    )
else:
    # Fallback to SQLite for development if no PostgreSQL URL is set
    SQLITE_DATABASE_URL = "sqlite:///./spicecraft.db"
    engine = create_engine(
        SQLITE_DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite specific
        echo=True,
    )
    print("⚠️  Using SQLite for development. Set DATABASE_URL for PostgreSQL.")

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


# Dependency to get database session
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables in the database."""
    # Import all models here to ensure they're registered with Base
    from app.models import circuit_source, project  # noqa: F401

    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully.")


def drop_tables():
    """Drop all tables in the database. Use with caution!"""
    from app.models import circuit_source, project  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    print("⚠️  All tables dropped.")
