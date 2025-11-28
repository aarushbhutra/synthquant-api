"""
Event Manager Service.

Implements event injection for stress testing synthetic price paths.
Supports IPO simulation, market crashes, and earnings shocks.
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
import numpy as np
import pandas as pd
from enum import Enum

if TYPE_CHECKING:
    from app.models import EventSpec


class EventType(str, Enum):
    """Supported event types for injection."""
    IPO = "ipo"
    CRASH = "crash"
    EARNINGS = "earnings"


class EventManager:
    """
    Manager for applying market events to synthetic price paths.
    
    Supports three event types:
    - IPO: Simulates limited history (NaN before trigger point)
    - Crash: Linear/exponential decay over duration
    - Earnings: Sudden gap (jump or drop) at a specific point
    """
    
    def __init__(self):
        """Initialize the event manager."""
        pass
    
    def apply_events(
        self,
        df: pd.DataFrame,
        events: List["EventSpec"],
        price_column: str = "Close",
    ) -> pd.DataFrame:
        """
        Apply a list of events to a price DataFrame.
        
        Events are applied in order, so the sequence matters.
        Invalid events (e.g., trigger_step out of bounds) are skipped gracefully.
        
        Args:
            df: DataFrame with price data (must have the price_column)
            events: List of EventSpec objects defining the events
            price_column: Name of the column containing prices (default: "Close")
        
        Returns:
            Modified DataFrame with events applied
        """
        # Work on a copy to avoid side effects
        result = df.copy()
        
        if price_column not in result.columns:
            # Try to find a price-like column
            price_cols = [c for c in result.columns if c.lower() in ("close", "price", "prices")]
            if price_cols:
                price_column = price_cols[0]
            else:
                # Return unchanged if no price column found
                return result
        
        for event in events:
            try:
                event_type = event.type.lower()
                
                if event_type == EventType.IPO:
                    result = self._apply_ipo(
                        result,
                        trigger_step=event.trigger_step,
                        price_column=price_column,
                    )
                elif event_type == EventType.CRASH:
                    result = self._apply_crash(
                        result,
                        trigger_step=event.trigger_step,
                        magnitude=event.magnitude or 0.3,
                        duration_steps=event.duration or 10,
                        price_column=price_column,
                    )
                elif event_type == EventType.EARNINGS:
                    result = self._apply_earnings_shock(
                        result,
                        trigger_step=event.trigger_step,
                        magnitude=event.magnitude or 0.1,
                        price_column=price_column,
                    )
                else:
                    # Unknown event type, skip
                    continue
                    
            except Exception as e:
                # Log error but continue processing other events
                # In production, you might want to log this properly
                print(f"Warning: Failed to apply event {event}: {e}")
                continue
        
        return result
    
    def _apply_ipo(
        self,
        df: pd.DataFrame,
        trigger_step: int,
        price_column: str,
    ) -> pd.DataFrame:
        """
        Apply IPO event - set all prices before trigger_step to NaN.
        
        This simulates a stock that didn't exist before the IPO date,
        useful for backtesting strategies that need to handle limited history.
        
        Args:
            df: DataFrame with price data
            trigger_step: Row index where the stock "goes public"
            price_column: Name of the price column
        
        Returns:
            Modified DataFrame with pre-IPO rows set to NaN
        """
        if trigger_step < 0 or trigger_step >= len(df):
            # Out of bounds, return unchanged
            return df
        
        result = df.copy()
        
        # Set all prices before trigger_step to NaN
        result.iloc[:trigger_step, result.columns.get_loc(price_column)] = np.nan
        
        return result
    
    def _apply_crash(
        self,
        df: pd.DataFrame,
        trigger_step: int,
        magnitude: float,
        duration_steps: int,
        price_column: str,
        seed: int = None,
    ) -> pd.DataFrame:
        """
        Apply a realistic market crash event with true randomness.
        
        Simulates realistic crash behavior with:
        - Random walk downward with high volatility
        - Small occasional bounces (1-3% max)
        - Varying intensity of drops
        - Different shape each time (unless seed is fixed)
        
        Args:
            df: DataFrame with price data
            trigger_step: Row index where crash begins
            magnitude: Total drop as decimal (0.3 = 30% drop)
            duration_steps: Number of steps over which the crash occurs
            price_column: Name of the price column
            seed: Optional seed for reproducibility (None = random each time)
        
        Returns:
            Modified DataFrame with realistic crash applied
        """
        if trigger_step < 0 or trigger_step >= len(df):
            return df
        
        if magnitude <= 0 or magnitude >= 1:
            magnitude = min(0.99, max(0.01, magnitude))
        
        if duration_steps < 1:
            duration_steps = 1
        
        result = df.copy()
        prices = result[price_column].values.copy()
        n = len(prices)
        
        # Use random seed - if None, each run is different
        # Use timestamp-based seed for true randomness when seed not provided
        if seed is None:
            import time
            seed = int(time.time() * 1000) % (2**31)
        rng = np.random.RandomState(seed=seed)
        
        crash_end = min(trigger_step + duration_steps, n)
        actual_duration = crash_end - trigger_step
        
        if actual_duration < 1:
            return result
        
        # ===== STOCHASTIC CRASH MODEL =====
        # Generate random returns that sum to approximately -magnitude
        
        # Average return needed per step to achieve magnitude drop
        avg_return = -magnitude / actual_duration
        
        # High volatility during crashes (3-5x normal market vol)
        crash_volatility = abs(avg_return) * rng.uniform(2.5, 4.0)
        
        # Generate random returns with downward drift
        returns = []
        for i in range(actual_duration):
            # Progress through crash (0 to 1)
            progress = i / actual_duration
            
            # Drift becomes less negative over time (panic subsides)
            # Early: strong negative drift, Later: weaker drift
            drift_multiplier = 1.5 - progress * 0.8  # 1.5 -> 0.7
            current_drift = avg_return * drift_multiplier
            
            # Volatility also decreases slightly over time
            vol_multiplier = 1.3 - progress * 0.4  # 1.3 -> 0.9
            current_vol = crash_volatility * vol_multiplier
            
            # Generate random return (normal distribution with drift)
            ret = rng.normal(current_drift, current_vol)
            
            # Clamp extreme moves (no single step > 15% drop or > 5% gain)
            ret = max(ret, -0.15)
            ret = min(ret, 0.05)
            
            returns.append(ret)
        
        # Convert returns to price multipliers
        returns = np.array(returns)
        
        # Adjust returns to hit target magnitude approximately
        cumulative = np.cumsum(returns)
        final_cumulative = cumulative[-1]
        target_cumulative = -magnitude
        
        # Scale returns to hit target (but keep randomness)
        if abs(final_cumulative) > 0.01:
            # Blend: 70% scaled to target, 30% original randomness
            scale_factor = target_cumulative / final_cumulative
            returns = returns * (0.7 * scale_factor + 0.3)
        
        # Apply returns to prices during crash
        cumulative_mult = 1.0
        for i in range(actual_duration):
            cumulative_mult *= (1 + returns[i])
            # Don't let it go below the target
            cumulative_mult = max(cumulative_mult, 1.0 - magnitude * 1.1)
            prices[trigger_step + i] = prices[trigger_step + i] * cumulative_mult
        
        # Rebase all prices after crash
        final_multiplier = 1.0 - magnitude
        if crash_end < n:
            prices[crash_end:] = prices[crash_end:] * final_multiplier
        
        result[price_column] = prices
        return result
    
    def _apply_earnings_shock(
        self,
        df: pd.DataFrame,
        trigger_step: int,
        magnitude: float,
        price_column: str,
    ) -> pd.DataFrame:
        """
        Apply an earnings shock - instant jump/drop at trigger point.
        
        Creates a permanent gap in the price series starting at trigger_step.
        Positive magnitude = price jumps up, negative = price drops.
        
        Args:
            df: DataFrame with price data
            trigger_step: Row index where shock occurs
            magnitude: Size of gap as decimal (0.1 = +10%, -0.1 = -10%)
            price_column: Name of the price column
        
        Returns:
            Modified DataFrame with earnings shock applied
        """
        if trigger_step < 0 or trigger_step >= len(df):
            return df
        
        result = df.copy()
        
        # Multiply all prices from trigger_step onwards by (1 + magnitude)
        multiplier = 1.0 + magnitude
        
        # Ensure multiplier doesn't make prices negative or zero
        if multiplier <= 0:
            multiplier = 0.01  # Floor at 1% of original
        
        # Apply using iloc for position-based indexing
        col_idx = result.columns.get_loc(price_column)
        result.iloc[trigger_step:, col_idx] = result.iloc[trigger_step:, col_idx] * multiplier
        
        return result
    
    def apply_events_to_dict(
        self,
        data_store: Dict[str, pd.DataFrame],
        events: List["EventSpec"],
        price_column: str = "price",
    ) -> Dict[str, pd.DataFrame]:
        """
        Apply events to all DataFrames in a data store dictionary.
        
        This is useful when you have multiple assets in a single dataset.
        
        Args:
            data_store: Dictionary mapping symbol -> DataFrame
            events: List of events to apply
            price_column: Name of the price column in each DataFrame
        
        Returns:
            Modified data store with events applied to all assets
        """
        result = {}
        for symbol, df in data_store.items():
            result[symbol] = self.apply_events(df, events, price_column)
        return result


# Global singleton instance
event_manager = EventManager()
