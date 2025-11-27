"""
Pydantic models for request/response schemas.
Defines all data structures used in the API.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


# ==================== Enums ====================

class EventTypeEnum(str, Enum):
    """Supported event types for scenario stress testing."""
    IPO = "ipo"
    CRASH = "crash"
    EARNINGS = "earnings"


# ==================== Event Models ====================

class EventSpec(BaseModel):
    """
    Specification for a market event to inject into synthetic data.
    
    Event Types:
    - ipo: Simulates limited history (NaN before trigger_step)
    - crash: Gradual price decline over duration_steps
    - earnings: Instant price gap (jump or drop) at trigger_step
    """
    type: EventTypeEnum = Field(
        ...,
        description="Event type: 'ipo', 'crash', or 'earnings'"
    )
    trigger_step: int = Field(
        ...,
        ge=0,
        description="Row index where the event starts (0-indexed)"
    )
    magnitude: Optional[float] = Field(
        default=None,
        description="Event magnitude: for crash (0.3 = 30% drop), for earnings (0.1 = +10%, -0.1 = -10%)"
    )
    duration: Optional[int] = Field(
        default=None,
        ge=1,
        description="Duration in steps (only used for crash events)"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "ipo",
                    "trigger_step": 10,
                },
                {
                    "type": "crash",
                    "trigger_step": 50,
                    "magnitude": 0.3,
                    "duration": 20,
                },
                {
                    "type": "earnings",
                    "trigger_step": 100,
                    "magnitude": 0.15,
                },
            ]
        }


# ==================== Request Models ====================

class AssetInput(BaseModel):
    """Single asset configuration for dataset creation."""
    symbol: str = Field(..., description="Asset symbol (e.g., 'BTC', 'ETH')")
    start_price: float = Field(..., gt=0, description="Starting price for the asset")


class RealAssetInput(BaseModel):
    """Asset configuration using real market data."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Stock symbol (e.g., 'AAPL', 'RELIANCE')")
    region: str = Field(default="US", pattern="^(US|IN)$", description="Market region: 'US' or 'IN'")
    volatility_multiplier: float = Field(default=1.0, ge=0.1, le=10.0, description="Multiply volatility by this factor")
    drift_multiplier: float = Field(default=1.0, ge=-5.0, le=5.0, description="Multiply drift by this factor")


class DatasetCreateRequest(BaseModel):
    """Request body for creating a new synthetic dataset."""
    project: str = Field(..., min_length=1, max_length=100, description="Project name")
    assets: List[AssetInput] = Field(..., min_length=1, description="List of assets to simulate")
    frequency: str = Field(default="1h", description="Data frequency (1m, 5m, 15m, 30m, 1h, 4h, 1d)")
    horizon_days: int = Field(..., gt=0, le=365, description="Number of days to simulate")
    seed: int = Field(..., description="Random seed for reproducibility")
    events: List[EventSpec] = Field(
        default=[],
        description="Optional list of market events to inject (IPO, crash, earnings shock)"
    )


class RealisticDatasetCreateRequest(BaseModel):
    """Request body for creating a synthetic dataset based on real market data."""
    project: str = Field(..., min_length=1, max_length=100, description="Project name")
    assets: List[RealAssetInput] = Field(..., min_length=1, description="List of real assets to base simulation on")
    frequency: str = Field(default="1h", description="Data frequency (1m, 5m, 15m, 30m, 1h, 4h, 1d)")
    horizon_days: int = Field(..., gt=0, le=365, description="Number of days to simulate")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility (optional)")
    events: List[EventSpec] = Field(
        default=[],
        description="Optional list of market events to inject (IPO, crash, earnings shock)"
    )


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
    prices: List[Optional[float]]  # Can be None for IPO events (pre-IPO rows)


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


# ==================== Market Profiler Models ====================

class MarketProfileRequest(BaseModel):
    """Request body for market profiling."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Stock symbol (e.g., 'AAPL', 'RELIANCE')")
    region: str = Field(default="US", pattern="^(US|IN)$", description="Market region: 'US' or 'IN'")


class MarketProfileResponse(BaseModel):
    """Response for market profiling endpoint."""
    symbol: str
    region: str
    mu: float = Field(..., description="Drift (mean daily log return)")
    sigma: float = Field(..., description="Volatility (std dev of log returns)")
    last_price: float = Field(..., description="Most recent closing price")
    data_points: int = Field(..., description="Number of data points used")
    fetched_at: str = Field(..., description="Timestamp when data was fetched")
    annualized_return: float = Field(..., description="Annualized expected return (mu * 252)")
    annualized_volatility: float = Field(..., description="Annualized volatility (sigma * sqrt(252))")

