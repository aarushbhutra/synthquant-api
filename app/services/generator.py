"""
Synthetic Data Generator Service.

Implements Geometric Brownian Motion (GBM) for synthetic price path generation
using real market parameters from the MarketProfiler.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, TypedDict, List
import numpy as np
import pandas as pd

from app.config import SUPPORTED_FREQUENCIES


class GeneratorConfig(TypedDict, total=False):
    """Configuration for synthetic data generation."""
    volatility_multiplier: float  # Multiply sigma by this factor (default: 1.0)
    drift_multiplier: float       # Multiply mu by this factor (default: 1.0)
    horizon_days: int             # Number of days to simulate
    frequency: str                # Target frequency (1m, 5m, 15m, 30m, 1h, 4h, 1d)


class SyntheticGenerator:
    """
    Generator for synthetic price paths using Geometric Brownian Motion.
    
    Takes real market parameters (mu, sigma) and generates synthetic
    time series at configurable frequencies.
    """
    
    # Steps per day for each frequency (assuming 24/7 trading for simplicity)
    STEPS_PER_DAY = {
        "1m": 1440,    # 60 * 24
        "5m": 288,     # 12 * 24
        "15m": 96,     # 4 * 24
        "30m": 48,     # 2 * 24
        "1h": 24,
        "4h": 6,
        "1d": 1,
    }
    
    # Time delta for each frequency
    FREQUENCY_DELTA = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1),
    }
    
    def __init__(self):
        """Initialize the synthetic generator."""
        pass
    
    def _get_steps_per_day(self, frequency: str) -> int:
        """Get the number of steps per day for a given frequency."""
        if frequency not in self.STEPS_PER_DAY:
            raise ValueError(f"Unsupported frequency: {frequency}. Supported: {list(self.STEPS_PER_DAY.keys())}")
        return self.STEPS_PER_DAY[frequency]
    
    def _scale_parameters(
        self,
        mu_daily: float,
        sigma_daily: float,
        steps_per_day: int,
    ) -> tuple[float, float]:
        """
        Scale daily parameters to the target frequency.
        
        For GBM, when scaling from daily to higher frequency:
        - mu scales linearly: mu_target = mu_daily / steps_per_day
        - sigma scales with sqrt: sigma_target = sigma_daily / sqrt(steps_per_day)
        
        Args:
            mu_daily: Daily drift (mean log return)
            sigma_daily: Daily volatility (std dev of log returns)
            steps_per_day: Number of steps per day for target frequency
        
        Returns:
            Tuple of (mu_scaled, sigma_scaled)
        """
        mu_scaled = mu_daily / steps_per_day
        sigma_scaled = sigma_daily / np.sqrt(steps_per_day)
        return mu_scaled, sigma_scaled
    
    def generate_path(
        self,
        base_params: Dict[str, float],
        config: Optional[GeneratorConfig] = None,
        seed: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Generate a synthetic price path using GBM.
        
        The GBM model:
        S_t = S_{t-1} * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
        
        Where Z ~ N(0,1)
        
        Args:
            base_params: Dictionary with keys:
                - mu: Daily drift (mean log return)
                - sigma: Daily volatility
                - last_price: Starting price for simulation
            config: Optional configuration overrides:
                - volatility_multiplier: Multiply sigma (default: 1.0)
                - drift_multiplier: Multiply mu (default: 1.0)
                - horizon_days: Days to simulate (default: 30)
                - frequency: Target frequency (default: "1h")
            seed: Random seed for reproducibility
        
        Returns:
            DataFrame with DatetimeIndex and 'Close' column
        """
        # Extract base parameters
        mu_daily = base_params.get("mu", 0.0)
        sigma_daily = base_params.get("sigma", 0.02)
        start_price = base_params.get("last_price", 100.0)
        
        # Apply config defaults
        config = config or {}
        volatility_multiplier = config.get("volatility_multiplier", 1.0)
        drift_multiplier = config.get("drift_multiplier", 1.0)
        horizon_days = config.get("horizon_days", 30)
        frequency = config.get("frequency", "1h")
        
        # Validate frequency
        if frequency not in SUPPORTED_FREQUENCIES:
            raise ValueError(f"Unsupported frequency: {frequency}. Supported: {SUPPORTED_FREQUENCIES}")
        
        # Calculate time parameters
        steps_per_day = self._get_steps_per_day(frequency)
        total_steps = steps_per_day * horizon_days
        dt = 1.0 / steps_per_day  # Time step as fraction of day
        
        # Scale parameters to target frequency
        mu_scaled, sigma_scaled = self._scale_parameters(mu_daily, sigma_daily, steps_per_day)
        
        # Apply user multipliers
        mu_adjusted = mu_scaled * drift_multiplier
        sigma_adjusted = sigma_scaled * volatility_multiplier
        
        # Set random seed if provided
        rng = np.random.default_rng(seed)
        
        # Generate random shocks (vectorized)
        Z = rng.standard_normal(total_steps)
        
        # Calculate log returns using GBM formula
        # S_t = S_{t-1} * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
        # Since we scaled mu and sigma to per-step values, dt=1 for the formula
        log_returns = (mu_adjusted - 0.5 * sigma_adjusted**2) + sigma_adjusted * Z
        
        # Calculate cumulative log returns
        cumulative_log_returns = np.cumsum(log_returns)
        
        # Generate prices (including start price at index 0)
        prices = np.zeros(total_steps + 1)
        prices[0] = start_price
        prices[1:] = start_price * np.exp(cumulative_log_returns)
        
        # Generate timestamps
        start_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        delta = self.FREQUENCY_DELTA[frequency]
        timestamps = [start_time + i * delta for i in range(total_steps + 1)]
        
        # Create DataFrame
        df = pd.DataFrame({
            "Close": prices,
        }, index=pd.DatetimeIndex(timestamps, name="Timestamp"))
        
        return df
    
    def generate_multiple_paths(
        self,
        base_params: Dict[str, float],
        num_paths: int,
        config: Optional[GeneratorConfig] = None,
        base_seed: Optional[int] = None,
    ) -> List[pd.DataFrame]:
        """
        Generate multiple synthetic price paths.
        
        Useful for Monte Carlo simulations.
        
        Args:
            base_params: Base market parameters
            num_paths: Number of paths to generate
            config: Generation configuration
            base_seed: Base seed (each path uses base_seed + path_index)
        
        Returns:
            List of DataFrames, each with a price path
        """
        paths = []
        for i in range(num_paths):
            seed = base_seed + i if base_seed is not None else None
            path = self.generate_path(base_params, config, seed)
            paths.append(path)
        return paths
    
    def calculate_path_statistics(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate statistics for a generated price path.
        
        Args:
            df: DataFrame with 'Close' column
        
        Returns:
            Dictionary with statistics
        """
        prices = df["Close"].values
        returns = np.diff(prices) / prices[:-1]
        log_returns = np.log(prices[1:] / prices[:-1])
        
        return {
            "start_price": float(prices[0]),
            "end_price": float(prices[-1]),
            "min_price": float(np.min(prices)),
            "max_price": float(np.max(prices)),
            "total_return": float((prices[-1] - prices[0]) / prices[0]),
            "volatility": float(np.std(returns)),
            "log_volatility": float(np.std(log_returns)),
            "sharpe_approx": float(np.mean(returns) / np.std(returns)) if np.std(returns) > 0 else 0.0,
        }


# Global singleton instance
synthetic_generator = SyntheticGenerator()
