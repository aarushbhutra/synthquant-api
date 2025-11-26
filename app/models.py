"""
Pydantic models for request/response schemas.
Defines all data structures used in the API.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==================== Request Models ====================

class AssetInput(BaseModel):
    """Single asset configuration for dataset creation."""
    symbol: str = Field(..., description="Asset symbol (e.g., 'BTC', 'ETH')")
    start_price: float = Field(..., gt=0, description="Starting price for the asset")


class DatasetCreateRequest(BaseModel):
    """Request body for creating a new synthetic dataset."""
    project: str = Field(..., min_length=1, max_length=100, description="Project name")
    assets: List[AssetInput] = Field(..., min_length=1, description="List of assets to simulate")
    frequency: str = Field(default="1h", description="Data frequency (1m, 5m, 15m, 30m, 1h, 4h, 1d)")
    horizon_days: int = Field(..., gt=0, le=365, description="Number of days to simulate")
    seed: int = Field(..., description="Random seed for reproducibility")


class ApiKeyVerifyRequest(BaseModel):
    """Request body for API key verification."""
    api_key: str = Field(..., description="API key to verify")


# ==================== Response Models ====================

class StatusResponse(BaseModel):
    """Response for service status endpoint."""
    service: str = "ok"
    timestamp: str
    note: str = "Simulation Mode"


class ApiKeyVerifyResponse(BaseModel):
    """Response for API key verification."""
    valid: bool
    quota_remaining: int
    limit: int


class AssetPreview(BaseModel):
    """Preview data for a single asset."""
    symbol: str
    timestamps: List[str]
    prices: List[float]


class DatasetPreview(BaseModel):
    """Preview of dataset with first N rows."""
    assets: List[AssetPreview]


class DatasetMetadata(BaseModel):
    """Metadata for a generated dataset."""
    dataset_id: str
    project: str
    assets: List[str]
    frequency: str
    horizon_days: int
    seed: int
    total_rows: int
    created_at: str
    status: str = "ready"
    realism_score: float


class DatasetCreateResponse(BaseModel):
    """Response for dataset creation."""
    dataset_id: str
    status: str = "ready"
    realism_score: float
    download_url: str
    preview: DatasetPreview


class DatasetDetailResponse(BaseModel):
    """Response for dataset detail endpoint."""
    metadata: DatasetMetadata
    preview: DatasetPreview


class DatasetListResponse(BaseModel):
    """Response for listing all datasets."""
    datasets: List[DatasetMetadata]
    total_count: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None


class RateLimitExceededResponse(BaseModel):
    """Response when rate limit is exceeded."""
    detail: str = "Rate limit exceeded"
    retry_after_seconds: int
