"""
Security module for API key validation and rate limiting.
Implements FastAPI dependencies for authentication and throttling.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from fastapi import Header, HTTPException, Depends, status

from app.config import (
    VALID_API_KEYS,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)
from app.store import store, RateLimitRecord


class APIKeyValidator:
    """Validates API keys against the configured set and dynamic store."""

    @staticmethod
    def is_valid(api_key: str) -> bool:
        """Check if an API key is valid (from config or dynamically added)."""
        # Check static keys from config
        if api_key in VALID_API_KEYS:
            return True
        # Check dynamically added keys from store
        return store.has_key(api_key)


class RateLimiter:
    """
    Rate limiter implementation using sliding window approach.
    Tracks requests per API key within a time window.
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check_and_update(self, api_key: str) -> Tuple[bool, int, int]:
        """
        Check rate limit and update counter.
        
        Returns:
            Tuple of (is_allowed, remaining_quota, retry_after_seconds)
        """
        now = datetime.utcnow()
        record = store.get_rate_limit_record(api_key)
        
        # Check if we're in a new window
        window_end = record.window_start + timedelta(seconds=self.window_seconds)
        
        if now >= window_end:
            # Start a new window
            new_record = RateLimitRecord(request_count=1, window_start=now)
            store.update_rate_limit(api_key, new_record)
            return True, self.max_requests - 1, 0
        
        # Still in the same window
        if record.request_count >= self.max_requests:
            # Rate limit exceeded
            retry_after = int((window_end - now).total_seconds()) + 1
            return False, 0, retry_after
        
        # Increment counter
        record.request_count += 1
        store.update_rate_limit(api_key, record)
        remaining = self.max_requests - record.request_count
        return True, remaining, 0

    def get_status(self, api_key: str) -> Tuple[int, int]:
        """
        Get current rate limit status without incrementing.
        
        Returns:
            Tuple of (remaining_quota, limit)
        """
        now = datetime.utcnow()
        record = store.get_rate_limit_record(api_key)
        
        # Check if we're in a new window
        window_end = record.window_start + timedelta(seconds=self.window_seconds)
        
        if now >= window_end:
            # Would be a new window, full quota available
            return self.max_requests, self.max_requests
        
        remaining = max(0, self.max_requests - record.request_count)
        return remaining, self.max_requests


# Global rate limiter instance
rate_limiter = RateLimiter()


async def validate_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
) -> str:
    """
    FastAPI dependency for API key validation.
    Raises 401 if key is missing or invalid.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Please provide X-API-KEY header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if not APIKeyValidator.is_valid(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return x_api_key


async def check_rate_limit(api_key: str = Depends(validate_api_key)) -> str:
    """
    FastAPI dependency for rate limiting.
    Must be used after validate_api_key.
    Raises 429 if rate limit exceeded.
    """
    is_allowed, remaining, retry_after = rate_limiter.check_and_update(api_key)
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    
    return api_key


def verify_api_key_status(api_key: str) -> Tuple[bool, int, int]:
    """
    Verify an API key and get its rate limit status.
    Used for the /apikeys/verify endpoint.
    
    Returns:
        Tuple of (is_valid, remaining_quota, limit)
    """
    is_valid = APIKeyValidator.is_valid(api_key)
    
    if not is_valid:
        return False, 0, RATE_LIMIT_REQUESTS
    
    remaining, limit = rate_limiter.get_status(api_key)
    return True, remaining, limit
