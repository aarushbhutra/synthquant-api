"""
SQLAlchemy ORM models for persistent database storage.
Defines tables for API keys and datasets.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class ApiKey(Base):
    """
    API Keys table for authentication.
    
    Note: In production, the `key` field should be hashed.
    For this MVP, we store it in plain text for simplicity.
    """
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Default")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Create composite index for common queries
    __table_args__ = (
        Index("ix_api_keys_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, key='{self.key[:10]}...', user_id='{self.user_id}')>"


class Dataset(Base):
    """
    Datasets table for storing generated synthetic data metadata.
    
    The actual price data is stored in the `config` JSON field
    along with generation parameters for reproducibility.
    """
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="processing",
    )
    realism_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Create index for listing user's datasets
    __table_args__ = (
        Index("ix_datasets_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Dataset(id='{self.id}', project='{self.project_name}', status='{self.status}')>"


class RateLimit(Base):
    """
    Rate limiting records table.
    
    Tracks request counts per API key within time windows
    for enforcing rate limits.
    """
    __tablename__ = "rate_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    def __repr__(self) -> str:
        return f"<RateLimit(api_key='{self.api_key[:10]}...', count={self.request_count})>"
