"""
In-memory data store singleton.
Thread-safe storage for datasets and rate limiting data.
"""

import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class DatasetRecord:
    """Represents a stored dataset with metadata and data."""
    dataset_id: str
    project: str
    assets: List[str]
    frequency: str
    horizon_days: int
    seed: int
    total_rows: int
    created_at: str
    realism_score: float
    data: Dict[str, pd.DataFrame]  # symbol -> DataFrame with timestamps and prices


@dataclass
class RateLimitRecord:
    """Tracks rate limiting for an API key."""
    request_count: int = 0
    window_start: datetime = field(default_factory=datetime.utcnow)


class InMemoryStore:
    """
    Thread-safe singleton for in-memory data storage.
    Stores generated datasets and rate limiting information.
    """
    _instance: Optional['InMemoryStore'] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> 'InMemoryStore':
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
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
            
            # Dataset storage: dataset_id -> DatasetRecord
            self._datasets: Dict[str, DatasetRecord] = {}
            self._datasets_lock = threading.RLock()
            
            # Rate limiting storage: api_key -> RateLimitRecord
            self._rate_limits: Dict[str, RateLimitRecord] = {}
            self._rate_limits_lock = threading.RLock()
            
            # Dataset ID counter
            self._dataset_counter = 0
            self._counter_lock = threading.Lock()
            
            # Dynamic API keys storage
            self._api_keys: set = set()
            self._api_keys_lock = threading.RLock()
            
            self._initialized = True

    def generate_dataset_id(self) -> str:
        """Generate a unique dataset ID."""
        with self._counter_lock:
            self._dataset_counter += 1
            return f"ds-{self._dataset_counter:06d}"

    # ==================== Dataset Operations ====================

    def store_dataset(self, record: DatasetRecord) -> None:
        """Store a dataset record."""
        with self._datasets_lock:
            self._datasets[record.dataset_id] = record

    def get_dataset(self, dataset_id: str) -> Optional[DatasetRecord]:
        """Retrieve a dataset by ID."""
        with self._datasets_lock:
            return self._datasets.get(dataset_id)

    def list_datasets(self) -> List[DatasetRecord]:
        """List all stored datasets."""
        with self._datasets_lock:
            return list(self._datasets.values())

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset. Returns True if deleted, False if not found."""
        with self._datasets_lock:
            if dataset_id in self._datasets:
                del self._datasets[dataset_id]
                return True
            return False

    # ==================== Rate Limiting Operations ====================

    def get_rate_limit_record(self, api_key: str) -> RateLimitRecord:
        """Get or create rate limit record for an API key."""
        with self._rate_limits_lock:
            if api_key not in self._rate_limits:
                self._rate_limits[api_key] = RateLimitRecord()
            return self._rate_limits[api_key]

    def update_rate_limit(self, api_key: str, record: RateLimitRecord) -> None:
        """Update rate limit record for an API key."""
        with self._rate_limits_lock:
            self._rate_limits[api_key] = record

    def reset_rate_limit(self, api_key: str) -> None:
        """Reset rate limit for an API key."""
        with self._rate_limits_lock:
            self._rate_limits[api_key] = RateLimitRecord()

    # ==================== API Key Operations ====================

    def add_key(self, key: str) -> None:
        """Add a new API key to the dynamic store."""
        with self._api_keys_lock:
            self._api_keys.add(key)

    def remove_key(self, key: str) -> bool:
        """Remove an API key. Returns True if removed, False if not found."""
        with self._api_keys_lock:
            if key in self._api_keys:
                self._api_keys.discard(key)
                return True
            return False

    def has_key(self, key: str) -> bool:
        """Check if a key exists in the dynamic store."""
        with self._api_keys_lock:
            return key in self._api_keys

    def list_keys(self) -> List[str]:
        """List all dynamically added API keys."""
        with self._api_keys_lock:
            return list(self._api_keys)

    # ==================== Utility Operations ====================

    def clear_all(self) -> None:
        """Clear all stored data (useful for testing)."""
        with self._datasets_lock:
            self._datasets.clear()
        with self._rate_limits_lock:
            self._rate_limits.clear()
        with self._counter_lock:
            self._dataset_counter = 0
        with self._api_keys_lock:
            self._api_keys.clear()


# Global store instance
store = InMemoryStore()
