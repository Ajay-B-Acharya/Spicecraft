"""
Pydantic schemas for CircuitSource model.
Used for request/response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CircuitSourceBase(BaseModel):
    """Base schema with common circuit source fields."""

    title: str = Field(
        ..., min_length=1, max_length=500, description="Circuit source title"
    )
    source_name: Optional[str] = Field(None, max_length=255, description="Source name")
    source_url: Optional[str] = Field(None, description="URL to original source")
    image_url: Optional[str] = Field(None, description="URL to circuit image")
    description: Optional[str] = Field(None, description="Source description or notes")


class CircuitSourceCreate(CircuitSourceBase):
    """Schema for creating a new circuit source."""

    project_id: UUID = Field(..., description="Project ID this source belongs to")


class CircuitSourceUpdate(BaseModel):
    """Schema for updating an existing circuit source."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    source_name: Optional[str] = Field(None, max_length=255)
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None


class CircuitSourceResponse(CircuitSourceBase):
    """Schema for circuit source responses."""

    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CircuitSourceList(BaseModel):
    """Schema for paginated circuit source list."""

    circuit_sources: list[CircuitSourceResponse]
    total: int
    page: int = 1
    page_size: int = 10
