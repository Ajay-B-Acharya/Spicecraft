"""
Database initialization script for SpiceCraft.

Run this script to create all database tables.

Usage:
    python create_db.py
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import create_tables


def main():
    """Create all database tables."""
    print("🚀 Creating SpiceCraft database tables...")
    print()

    try:
        create_tables()
        print()
        print("✨ Database setup complete!")
        print()
        print("Next steps:")
        print("1. Start the backend: uvicorn app.main:app --reload")
        print("2. Visit API docs: http://localhost:8000/docs")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
