"""
Unit tests for the Event Injection system.

Tests cover:
- IPO events (NaN before trigger point)
- Crash events (gradual price decline)
- Earnings shock events (instant price gap)
- Edge cases and error handling
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch

from app.services.event_manager import EventManager, event_manager
from app.models import EventSpec, EventTypeEnum


class TestEventManagerIPO:
    """Tests for IPO event injection."""
    
    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame with constant prices for testing."""
        return pd.DataFrame({
            "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(20)],
            "price": [100.0] * 20,
        })
    
    def test_ipo_sets_pre_trigger_to_nan(self, sample_df):
        """Test that IPO event sets all prices before trigger_step to NaN."""
        event = EventSpec(type=EventTypeEnum.IPO, trigger_step=10)
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # Rows 0-9 should be NaN
        assert all(pd.isna(result["price"].iloc[:10]))
        # Rows 10-19 should still be 100.0
        assert all(result["price"].iloc[10:] == 100.0)
    
    def test_ipo_at_index_0_no_change(self, sample_df):
        """Test that IPO at index 0 doesn't set anything to NaN."""
        event = EventSpec(type=EventTypeEnum.IPO, trigger_step=0)
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # No rows should be NaN (IPO at start means all data is post-IPO)
        assert all(result["price"].notna())
    
    def test_ipo_out_of_bounds_ignored(self, sample_df):
        """Test that IPO with trigger_step beyond DataFrame length is ignored."""
        event = EventSpec(type=EventTypeEnum.IPO, trigger_step=100)
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # DataFrame should be unchanged
        assert all(result["price"] == 100.0)
    
    def test_ipo_negative_trigger_ignored(self, sample_df):
        """Test that negative trigger_step is handled gracefully."""
        # Note: Pydantic validation should prevent this, but test defensive coding
        event = EventSpec(type=EventTypeEnum.IPO, trigger_step=0)  # ge=0 in model
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # Should not crash
        assert len(result) == 20


class TestEventManagerCrash:
    """Tests for market crash event injection."""
    
    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame with constant prices for testing."""
        return pd.DataFrame({
            "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(20)],
            "price": [100.0] * 20,
        })
    
    def test_crash_reduces_price_by_magnitude(self, sample_df):
        """Test that crash reduces final price by approximately the magnitude."""
        event = EventSpec(
            type=EventTypeEnum.CRASH,
            trigger_step=5,
            magnitude=0.3,
            duration=5,
        )
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # Prices before trigger should be unchanged
        assert all(result["price"].iloc[:5] == 100.0)
        
        # Price at crash end (step 10) should be ~70 (30% drop)
        # and all subsequent prices should be rebased
        final_price = result["price"].iloc[-1]
        assert final_price < 75.0  # Allow some tolerance
        assert final_price > 65.0
    
    def test_crash_applies_gradual_decline(self, sample_df):
        """Test that crash applies overall decline during duration (with realistic volatility)."""
        event = EventSpec(
            type=EventTypeEnum.CRASH,
            trigger_step=5,
            magnitude=0.5,
            duration=10,
        )
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # With realistic crashes, we expect net decline but allow for bounces
        # So we check that the END of crash is lower than the START
        crash_start_price = result["price"].iloc[5]
        crash_end_price = result["price"].iloc[14]
        
        # Overall trend should be down
        assert crash_end_price < crash_start_price, "Crash should result in net decline"
        # Should be significantly down (at least 30% of the 50% target)
        assert crash_end_price < crash_start_price * 0.7, "Crash should cause significant decline"
    
    def test_crash_sticks_after_duration(self, sample_df):
        """Test that the crash 'sticks' - prices stay low after crash ends."""
        event = EventSpec(
            type=EventTypeEnum.CRASH,
            trigger_step=5,
            magnitude=0.4,
            duration=5,
        )
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # All prices after crash should be significantly lower
        post_crash_prices = result["price"].iloc[10:].tolist()
        assert all(p < 65.0 for p in post_crash_prices)
    
    def test_crash_out_of_bounds_ignored(self, sample_df):
        """Test that crash with trigger beyond DataFrame is ignored."""
        event = EventSpec(
            type=EventTypeEnum.CRASH,
            trigger_step=100,
            magnitude=0.3,
            duration=10,
        )
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # DataFrame should be unchanged
        assert all(result["price"] == 100.0)


class TestEventManagerEarnings:
    """Tests for earnings shock event injection."""
    
    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame with constant prices for testing."""
        return pd.DataFrame({
            "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(20)],
            "price": [100.0] * 20,
        })
    
    def test_earnings_positive_shock_increases_price(self, sample_df):
        """Test that positive earnings shock increases price by magnitude."""
        event = EventSpec(
            type=EventTypeEnum.EARNINGS,
            trigger_step=10,
            magnitude=0.1,  # +10%
        )
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # Prices before trigger should be unchanged
        assert result["price"].iloc[:10].tolist() == pytest.approx([100.0] * 10)
        
        # Prices from trigger onwards should be 110.0 (+10%)
        assert result["price"].iloc[10:].tolist() == pytest.approx([110.0] * 10)
    
    def test_earnings_negative_shock_decreases_price(self, sample_df):
        """Test that negative earnings shock decreases price by magnitude."""
        event = EventSpec(
            type=EventTypeEnum.EARNINGS,
            trigger_step=10,
            magnitude=-0.1,  # -10%
        )
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # Prices before trigger should be unchanged
        assert all(result["price"].iloc[:10] == 100.0)
        
        # Prices from trigger onwards should be 90.0 (-10%)
        assert all(result["price"].iloc[10:] == 90.0)
    
    def test_earnings_creates_permanent_gap(self, sample_df):
        """Test that earnings shock creates a permanent gap in prices."""
        event = EventSpec(
            type=EventTypeEnum.EARNINGS,
            trigger_step=5,
            magnitude=0.15,  # +15%
        )
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # There should be a clear gap between pre and post shock
        pre_shock = result["price"].iloc[4]
        post_shock = result["price"].iloc[5]
        
        assert post_shock > pre_shock
        assert abs(post_shock / pre_shock - 1.15) < 0.01
    
    def test_earnings_out_of_bounds_ignored(self, sample_df):
        """Test that earnings shock beyond DataFrame is ignored."""
        event = EventSpec(
            type=EventTypeEnum.EARNINGS,
            trigger_step=100,
            magnitude=0.2,
        )
        
        result = event_manager.apply_events(sample_df, [event], price_column="price")
        
        # DataFrame should be unchanged
        assert all(result["price"] == 100.0)


