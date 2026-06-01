"""Example CRUD operations for SpiceCraft Phase 3 models."""

from uuid import UUID

from app.database import SessionLocal
from app.models.circuit_source import CircuitSource
from app.models.project import Project
from sqlalchemy.orm import Session


def create_project_example(db: Session, firebase_uid: str) -> Project:
    """Create a new project for a Firebase-authenticated user."""
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


def get_user_projects(
    db: Session,
    firebase_uid: str,
    skip: int = 0,
    limit: int = 10,
) -> list[Project]:
    """Get a paginated list of projects owned by a Firebase user."""
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


def get_project_by_id(
    db: Session,
    project_id: UUID,
    firebase_uid: str,
) -> Project | None:
    """Get a specific project with ownership verification."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.firebase_uid == firebase_uid)
        .first()
    )
    if project:
        print(f"✅ Found project: {project.name}")
    else:
        print("❌ Project not found or unauthorized")
    return project


def update_project_example(
    db: Session,
    project_id: UUID,
    firebase_uid: str,
) -> Project | None:
    """Update a project after verifying ownership."""
    project = get_project_by_id(db, project_id, firebase_uid)
    if not project:
        return None

    project.name = "Updated FM Radio Circuit"
    project.description = "Updated description with revised component choices"
    db.commit()
    db.refresh(project)
    print(f"✅ Updated project: {project.name}")
    return project


def delete_project_example(db: Session, project_id: UUID, firebase_uid: str) -> bool:
    """Delete a project and its child circuit sources via cascade delete."""
    project = get_project_by_id(db, project_id, firebase_uid)
    if not project:
        return False

    db.delete(project)
    db.commit()
    print(f"✅ Deleted project: {project.name}")
    return True


def create_circuit_source_example(db: Session, project_id: UUID) -> CircuitSource:
    """Create a circuit source linked to a project."""
    source = CircuitSource(
        project_id=project_id,
        title="FM Receiver Circuit Diagram",
        source_name="Electronics Hub",
        source_url="https://example.com/fm-receiver",
        image_url="https://example.com/circuit-diagram.png",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    print(f"✅ Created circuit source: {source.title}")
    return source


def get_project_sources(db: Session, project_id: UUID) -> list[CircuitSource]:
    """Get all circuit sources for a project."""
    sources = (
        db.query(CircuitSource)
        .filter(CircuitSource.project_id == project_id)
        .order_by(CircuitSource.created_at.desc())
        .all()
    )
    print(f"📋 Found {len(sources)} circuit source(s) for project {project_id}")
    return sources


def get_project_with_sources(
    db: Session,
    project_id: UUID,
    firebase_uid: str,
) -> Project | None:
    """Get a project and access its related circuit sources."""
    project = get_project_by_id(db, project_id, firebase_uid)
    if not project:
        return None

    sources_count = len(project.circuit_sources)
    print(f"✅ Project '{project.name}' has {sources_count} circuit source(s)")
    return project


def run_examples() -> None:
    """Run all example CRUD operations."""
    print("🔧 SpiceCraft Database CRUD Examples")
    print("=" * 50)
    print()

    db = SessionLocal()
    try:
        test_firebase_uid = "firebase-test-user-123"

        print("1️⃣  Creating a project...")
        project = create_project_example(db, test_firebase_uid)
        print()

        print("2️⃣  Getting user's projects...")
        _projects = get_user_projects(db, test_firebase_uid)
        print()

        print("3️⃣  Adding circuit sources...")
        create_circuit_source_example(db, project.id)
        create_circuit_source_example(db, project.id)
        print()

        print("4️⃣  Getting project with sources...")
        get_project_with_sources(db, project.id, test_firebase_uid)
        print()

        print("5️⃣  Updating project...")
        update_project_example(db, project.id, test_firebase_uid)
        print()

        print("6️⃣  Getting all circuit sources...")
        get_project_sources(db, project.id)
        print()

        print("=" * 50)
        print("✨ All examples completed successfully!")
        print()
        print("Note: These are examples. In production, delete test data:")
        print(f"   - Project ID: {project.id}")

    except Exception as exc:
        print(f"❌ Error: {exc}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_examples()
