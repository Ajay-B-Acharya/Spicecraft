import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

sys.path.insert(0, str(Path(__file__).parent))

from app.database import create_tables, engine  # noqa: E402


def main() -> None:
    print("🚀 Connecting to PostgreSQL...")

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("✅ PostgreSQL connection successful")

        create_tables()
        print("✅ SQLAlchemy tables created successfully")
        print("🎉 Database setup complete")
    except OperationalError as exc:
        print(f"❌ Database connection error: {exc}")
        sys.exit(1)
    except SQLAlchemyError as exc:
        print(f"❌ SQLAlchemy error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