class TestEventManagerMultipleEvents:
    """Tests for applying multiple events."""
    
    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame with constant prices for testing."""
        return pd.DataFrame({
            "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(30)],
            "price": [100.0] * 30,
        })
    
    def test_multiple_events_applied_in_order(self, sample_df):
        """Test that multiple events are applied in sequence."""
        events = [
            EventSpec(type=EventTypeEnum.EARNINGS, trigger_step=10, magnitude=0.2),
            EventSpec(type=EventTypeEnum.CRASH, trigger_step=20, magnitude=0.3, duration=5),
        ]
        
        result = event_manager.apply_events(sample_df, events, price_column="price")
        
        # Check earnings effect (rows 10-19 should be 120)
        # Note: rows 20+ will be affected by both events
        assert result["price"].iloc[9] == 100.0
        assert result["price"].iloc[10] == 120.0
        
        # Final price should reflect both events
        final_price = result["price"].iloc[-1]
        assert final_price < 100.0  # Combined effect of +20% and -30%
    
    def test_ipo_with_earnings(self, sample_df):
        """Test IPO combined with earnings shock."""
        events = [
            EventSpec(type=EventTypeEnum.IPO, trigger_step=10),
            EventSpec(type=EventTypeEnum.EARNINGS, trigger_step=15, magnitude=0.1),
        ]
        
        result = event_manager.apply_events(sample_df, events, price_column="price")
        
        # Pre-IPO should be NaN
        assert all(pd.isna(result["price"].iloc[:10]))
        
        # Post-IPO, pre-earnings should be 100
        assert result["price"].iloc[10:15].tolist() == pytest.approx([100.0] * 5)
        
        # Post-earnings should be 110
        assert result["price"].iloc[15:].tolist() == pytest.approx([110.0] * 15)


class TestEventManagerEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_events_list(self):
        """Test that empty events list returns unchanged DataFrame."""
        df = pd.DataFrame({"price": [100.0] * 10})
        
        result = event_manager.apply_events(df, [], price_column="price")
        
        assert all(result["price"] == 100.0)
    
    def test_missing_price_column_handled(self):
        """Test that missing price column is handled gracefully."""
        df = pd.DataFrame({"other_column": [100.0] * 10})
        events = [EventSpec(type=EventTypeEnum.EARNINGS, trigger_step=5, magnitude=0.1)]
        
        # Should not crash, return unchanged
        result = event_manager.apply_events(df, events, price_column="price")
        assert "other_column" in result.columns
    
    def test_alternative_price_column_name(self):
        """Test with 'Close' column name (common in stock data)."""
        df = pd.DataFrame({"Close": [100.0] * 10})
        events = [EventSpec(type=EventTypeEnum.EARNINGS, trigger_step=5, magnitude=0.1)]
        
        result = event_manager.apply_events(df, events, price_column="Close")
        
        assert result["Close"].iloc[5] == pytest.approx(110.0)
    
    def test_apply_events_to_dict(self):
        """Test applying events to a dictionary of DataFrames."""
        data_store = {
            "AAPL": pd.DataFrame({"price": [100.0] * 10}),
            "GOOGL": pd.DataFrame({"price": [200.0] * 10}),
        }
        events = [EventSpec(type=EventTypeEnum.EARNINGS, trigger_step=5, magnitude=0.1)]
        
        result = event_manager.apply_events_to_dict(data_store, events, price_column="price")
        
        # Both should have the shock applied
        assert result["AAPL"]["price"].iloc[5] == pytest.approx(110.0)
        assert result["GOOGL"]["price"].iloc[5] == pytest.approx(220.0)


class TestEventIntegrationWithAPI:
    """Integration tests for events with the API endpoints."""
    
    def test_create_dataset_with_ipo_event(self, client, valid_api_key):
        """Test creating a dataset with an IPO event via API."""
        response = client.post(
            "/v1/datasets/create",
            json={
                "project": "test-ipo",
                "assets": [{"symbol": "NEWSTOCK", "start_price": 50.0}],
                "frequency": "1h",
                "horizon_days": 1,
                "seed": 42,
                "events": [
                    {"type": "ipo", "trigger_step": 10}
                ],
            },
            headers={"X-API-KEY": valid_api_key},
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Preview should show None values for pre-IPO rows
        preview = data["preview"]["assets"][0]
        # First 10 rows in preview should have None prices
        assert preview["prices"][0] is None
        assert preview["prices"][9] is None
    
    def test_create_dataset_with_earnings_event(self, client, valid_api_key):
        """Test creating a dataset with an earnings shock event."""
        response = client.post(
            "/v1/datasets/create",
            json={
                "project": "test-earnings",
                "assets": [{"symbol": "STOCK", "start_price": 100.0}],
                "frequency": "1h",
                "horizon_days": 1,
                "seed": 42,
                "events": [
                    {"type": "earnings", "trigger_step": 5, "magnitude": 0.2}
                ],
            },
            headers={"X-API-KEY": valid_api_key},
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Preview prices should show a jump at step 5
        preview = data["preview"]["assets"][0]
        # Price at index 5 should be higher than at index 4
        assert preview["prices"][5] > preview["prices"][4] * 1.1
    
    def test_create_dataset_with_crash_event(self, client, valid_api_key):
        """Test creating a dataset with a crash event."""
        response = client.post(
            "/v1/datasets/create",
            json={
                "project": "test-crash",
                "assets": [{"symbol": "CRASHING", "start_price": 100.0}],
                "frequency": "1h",
                "horizon_days": 1,
                "seed": 42,
                "events": [
                    {"type": "crash", "trigger_step": 5, "magnitude": 0.4, "duration": 5}
                ],
            },
            headers={"X-API-KEY": valid_api_key},
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Preview prices should show a decline
        preview = data["preview"]["assets"][0]
        # The last price in preview should be lower than the start
        assert preview["prices"][9] < preview["prices"][0]
    
    def test_create_dataset_with_multiple_events(self, client, valid_api_key):
        """Test creating a dataset with multiple events."""
        response = client.post(
            "/v1/datasets/create",
            json={
                "project": "test-multi-event",
                "assets": [{"symbol": "VOLATILE", "start_price": 100.0}],
                "frequency": "1h",
                "horizon_days": 2,
                "seed": 42,
                "events": [
                    {"type": "earnings", "trigger_step": 10, "magnitude": 0.15},
                    {"type": "crash", "trigger_step": 30, "magnitude": 0.25, "duration": 10},
                ],
            },
            headers={"X-API-KEY": valid_api_key},
        )
        
        assert response.status_code == 201
    
    def test_invalid_event_type_rejected(self, client, valid_api_key):
        """Test that invalid event type is rejected by validation."""
        response = client.post(
            "/v1/datasets/create",
            json={
                "project": "test-invalid",
                "assets": [{"symbol": "TEST", "start_price": 100.0}],
                "frequency": "1h",
                "horizon_days": 1,
                "seed": 42,
                "events": [
                    {"type": "invalid_event", "trigger_step": 5}
                ],
            },
            headers={"X-API-KEY": valid_api_key},
        )
        
        assert response.status_code == 422  # Validation error
