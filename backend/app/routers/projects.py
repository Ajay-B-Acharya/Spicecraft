import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_firebase_uid
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import project_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    logger.info("POST /projects — user=%s name=%r", firebase_uid, data.name)
    project = project_service.create_project(db, firebase_uid, data)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> list[ProjectResponse]:
    logger.info("GET /projects — user=%s", firebase_uid)
    return project_service.get_projects(db, firebase_uid)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = project_service.get_project(db, firebase_uid, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = project_service.update_project(db, firebase_uid, project_id, data)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> None:
    deleted = project_service.delete_project(db, firebase_uid, project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
