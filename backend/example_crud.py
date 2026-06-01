"""
Example CRUD operations for SpiceCraft models.

This demonstrates how to interact with the database using SQLAlchemy ORM.
These examples can be adapted for use in API route handlers.
"""

from uuid import uuid4

from app.database import SessionLocal
from app.models.circuit_source import CircuitSource
from app.models.project import Project
from sqlalchemy.orm import Session


def create_project_example(db: Session, firebase_uid: str):
    """
    Example: Create a new project.

    Args:
        db: Database session
        firebase_uid: Firebase Authentication UID

    Returns:
        Created Project instance
    """
    project = Project(
        firebase_uid=firebase_uid,
        name="FM Radio Circuit Design",
        description="Building a frequency modulation radio receiver circuit",
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    print(f"✅ Created project: {project.name} (ID: {project.id})")
    return project


def get_user_projects(db: Session, firebase_uid: str, skip: int = 0, limit: int = 10):
    """
    Example: Get all projects for a user with pagination.

    Args:
        db: Database session
        firebase_uid: Firebase Authentication UID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of Project instances
    """
    projects = (
        db.query(Project)
        .filter(Project.firebase_uid == firebase_uid)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    print(f"📋 Found {len(projects)} project(s) for user {firebase_uid}")
    return projects


def get_project_by_id(db: Session, project_id: str, firebase_uid: str):
    """
    Example: Get a specific project by ID (with ownership verification).

    Args:
        db: Database session
        project_id: Project UUID
        firebase_uid: Firebase Authentication UID (for verification)

    Returns:
        Project instance or None
    """
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.firebase_uid == firebase_uid,  # Ensure user owns this project
        )
        .first()
    )

    if project:
        print(f"✅ Found project: {project.name}")
    else:
        print(f"❌ Project not found or unauthorized")

    return project


def update_project_example(db: Session, project_id: str, firebase_uid: str):
    """
    Example: Update a project.

    Args:
        db: Database session
        project_id: Project UUID
        firebase_uid: Firebase Authentication UID

    Returns:
        Updated Project instance or None
    """
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.firebase_uid == firebase_uid)
        .first()
    )

    if not project:
        print(f"❌ Project not found or unauthorized")
        return None

    # Update fields
    project.name = "Updated: FM Radio Circuit"
    project.description = "Updated description with new components"

    db.commit()
    db.refresh(project)

    print(f"✅ Updated project: {project.name}")
    return project


def delete_project_example(db: Session, project_id: str, firebase_uid: str):
    """
    Example: Delete a project (and all its circuit sources via CASCADE).

    Args:
        db: Database session
        project_id: Project UUID
        firebase_uid: Firebase Authentication UID

    Returns:
        True if deleted, False otherwise
    """
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.firebase_uid == firebase_uid)
        .first()
    )

    if not project:
        print(f"❌ Project not found or unauthorized")
        return False

    db.delete(project)
    db.commit()

    print(f"✅ Deleted project: {project.name}")
    return True


def create_circuit_source_example(db: Session, project_id: str):
    """
    Example: Add a circuit source to a project.

    Args:
        db: Database session
        project_id: Project UUID

    Returns:
        Created CircuitSource instance
    """
    source = CircuitSource(
        project_id=project_id,
        title="FM Receiver Circuit Diagram",
        source_name="Electronics Hub",
        source_url="https://example.com/fm-receiver",
        image_url="https://example.com/circuit-diagram.png",
        description="Complete FM receiver circuit with component values",
    )

    db.add(source)
    db.commit()
    db.refresh(source)

    print(f"✅ Created circuit source: {source.title}")
    return source


def get_project_sources(db: Session, project_id: str):
    """
    Example: Get all circuit sources for a project.

    Args:
        db: Database session
        project_id: Project UUID

    Returns:
        List of CircuitSource instances
    """
    sources = (
        db.query(CircuitSource)
        .filter(CircuitSource.project_id == project_id)
        .order_by(CircuitSource.created_at.desc())
        .all()
    )

    print(f"📋 Found {len(sources)} circuit source(s) for project {project_id}")
    return sources


def get_project_with_sources(db: Session, project_id: str, firebase_uid: str):
    """
    Example: Get a project with all its circuit sources (using relationship).

    Args:
        db: Database session
        project_id: Project UUID
        firebase_uid: Firebase Authentication UID

    Returns:
        Project instance with circuit_sources loaded
    """
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.firebase_uid == firebase_uid)
        .first()
    )

    if not project:
        print(f"❌ Project not found or unauthorized")
        return None

    # Access circuit sources through relationship
    sources_count = project.circuit_sources.count()
    print(f"✅ Project '{project.name}' has {sources_count} circuit source(s)")

    return project


def run_examples():
    """Run all example CRUD operations."""
    print("🔧 SpiceCraft Database CRUD Examples")
    print("=" * 50)
    print()

    # Create a database session
    db = SessionLocal()

    try:
        # Simulate a Firebase authenticated user
        test_firebase_uid = "firebase-test-user-123"

        # 1. Create a project
        print("1️⃣  Creating a project...")
        project = create_project_example(db, test_firebase_uid)
        print()

        # 2. Get user's projects
        print("2️⃣  Getting user's projects...")
        projects = get_user_projects(db, test_firebase_uid)
        print()

        # 3. Add circuit sources
        print("3️⃣  Adding circuit sources...")
        source1 = create_circuit_source_example(db, str(project.id))
        source2 = create_circuit_source_example(db, str(project.id))
        print()

        # 4. Get project with sources
        print("4️⃣  Getting project with sources...")
        project_with_sources = get_project_with_sources(
            db, str(project.id), test_firebase_uid
        )
        print()

        # 5. Update project
        print("5️⃣  Updating project...")
        updated_project = update_project_example(db, str(project.id), test_firebase_uid)
        print()

        # 6. Get all sources for a project
        print("6️⃣  Getting all circuit sources...")
        all_sources = get_project_sources(db, str(project.id))
        print()

        print("=" * 50)
        print("✨ All examples completed successfully!")
        print()
        print("Note: These are examples. In production, delete test data:")
        print(f"   - Project ID: {project.id}")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    run_examples()
