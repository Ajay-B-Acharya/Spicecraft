"""
Circuit Source model for SpiceCraft.
Stores circuit references, articles, images, and resources linked to projects.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class CircuitSource(Base):
    """
    CircuitSource model - stores circuit references and resources.

    Each circuit source belongs to a project and contains references to
    external circuit designs, articles, images, or documentation.
    """

    __tablename__ = "circuit_sources"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Foreign key to projects
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent project",
    )

    # Circuit source details
    title = Column(
        String(500), nullable=False, comment="Title or name of the circuit source"
    )

    source_name = Column(
        String(255),
        nullable=True,
        comment="Name of the source (e.g., 'Electronics Hub', 'Circuit Digest')",
    )

    source_url = Column(Text, nullable=True, comment="URL to the original source")

    image_url = Column(
        Text, nullable=True, comment="URL to circuit diagram or schematic image"
    )

    # Optional metadata
    description = Column(
        Text, nullable=True, comment="Description or notes about this circuit source"
    )

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="UTC timestamp of creation",
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="UTC timestamp of last update",
    )

    # Relationships
    project = relationship("Project", back_populates="circuit_sources")

    # Indexes
    __table_args__ = (
        Index("ix_circuit_sources_project_id", "project_id"),
        Index("ix_circuit_sources_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<CircuitSource(id={self.id}, title='{self.title}', project_id={self.project_id})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "title": self.title,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "image_url": self.image_url,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
