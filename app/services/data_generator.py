"""
Data Generator Service - The Dummy Data Generation Engine.
Implements Geometric Brownian Motion (GBM) for synthetic price path generation.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict
import numpy as np
import pandas as pd

from app.config import (
    DEFAULT_VOLATILITY,
    DEFAULT_DRIFT,
    SUPPORTED_FREQUENCIES,
    API_BASE_URL,
)
from app.models import (
    DatasetCreateRequest,
    AssetInput,
    DatasetPreview,
    AssetPreview,
    DatasetMetadata,
    DatasetCreateResponse,
)
from app.store import store, DatasetRecord
from app.services.event_manager import event_manager


def get_frequency_timedelta(frequency: str) -> timedelta:
    """Convert frequency string to timedelta."""
    freq_map = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1),
    }
    return freq_map.get(frequency, timedelta(hours=1))


def calculate_steps_per_day(frequency: str) -> int:
    """Calculate the number of steps per day for a given frequency."""
    steps_map = {
        "1m": 1440,    # 60 * 24
        "5m": 288,     # 12 * 24
        "15m": 96,     # 4 * 24
        "30m": 48,     # 2 * 24
        "1h": 24,
        "4h": 6,
        "1d": 1,
    }
    return steps_map.get(frequency, 24)


def generate_gbm_prices(
    start_price: float,
    num_steps: int,
    dt: float,
    seed: int,
    drift: float = DEFAULT_DRIFT,
    volatility: float = DEFAULT_VOLATILITY,
) -> np.ndarray:
    """
    Generate price path using Geometric Brownian Motion (GBM).
    
    The GBM model is defined by:
    dS = μ*S*dt + σ*S*dW
    
    Where:
    - S is the price
    - μ (mu) is the drift coefficient
    - σ (sigma) is the volatility
    - dW is a Wiener process (random walk)
    
    Discrete approximation:
    S(t+dt) = S(t) * exp((μ - σ²/2)*dt + σ*√dt*Z)
    
    Where Z ~ N(0,1)
    
    Args:
        start_price: Initial price
        num_steps: Number of time steps to generate
        dt: Time step size (fraction of a day)
        seed: Random seed for reproducibility
        drift: Expected return per time unit
        volatility: Standard deviation of returns
    
    Returns:
        NumPy array of prices
    """
    # Set seed for reproducibility
    rng = np.random.default_rng(seed)
    
    # Generate random shocks
    random_shocks = rng.standard_normal(num_steps)
    
    # Calculate log returns using GBM formula
    # S(t+dt) = S(t) * exp((μ - σ²/2)*dt + σ*√dt*Z)
    log_returns = (drift - 0.5 * volatility**2) * dt + volatility * np.sqrt(dt) * random_shocks
    
    # Calculate cumulative returns
    cumulative_returns = np.cumsum(log_returns)
    
    # Generate prices
    prices = start_price * np.exp(np.insert(cumulative_returns, 0, 0))
    
    return prices


def generate_timestamps(
    start_time: datetime,
    num_steps: int,
    frequency: str,
) -> List[datetime]:
    """Generate a list of timestamps for the price data."""
    delta = get_frequency_timedelta(frequency)
    timestamps = [start_time + i * delta for i in range(num_steps + 1)]
    return timestamps


def calculate_realism_score(prices: np.ndarray) -> float:
    """
    Calculate a mock "realism score" for the generated data.
    
    In a real implementation, this would use statistical tests
    to compare against real market data characteristics.
    
    For now, we use a simple heuristic based on:
    - Price path smoothness
    - Return distribution normality
    - Volatility clustering (dummy)
    """
    # Calculate returns
    returns = np.diff(prices) / prices[:-1]
    
    # Score components (all normalized to 0-100 range)
    
    # 1. Volatility reasonableness (should be in realistic range)
    volatility = np.std(returns)
    vol_score = min(100, max(0, 100 - abs(volatility - 0.02) * 1000))
    
    # 2. No extreme jumps (returns should mostly be within 3 std)
    outliers = np.sum(np.abs(returns) > 3 * volatility)
    outlier_ratio = outliers / len(returns)
    jump_score = max(0, 100 - outlier_ratio * 500)
    
    # 3. Path continuity (no zeros or negatives)
    continuity_score = 100 if np.all(prices > 0) else 50
    
    # 4. Some randomness bonus (mock - always add some points)
    randomness_bonus = 15
    
    # Weighted average
    final_score = (
        vol_score * 0.3 +
        jump_score * 0.3 +
        continuity_score * 0.2 +
        randomness_bonus
    )
    
    # Clamp to reasonable range and round
    return round(min(99.9, max(70.0, final_score)), 1)


def generate_dataset(request: DatasetCreateRequest) -> DatasetCreateResponse:
    """
    Generate a complete synthetic dataset based on the request.
    
    This is the main service function that:
    1. Validates the request
    2. Generates price paths for all assets
    3. Stores the dataset in memory
    4. Returns the response with metadata and preview
    """
    # Validate frequency
    if request.frequency not in SUPPORTED_FREQUENCIES:
        raise ValueError(f"Unsupported frequency: {request.frequency}. Supported: {SUPPORTED_FREQUENCIES}")
    
    # Calculate parameters
    steps_per_day = calculate_steps_per_day(request.frequency)
    total_steps = steps_per_day * request.horizon_days
    dt = 1.0 / steps_per_day  # Time step as fraction of day
    
    # Generate start time (current time, rounded to nearest frequency)
    start_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    
    # Generate timestamps
    timestamps = generate_timestamps(start_time, total_steps, request.frequency)
    timestamp_strings = [ts.isoformat() + "Z" for ts in timestamps]
    
    # Generate price data for each asset
    data_store: Dict[str, pd.DataFrame] = {}
    asset_previews: List[AssetPreview] = []
    
    for i, asset in enumerate(request.assets):
        # Use a unique seed per asset (base seed + asset index)
        asset_seed = request.seed + i * 1000
        
        prices = generate_gbm_prices(
            start_price=asset.start_price,
            num_steps=total_steps,
            dt=dt,
            seed=asset_seed,
        )
        
        # Create DataFrame for storage
        df = pd.DataFrame({
            "timestamp": timestamp_strings,
            "price": prices,
        })
        data_store[asset.symbol] = df
    
    # Apply events if any are specified
    if request.events:
        data_store = event_manager.apply_events_to_dict(
            data_store,
            request.events,
            price_column="price",
        )
    
    # Generate previews after events are applied
    asset_previews: List[AssetPreview] = []
    for asset in request.assets:
        df = data_store[asset.symbol]
        # Handle NaN values in preview (from IPO events)
        preview_prices = df["price"].head(10).tolist()
        preview_prices = [round(p, 4) if pd.notna(p) else None for p in preview_prices]
        
        preview = AssetPreview(
            symbol=asset.symbol,
            timestamps=df["timestamp"].head(10).tolist(),
            prices=preview_prices,
        )
        asset_previews.append(preview)
    
    # Calculate realism score (average across all assets, ignoring NaN)
    all_prices = []
    for a in request.assets:
        prices_arr = data_store[a.symbol]["price"].values
        valid_prices = prices_arr[~np.isnan(prices_arr)]
        if len(valid_prices) > 0:
            all_prices.append(valid_prices)
    
    if all_prices:
        all_prices = np.concatenate(all_prices)
        realism_score = calculate_realism_score(all_prices)
    else:
        realism_score = 0.0
    
    # Generate dataset ID and store
    dataset_id = store.generate_dataset_id()
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    record = DatasetRecord(
        dataset_id=dataset_id,
        project=request.project,
        assets=[a.symbol for a in request.assets],
        frequency=request.frequency,
        horizon_days=request.horizon_days,
        seed=request.seed,
        total_rows=total_steps + 1,
        created_at=created_at,
        realism_score=realism_score,
        data=data_store,
    )
    store.store_dataset(record)
    
    # Build response
    preview = DatasetPreview(assets=asset_previews)
    download_url = f"{API_BASE_URL}/v1/datasets/{dataset_id}/download"
    
    return DatasetCreateResponse(
        dataset_id=dataset_id,
        status="ready",
        realism_score=realism_score,
        download_url=download_url,
        preview=preview,
    )


def get_dataset_preview(record: DatasetRecord, num_rows: int = 10) -> DatasetPreview:
    """Extract a preview from a stored dataset record."""
    asset_previews: List[AssetPreview] = []
    
    for symbol in record.assets:
        df = record.data[symbol]
        preview = AssetPreview(
            symbol=symbol,
            timestamps=df["timestamp"].head(num_rows).tolist(),
            prices=[round(p, 4) for p in df["price"].head(num_rows).tolist()],
        )
        asset_previews.append(preview)
    
    return DatasetPreview(assets=asset_previews)


def record_to_metadata(record: DatasetRecord) -> DatasetMetadata:
    """Convert a DatasetRecord to DatasetMetadata."""
    return DatasetMetadata(
        dataset_id=record.dataset_id,
        project=record.project,
        assets=record.assets,
        frequency=record.frequency,
        horizon_days=record.horizon_days,
        seed=record.seed,
        total_rows=record.total_rows,
        created_at=record.created_at,
        status="ready",
        realism_score=record.realism_score,
    )
