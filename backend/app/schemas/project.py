from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .circuit_source import CircuitSourceResponse


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class ProjectResponse(ProjectBase):
    id: UUID
    firebase_uid: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectWithSources(ProjectResponse):
    circuit_sources: list[CircuitSourceResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
