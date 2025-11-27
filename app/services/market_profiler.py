"""
Market Profiler Service.

Fetches real market data and calculates statistical parameters (mu, sigma)
for Geometric Brownian Motion simulation.
"""

import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple, TypedDict
import numpy as np
import pandas as pd
import yfinance as yf

from app.exceptions import AssetNotFound, InsufficientDataError


class MarketParameters(TypedDict):
    """Statistical parameters for GBM simulation."""
    mu: float           # Drift (mean daily return)
    sigma: float        # Volatility (std dev of returns)
    last_price: float   # Most recent closing price
    symbol: str         # Original symbol
    region: str         # Market region
    data_points: int    # Number of data points used
    fetched_at: str     # Timestamp of fetch


class CacheEntry(TypedDict):
    """Cache entry structure."""
    parameters: MarketParameters
    expires_at: datetime


class MarketProfiler:
    """
    Service for fetching real market data and calculating GBM parameters.
    
    Supports US and Indian (NSE) markets via yfinance.
    Implements in-memory caching to reduce API calls.
    """
    
    # Cache TTL in seconds (1 hour)
    CACHE_TTL_SECONDS = 3600
    
    # Minimum data points required for reliable statistics
    MIN_DATA_POINTS = 30
    
    def __init__(self):
        """Initialize the market profiler with an empty cache."""
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_lock = threading.RLock()
    
    def _get_cache_key(self, symbol: str, region: str) -> str:
        """Generate a cache key for a symbol/region pair."""
        return f"{region}:{symbol.upper()}"
    
    def _format_symbol(self, symbol: str, region: str) -> str:
        """
        Format symbol for yfinance based on region.
        
        Args:
            symbol: Raw symbol (e.g., "RELIANCE", "AAPL")
            region: Market region ("US", "IN")
        
        Returns:
            Formatted symbol for yfinance
        """
        symbol = symbol.upper().strip()
        
        if region.upper() == "IN":
            # Indian NSE stocks need .NS suffix
            if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
                return f"{symbol}.NS"
        
        return symbol
    
    def fetch_history(
        self,
        symbol: str,
        region: str = "US",
        period: str = "1y"
    ) -> pd.Series:
        """
        Fetch historical closing prices for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "RELIANCE")
            region: Market region ("US" or "IN")
            period: Time period for historical data (default: "1y")
        
        Returns:
            Pandas Series of closing prices with datetime index
        
        Raises:
            AssetNotFound: If the ticker doesn't exist or no data available
        """
        formatted_symbol = self._format_symbol(symbol, region)
        
        try:
            # Create ticker object
            ticker = yf.Ticker(formatted_symbol)
            
            # Fetch historical data
            hist = ticker.history(period=period)
            
            if hist.empty:
                raise AssetNotFound(
                    symbol=symbol,
                    region=region,
                    message=f"No historical data found for '{symbol}' in region '{region}'"
                )
            
            # Extract closing prices
            close_prices = hist["Close"]
            
            if close_prices.empty or len(close_prices) < self.MIN_DATA_POINTS:
                raise AssetNotFound(
                    symbol=symbol,
                    region=region,
                    message=f"Insufficient data for '{symbol}': got {len(close_prices)} points, need {self.MIN_DATA_POINTS}"
                )
            
            return close_prices
            
        except AssetNotFound:
            raise
        except Exception as e:
            raise AssetNotFound(
                symbol=symbol,
                region=region,
                message=f"Failed to fetch data for '{symbol}': {str(e)}"
            )
    
    def calculate_parameters(self, price_series: pd.Series) -> Dict[str, float]:
        """
        Calculate GBM parameters from a price series.
        
        Uses log returns for accurate continuous compounding calculations.
        
        Args:
            price_series: Pandas Series of prices
        
        Returns:
            Dictionary with mu, sigma, and last_price
        """
        # Ensure we have enough data
        if len(price_series) < self.MIN_DATA_POINTS:
            raise InsufficientDataError(
                symbol="unknown",
                required=self.MIN_DATA_POINTS,
                available=len(price_series)
            )
        
        # Calculate log returns: ln(P_t / P_{t-1})
        # Using vectorized pandas operations
        log_returns = np.log(price_series / price_series.shift(1)).dropna()
        
        # Calculate annualized parameters
        # mu: Mean daily log return (drift)
        mu = float(log_returns.mean())
        
        # sigma: Standard deviation of daily log returns (volatility)
        sigma = float(log_returns.std())
        
        # Get the most recent price
        last_price = float(price_series.iloc[-1])
        
        return {
            "mu": mu,
            "sigma": sigma,
            "last_price": last_price,
        }
    
    def get_parameters(
        self,
        symbol: str,
        region: str = "US",
        use_cache: bool = True
    ) -> MarketParameters:
        """
        Get GBM parameters for a symbol, with caching.
        
        This is the main method to use - it handles fetching, calculation,
        and caching automatically.
        
        Args:
            symbol: Stock symbol
            region: Market region ("US" or "IN")
            use_cache: Whether to use cached values (default: True)
        
        Returns:
            MarketParameters dictionary with all statistical data
        
        Raises:
            AssetNotFound: If the ticker doesn't exist
        """
        cache_key = self._get_cache_key(symbol, region)
        now = datetime.now(timezone.utc)
        
        # Check cache first
        if use_cache:
            with self._cache_lock:
                if cache_key in self._cache:
                    entry = self._cache[cache_key]
                    if entry["expires_at"] > now:
                        return entry["parameters"]
        
        # Fetch fresh data
        price_series = self.fetch_history(symbol, region)
        params = self.calculate_parameters(price_series)
        
        # Build full parameters object
        market_params: MarketParameters = {
            "mu": params["mu"],
            "sigma": params["sigma"],
            "last_price": params["last_price"],
            "symbol": symbol.upper(),
            "region": region.upper(),
            "data_points": len(price_series),
            "fetched_at": now.isoformat().replace("+00:00", "Z"),
        }
        
        # Update cache
        with self._cache_lock:
            self._cache[cache_key] = {
                "parameters": market_params,
                "expires_at": now + timedelta(seconds=self.CACHE_TTL_SECONDS),
            }
        
        return market_params
    
    def clear_cache(self, symbol: str = None, region: str = None) -> int:
        """
        Clear cached parameters.
        
        Args:
            symbol: Specific symbol to clear (None = clear all)
            region: Specific region to clear (None = all regions)
        
        Returns:
            Number of cache entries cleared
        """
        with self._cache_lock:
            if symbol is None and region is None:
                count = len(self._cache)
                self._cache.clear()
                return count
            
            if symbol and region:
                cache_key = self._get_cache_key(symbol, region)
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    return 1
                return 0
            
            # Clear by region
            keys_to_remove = []
            for key in self._cache:
                key_region = key.split(":")[0]
                if region and key_region == region.upper():
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
            
            return len(keys_to_remove)
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self._cache_lock:
            now = datetime.now(timezone.utc)
            valid_count = sum(
                1 for entry in self._cache.values()
                if entry["expires_at"] > now
            )
            return {
                "total_entries": len(self._cache),
                "valid_entries": valid_count,
                "expired_entries": len(self._cache) - valid_count,
            }


# Global singleton instance
market_profiler = MarketProfiler()
