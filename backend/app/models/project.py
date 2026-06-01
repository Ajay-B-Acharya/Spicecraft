"""
Project model for SpiceCraft.
Stores user projects with Firebase UID as the user identifier.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    """
    Project model - stores user-created SpiceCraft projects.

    Each project belongs to a Firebase-authenticated user identified by firebase_uid.
    """

    __tablename__ = "projects"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Firebase user identifier (NOT a foreign key - Firebase handles auth)
    firebase_uid = Column(
        String(128), nullable=False, index=True, comment="Firebase Authentication UID"
    )

    # Project details
    name = Column(String(255), nullable=False, comment="Project name")

    description = Column(Text, nullable=True, comment="Project description")

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
    circuit_sources = relationship(
        "CircuitSource",
        back_populates="project",
        cascade="all, delete-orphan",  # Delete sources when project is deleted
        lazy="dynamic",  # Load sources on demand
    )

    # Indexes
    __table_args__ = (
        Index("ix_projects_firebase_uid", "firebase_uid"),
        Index("ix_projects_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', firebase_uid='{self.firebase_uid}')>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "firebase_uid": self.firebase_uid,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
