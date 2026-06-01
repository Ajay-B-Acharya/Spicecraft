import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)


def create_project(db: Session, firebase_uid: str, data: ProjectCreate) -> Project:
    project = Project(
        firebase_uid=firebase_uid,
        name=data.name,
        description=data.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Created project %s for user %s", project.id, firebase_uid)
    return project


def get_projects(db: Session, firebase_uid: str) -> list[Project]:
    projects = (
        db.query(Project)
        .filter(Project.firebase_uid == firebase_uid)
        .order_by(Project.created_at.desc())
        .all()
    )
    logger.info("Fetched %d project(s) for user %s", len(projects), firebase_uid)
    return projects


def get_project(db: Session, firebase_uid: str, project_id: UUID) -> Project | None:
    return (
        db.query(Project)
        .filter(Project.id == project_id, Project.firebase_uid == firebase_uid)
        .first()
    )


def update_project(
    db: Session,
    firebase_uid: str,
    project_id: UUID,
    data: ProjectUpdate,
) -> Project | None:
    project = get_project(db, firebase_uid, project_id)
    if not project:
        return None
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    db.commit()
    db.refresh(project)
    logger.info("Updated project %s", project_id)
    return project


def delete_project(db: Session, firebase_uid: str, project_id: UUID) -> bool:
    project = get_project(db, firebase_uid, project_id)
    if not project:
        return False
    db.delete(project)
    db.commit()
    logger.info("Deleted project %s", project_id)
    return True
