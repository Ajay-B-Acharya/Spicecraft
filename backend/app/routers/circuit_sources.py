import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_firebase_uid
from app.schemas.circuit_source import (
    CircuitSourceCreate,
    CircuitSourceResponse,
    CircuitSourceUpdate,
)
from app.services import circuit_source_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["circuit-sources"])


class _SourceBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    source_name: str | None = Field(None, max_length=255)
    source_url: str | None = None
    image_url: str | None = None


@router.get(
    "/projects/{project_id}/sources", response_model=list[CircuitSourceResponse]
)
def list_sources(
    project_id: UUID,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> list[CircuitSourceResponse]:
    logger.info("GET /projects/%s/sources — user=%s", project_id, firebase_uid)
    sources = circuit_source_service.get_sources_for_project(
        db, firebase_uid, project_id
    )
    if sources is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return sources


@router.post(
    "/projects/{project_id}/sources",
    response_model=CircuitSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    project_id: UUID,
    body: _SourceBody,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> CircuitSourceResponse:
    logger.info(
        "POST /projects/%s/sources — user=%s title=%r",
        project_id,
        firebase_uid,
        body.title,
    )
    data = CircuitSourceCreate(
        project_id=project_id,
        title=body.title,
        source_name=body.source_name,
        source_url=body.source_url,
        image_url=body.image_url,
    )
    source = circuit_source_service.create_source(db, firebase_uid, project_id, data)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return source


@router.get("/sources/{source_id}", response_model=CircuitSourceResponse)
def get_source(
    source_id: UUID,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> CircuitSourceResponse:
    logger.info("GET /sources/%s — user=%s", source_id, firebase_uid)
    source = circuit_source_service.get_source(db, firebase_uid, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        )
    return source


@router.put("/sources/{source_id}", response_model=CircuitSourceResponse)
def update_source(
    source_id: UUID,
    data: CircuitSourceUpdate,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> CircuitSourceResponse:
    logger.info("PUT /sources/%s — user=%s", source_id, firebase_uid)
    source = circuit_source_service.update_source(db, firebase_uid, source_id, data)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        )
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: UUID,
    firebase_uid: str = Depends(get_current_firebase_uid),
    db: Session = Depends(get_db),
) -> None:
    logger.info("DELETE /sources/%s — user=%s", source_id, firebase_uid)
    deleted = circuit_source_service.delete_source(db, firebase_uid, source_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        )
