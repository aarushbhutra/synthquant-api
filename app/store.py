"""
Database CRUD operations layer.
Provides async functions for interacting with the PostgreSQL database.
Replaces the previous in-memory dictionary store.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import uuid
import json

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_db import ApiKey, Dataset, RateLimit


# ====================================================================================
# API KEY OPERATIONS
# ====================================================================================

async def get_api_key(db: AsyncSession, key: str) -> Optional[ApiKey]:
    """
    Retrieve an API key record by its key value.
    
    Args:
        db: Database session.
        key: The API key string to look up.
    
    Returns:
        ApiKey model if found, None otherwise.
    """
    stmt = select(ApiKey).where(ApiKey.key == key, ApiKey.is_active == True)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_api_key(
    db: AsyncSession,
    key: str,
    user_id: str,
    label: str = "Default",
) -> ApiKey:
    """
    Create a new API key in the database.
    
    Args:
        db: Database session.
        key: The API key string.
        user_id: The Supabase user ID.
        label: User-friendly label for the key.
    
    Returns:
        The created ApiKey model.
    """
    api_key = ApiKey(
        key=key,
        user_id=user_id,
        label=label,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key


async def deactivate_api_key(db: AsyncSession, key: str) -> bool:
    """
    Deactivate an API key (soft delete).
    
    Args:
        db: Database session.
        key: The API key string to deactivate.
    
    Returns:
        True if key was found and deactivated, False otherwise.
    """
    stmt = (
        update(ApiKey)
        .where(ApiKey.key == key)
        .values(is_active=False)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def list_api_keys_for_user(db: AsyncSession, user_id: str) -> List[ApiKey]:
    """
    List all active API keys for a user.
    
    Args:
        db: Database session.
        user_id: The Supabase user ID.
    
    Returns:
        List of ApiKey models.
    """
    stmt = (
        select(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.is_active == True)
        .order_by(ApiKey.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ====================================================================================
# DATASET OPERATIONS
# ====================================================================================

def generate_dataset_id() -> str:
    """Generate a unique dataset ID using UUID."""
    return f"ds-{uuid.uuid4().hex[:12]}"


async def create_dataset(
    db: AsyncSession,
    user_id: str,
    project_name: str,
    config: Dict[str, Any],
    realism_score: Optional[float] = None,
    dataset_id: Optional[str] = None,
) -> Dataset:
    """
    Create a new dataset record in the database.
    
    Args:
        db: Database session.
        user_id: The owner's user ID.
        project_name: Project name for the dataset.
        config: JSON-serializable config containing assets, events, params, and data.
        realism_score: Optional realism score.
        dataset_id: Optional custom ID (generates UUID if not provided).
    
    Returns:
        The created Dataset model.
    """
    dataset = Dataset(
        id=dataset_id or generate_dataset_id(),
        user_id=user_id,
        project_name=project_name,
        config=config,
        status="completed",
        realism_score=realism_score,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def get_dataset(db: AsyncSession, dataset_id: str) -> Optional[Dataset]:
    """
    Retrieve a dataset by its ID.
    
    Args:
        db: Database session.
        dataset_id: The dataset's unique ID.
    
    Returns:
        Dataset model if found, None otherwise.
    """
    stmt = select(Dataset).where(Dataset.id == dataset_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_dataset_for_user(
    db: AsyncSession,
    dataset_id: str,
    user_id: str,
) -> Optional[Dataset]:
    """
    Retrieve a dataset by ID, verifying ownership.
    
    Args:
        db: Database session.
        dataset_id: The dataset's unique ID.
        user_id: The expected owner's user ID.
    
    Returns:
        Dataset model if found and owned by user, None otherwise.
    """
    stmt = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_datasets(db: AsyncSession, user_id: Optional[str] = None) -> List[Dataset]:
    """
    List datasets, optionally filtered by user.
    
    Args:
        db: Database session.
        user_id: Optional user ID to filter by.
    
    Returns:
        List of Dataset models.
    """
    if user_id:
        stmt = (
            select(Dataset)
            .where(Dataset.user_id == user_id)
            .order_by(Dataset.created_at.desc())
        )
    else:
        stmt = select(Dataset).order_by(Dataset.created_at.desc())
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_dataset(db: AsyncSession, dataset_id: str) -> bool:
    """
    Delete a dataset by ID.
    
    Args:
        db: Database session.
        dataset_id: The dataset's unique ID.
    
    Returns:
        True if deleted, False if not found.
    """
    stmt = delete(Dataset).where(Dataset.id == dataset_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def update_dataset_status(
    db: AsyncSession,
    dataset_id: str,
    status: str,
    realism_score: Optional[float] = None,
) -> bool:
    """
    Update a dataset's status.
    
    Args:
        db: Database session.
        dataset_id: The dataset's unique ID.
        status: New status value.
        realism_score: Optional realism score to set.
    
    Returns:
        True if updated, False if not found.
    """
    values = {"status": status}
    if realism_score is not None:
        values["realism_score"] = realism_score
    
    stmt = update(Dataset).where(Dataset.id == dataset_id).values(**values)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


# ====================================================================================
# RATE LIMITING OPERATIONS
# ====================================================================================

async def get_rate_limit_record(db: AsyncSession, api_key: str) -> Optional[RateLimit]:
    """
    Get the rate limit record for an API key.
    
    Args:
        db: Database session.
        api_key: The API key string.
    
    Returns:
        RateLimit model if exists, None otherwise.
    """
    stmt = select(RateLimit).where(RateLimit.api_key == api_key)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_rate_limit(
    db: AsyncSession,
    api_key: str,
    request_count: int,
    window_start: datetime,
) -> RateLimit:
    """
    Create or update rate limit record for an API key.
    
    Args:
        db: Database session.
        api_key: The API key string.
        request_count: Current request count.
        window_start: Start of the current rate limit window.
    
    Returns:
        The updated or created RateLimit model.
    """
    existing = await get_rate_limit_record(db, api_key)
    
    if existing:
        existing.request_count = request_count
        existing.window_start = window_start
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        rate_limit = RateLimit(
            api_key=api_key,
            request_count=request_count,
            window_start=window_start,
        )
        db.add(rate_limit)
        await db.commit()
        await db.refresh(rate_limit)
        return rate_limit


async def reset_rate_limit(db: AsyncSession, api_key: str) -> None:
    """
    Reset rate limit for an API key.
    
    Args:
        db: Database session.
        api_key: The API key string.
    """
    stmt = delete(RateLimit).where(RateLimit.api_key == api_key)
    await db.execute(stmt)
    await db.commit()


# ====================================================================================
# LEGACY COMPATIBILITY LAYER
# ====================================================================================
# These classes maintain backward compatibility with existing code that uses
# the old synchronous InMemoryStore pattern. They will be gradually deprecated.

from dataclasses import dataclass, field
from typing import Dict
import threading
import pandas as pd


@dataclass
class DatasetRecord:
    """Legacy dataclass for backward compatibility with existing code."""
    dataset_id: str
    project: str
    assets: List[str]
    frequency: str
    horizon_days: int
    seed: int
    total_rows: int
    created_at: str
    realism_score: float
    data: Dict[str, pd.DataFrame]


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


@dataclass
class RateLimitRecord:
    """Legacy rate limit record for backward compatibility."""
    request_count: int = 0
    window_start: datetime = field(default_factory=_utc_now)


class InMemoryStore:
    """
    Legacy in-memory store for backward compatibility.
    
    DEPRECATED: This class is maintained for backward compatibility during
    the migration to PostgreSQL. New code should use the async CRUD functions
    directly with database sessions.
    
    Rate limiting is still handled in-memory for performance reasons,
    but API keys and datasets are now stored in PostgreSQL.
    """
    _instance: Optional['InMemoryStore'] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> 'InMemoryStore':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            # Keep in-memory caches for fast lookups during transition
            self._datasets: Dict[str, DatasetRecord] = {}
            self._datasets_lock = threading.RLock()
            
            # Rate limiting stays in memory for performance
            self._rate_limits: Dict[str, RateLimitRecord] = {}
            self._rate_limits_lock = threading.RLock()
            
            self._dataset_counter = 0
            self._counter_lock = threading.Lock()
            
            # API keys cache (actual storage in PostgreSQL)
            self._api_keys: set = set()
            self._api_keys_lock = threading.RLock()
            
            self._initialized = True

    def generate_dataset_id(self) -> str:
        """Generate a unique dataset ID."""
        with self._counter_lock:
            self._dataset_counter += 1
            return f"ds-{self._dataset_counter:06d}"

    # Dataset Operations (in-memory cache, will sync to DB)
    def store_dataset(self, record: DatasetRecord) -> None:
        with self._datasets_lock:
            self._datasets[record.dataset_id] = record

    def get_dataset(self, dataset_id: str) -> Optional[DatasetRecord]:
        with self._datasets_lock:
            return self._datasets.get(dataset_id)

    def list_datasets(self) -> List[DatasetRecord]:
        with self._datasets_lock:
            return list(self._datasets.values())

    def delete_dataset(self, dataset_id: str) -> bool:
        with self._datasets_lock:
            if dataset_id in self._datasets:
                del self._datasets[dataset_id]
                return True
            return False

    # Rate Limiting (stays in memory)
    def get_rate_limit_record(self, api_key: str) -> RateLimitRecord:
        with self._rate_limits_lock:
            if api_key not in self._rate_limits:
                self._rate_limits[api_key] = RateLimitRecord()
            return self._rate_limits[api_key]

    def update_rate_limit(self, api_key: str, record: RateLimitRecord) -> None:
        with self._rate_limits_lock:
            self._rate_limits[api_key] = record

    def reset_rate_limit(self, api_key: str) -> None:
        with self._rate_limits_lock:
            self._rate_limits[api_key] = RateLimitRecord()

    # API Key Operations (cache, actual storage in DB)
    def add_key(self, key: str) -> None:
        with self._api_keys_lock:
            self._api_keys.add(key)

    def remove_key(self, key: str) -> bool:
        with self._api_keys_lock:
            if key in self._api_keys:
                self._api_keys.discard(key)
                return True
            return False

    def has_key(self, key: str) -> bool:
        with self._api_keys_lock:
            return key in self._api_keys

    def list_keys(self) -> List[str]:
        with self._api_keys_lock:
            return list(self._api_keys)

    def clear_all(self) -> None:
        with self._datasets_lock:
            self._datasets.clear()
        with self._rate_limits_lock:
            self._rate_limits.clear()
        with self._counter_lock:
            self._dataset_counter = 0
        with self._api_keys_lock:
            self._api_keys.clear()


# Global store instance (legacy compatibility)
store = InMemoryStore()
