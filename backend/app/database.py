import os
from collections.abc import Generator
from importlib import import_module

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Configure it in backend/.env.")
    print("DATABASE_URL =", DATABASE_URL)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all SQLAlchemy tables."""
    import_module("app.models.project")
    import_module("app.models.circuit_source")
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """Drop all SQLAlchemy tables."""
    import_module("app.models.project")
    import_module("app.models.circuit_source")
    Base.metadata.drop_all(bind=engine)
