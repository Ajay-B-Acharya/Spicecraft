"""
Pydantic schemas for Project model.
Used for request/response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    """Base schema with common project fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    # firebase_uid will be extracted from the authenticated user's token
    # No need to include it in the request body
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Schema for project responses."""

    id: UUID
    firebase_uid: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectWithSources(ProjectResponse):
    """Schema for project with circuit sources included."""

    circuit_sources: list = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProjectList(BaseModel):
    """Schema for paginated project list."""

    projects: list[ProjectResponse]
    total: int
    page: int = 1
    page_size: int = 10
