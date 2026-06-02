import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.circuit_source import CircuitSource
from app.models.project import Project
from app.schemas.circuit_source import CircuitSourceCreate, CircuitSourceUpdate

logger = logging.getLogger(__name__)


def _owned_project(db: Session, firebase_uid: str, project_id: UUID) -> Project | None:
    return (
        db.query(Project)
        .filter(Project.id == project_id, Project.firebase_uid == firebase_uid)
        .first()
    )


def create_source(
    db: Session,
    firebase_uid: str,
    project_id: UUID,
    data: CircuitSourceCreate,
) -> CircuitSource | None:
    project = _owned_project(db, firebase_uid, project_id)
    if not project:
        return None
    source = CircuitSource(
        project_id=project_id,
        title=data.title,
        source_name=data.source_name,
        source_url=data.source_url,
        image_url=data.image_url,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    logger.info("Created circuit source %s for project %s", source.id, project_id)
    return source


def get_sources_for_project(
    db: Session,
    firebase_uid: str,
    project_id: UUID,
) -> list[CircuitSource] | None:
    project = _owned_project(db, firebase_uid, project_id)
    if not project:
        return None
    sources = (
        db.query(CircuitSource)
        .filter(CircuitSource.project_id == project_id)
        .order_by(CircuitSource.created_at.desc())
        .all()
    )
    logger.info(
        "Fetched %d source(s) for project %s (user %s)",
        len(sources),
        project_id,
        firebase_uid,
    )
    return sources


def get_source(
    db: Session,
    firebase_uid: str,
    source_id: UUID,
) -> CircuitSource | None:
    return (
        db.query(CircuitSource)
        .join(Project, CircuitSource.project_id == Project.id)
        .filter(CircuitSource.id == source_id, Project.firebase_uid == firebase_uid)
        .first()
    )


def update_source(
    db: Session,
    firebase_uid: str,
    source_id: UUID,
    data: CircuitSourceUpdate,
) -> CircuitSource | None:
    source = get_source(db, firebase_uid, source_id)
    if not source:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)

    db.commit()
    db.refresh(source)
    logger.info("Updated circuit source %s", source_id)
    return source


def delete_source(
    db: Session,
    firebase_uid: str,
    source_id: UUID,
) -> bool:
    source = get_source(db, firebase_uid, source_id)
    if not source:
        return False
    db.delete(source)
    db.commit()
    logger.info("Deleted circuit source %s", source_id)
    return True
