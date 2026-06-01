from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CircuitSourceBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    source_name: str | None = Field(None, max_length=255)
    source_url: str | None = None
    image_url: str | None = None


class CircuitSourceCreate(CircuitSourceBase):
    project_id: UUID


class CircuitSourceUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    source_name: str | None = Field(None, max_length=255)
    source_url: str | None = None
    image_url: str | None = None


class CircuitSourceResponse(CircuitSourceBase):
    id: UUID
    project_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
