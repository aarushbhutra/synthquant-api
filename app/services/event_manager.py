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
    ) -> pd.DataFrame:
        """
        Apply a market crash event - gradual price decline over duration.
        
        The crash applies a linear decay from the trigger point, reaching
        the full magnitude drop by (trigger_step + duration_steps).
        The drop "sticks" - all prices after the crash period are rebased.
        
        Args:
            df: DataFrame with price data
            trigger_step: Row index where crash begins
            magnitude: Total drop as decimal (0.3 = 30% drop)
            duration_steps: Number of steps over which the crash occurs
            price_column: Name of the price column
        
        Returns:
            Modified DataFrame with crash applied
        """
        if trigger_step < 0 or trigger_step >= len(df):
            return df
        
        if magnitude <= 0 or magnitude >= 1:
            # Invalid magnitude (must be between 0 and 1 exclusive)
            magnitude = min(0.99, max(0.01, magnitude))
        
        if duration_steps < 1:
            duration_steps = 1
        
        result = df.copy()
        prices = result[price_column].values.copy()
        n = len(prices)
        
        # Calculate the crash end point
        crash_end = min(trigger_step + duration_steps, n)
        
        # Apply linear decay during crash period
        # multiplier goes from 1.0 at trigger_step to (1-magnitude) at crash_end
        for i in range(trigger_step, crash_end):
            progress = (i - trigger_step + 1) / duration_steps
            multiplier = 1.0 - (magnitude * progress)
            prices[i] = prices[i] * multiplier
        
        # Rebase all prices after crash - apply full magnitude
        final_multiplier = 1.0 - magnitude
        if crash_end < n:
            # Calculate the ratio at crash_end to maintain continuity
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
