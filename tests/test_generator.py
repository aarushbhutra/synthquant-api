"""
Unit tests for the SyntheticGenerator service.

Tests cover:
- Correct number of rows for different frequencies
- Seed reproducibility
- Volatility and drift multiplier effects
- Path statistics calculation
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from app.services.generator import SyntheticGenerator, synthetic_generator


class TestSyntheticGenerator:
    """Tests for the SyntheticGenerator class."""
    
    @pytest.fixture
    def base_params(self):
        """Sample base parameters mimicking market profiler output."""
        return {
            "symbol": "AAPL",
            "region": "US",
            "mu": 0.0005,  # Daily drift
            "sigma": 0.02,  # Daily volatility
            "last_price": 150.0,
            "data_points": 252,
            "fetched_at": "2024-01-15T10:00:00Z",
        }
    
    @pytest.fixture
    def default_config(self):
        """Default generation configuration."""
        return {
            "frequency": "1h",
            "horizon_days": 1,
            "volatility_multiplier": 1.0,
            "drift_multiplier": 1.0,
        }
    
    def test_generate_path_returns_dataframe(self, base_params, default_config):
        """Test that generate_path returns a pandas DataFrame with Close column."""
        import pandas as pd
        
        result = synthetic_generator.generate_path(base_params, default_config, seed=42)
        
        assert isinstance(result, pd.DataFrame)
        # Generator returns DataFrame with Timestamp index and Close column
        assert "Close" in result.columns
        assert result.index.name == "Timestamp"
    
    def test_correct_row_count_1h_1day(self, base_params, default_config):
        """Test row count for 1-hour frequency over 1 day (24 hours + 1 start)."""
        result = synthetic_generator.generate_path(base_params, default_config, seed=42)
        
        # 1 day at 1h frequency = 24 hours, so 25 rows (including start point)
        assert len(result) == 25
    
    def test_correct_row_count_1d_7days(self, base_params):
        """Test row count for 1-day frequency over 7 days."""
        config = {
            "frequency": "1d",
            "horizon_days": 7,
            "volatility_multiplier": 1.0,
            "drift_multiplier": 1.0,
        }
        result = synthetic_generator.generate_path(base_params, config, seed=42)
        
        # 7 days at 1d frequency = 8 rows (including start point)
        assert len(result) == 8
    
    def test_correct_row_count_5m_1day(self, base_params):
        """Test row count for 5-minute frequency over 1 day."""
        config = {
            "frequency": "5m",
            "horizon_days": 1,
            "volatility_multiplier": 1.0,
            "drift_multiplier": 1.0,
        }
        result = synthetic_generator.generate_path(base_params, config, seed=42)
        
        # 1 day at 5m frequency = 24*12 = 288 steps, so 289 rows (including start)
        assert len(result) == 289
    
    def test_seed_reproducibility(self, base_params, default_config):
        """Test that same seed produces identical results."""
        result1 = synthetic_generator.generate_path(base_params, default_config, seed=12345)
        result2 = synthetic_generator.generate_path(base_params, default_config, seed=12345)
        
        # DataFrames should be identical
        assert result1["Close"].tolist() == result2["Close"].tolist()
    
    def test_different_seeds_produce_different_results(self, base_params, default_config):
        """Test that different seeds produce different results."""
        result1 = synthetic_generator.generate_path(base_params, default_config, seed=111)
        result2 = synthetic_generator.generate_path(base_params, default_config, seed=222)
        
        # Close prices should differ
        assert result1["Close"].tolist() != result2["Close"].tolist()
    
    def test_volatility_multiplier_increases_std(self, base_params):
        """Test that higher volatility multiplier increases price variance."""
        config_low = {
            "frequency": "1h",
            "horizon_days": 5,
            "volatility_multiplier": 1.0,
            "drift_multiplier": 1.0,
        }
        config_high = {
            "frequency": "1h",
            "horizon_days": 5,
            "volatility_multiplier": 2.0,
            "drift_multiplier": 1.0,
        }
        
        # Use same seed for fair comparison
        result_low = synthetic_generator.generate_path(base_params, config_low, seed=42)
        result_high = synthetic_generator.generate_path(base_params, config_high, seed=42)
        
        # Calculate returns
        returns_low = result_low["Close"].pct_change().dropna()
        returns_high = result_high["Close"].pct_change().dropna()
        
        # Higher volatility multiplier should produce higher std of returns
        # With same seed, the randomness is identical, but scaled differently
        std_low = returns_low.std()
        std_high = returns_high.std()
        
        # The ratio should be approximately 2.0 (high/low volatility)
        assert std_high > std_low
        assert abs(std_high / std_low - 2.0) < 0.1  # Allow some tolerance
    
    def test_starting_price_matches_last_price(self, base_params, default_config):
        """Test that the first price matches the base last_price."""
        result = synthetic_generator.generate_path(base_params, default_config, seed=42)
        
        assert result["Close"].iloc[0] == base_params["last_price"]
    
    def test_prices_are_positive(self, base_params, default_config):
        """Test that all prices are positive (GBM property)."""
        result = synthetic_generator.generate_path(base_params, default_config, seed=42)
        
        assert all(result["Close"] > 0)
    
    def test_timestamps_are_sequential(self, base_params, default_config):
        """Test that timestamps are in ascending order."""
        result = synthetic_generator.generate_path(base_params, default_config, seed=42)
        
        # Index is DatetimeIndex
        timestamps = result.index.tolist()
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1]
    
    def test_calculate_path_statistics(self, base_params, default_config):
        """Test the path statistics calculation method."""
        result = synthetic_generator.generate_path(base_params, default_config, seed=42)
        
        stats = synthetic_generator.calculate_path_statistics(result)
        
        assert "start_price" in stats
        assert "end_price" in stats
        assert "min_price" in stats
        assert "max_price" in stats
        assert "total_return" in stats
        assert "volatility" in stats
        assert "sharpe_approx" in stats  # The actual key used
        
        # Basic sanity checks
        assert stats["min_price"] <= stats["start_price"] <= stats["max_price"]
        assert stats["min_price"] <= stats["end_price"] <= stats["max_price"]
    
    def test_no_seed_produces_random_results(self, base_params, default_config):
        """Test that no seed produces different results each time."""
        result1 = synthetic_generator.generate_path(base_params, default_config, seed=None)
        result2 = synthetic_generator.generate_path(base_params, default_config, seed=None)
        
        # Very unlikely to be identical
        assert result1["Close"].tolist() != result2["Close"].tolist()
    
    def test_frequency_scaling_1m(self, base_params):
        """Test that 1-minute frequency produces correct number of steps."""
        config = {
            "frequency": "1m",
            "horizon_days": 1,
            "volatility_multiplier": 1.0,
            "drift_multiplier": 1.0,
        }
        result = synthetic_generator.generate_path(base_params, config, seed=42)
        
        # 1 day at 1m = 24 * 60 = 1440 steps + 1 = 1441 rows
        assert len(result) == 1441


class TestRealisticEndpointIntegration:
    """Integration tests for the /datasets/create/realistic endpoint."""
    
    @pytest.fixture
    def mock_market_params(self):
        """Mock market profiler response."""
        return {
            "symbol": "AAPL",
            "region": "US",
            "mu": 0.0005,
            "sigma": 0.02,
            "last_price": 150.0,
            "data_points": 252,
            "fetched_at": "2024-01-15T10:00:00Z",
        }
    
    def test_create_realistic_dataset_endpoint(self, client, valid_api_key, mock_market_params):
        """Test the realistic dataset creation endpoint."""
        with patch("app.routers.v1.market_profiler.get_parameters") as mock_get:
            mock_get.return_value = mock_market_params
            
            response = client.post(
                "/v1/datasets/create/realistic",
                json={
                    "project": "test-realistic",
                    "assets": [
                        {
                            "symbol": "AAPL",
                            "region": "US",
                            "volatility_multiplier": 1.0,
                            "drift_multiplier": 1.0,
                        }
                    ],
                    "frequency": "1h",
                    "horizon_days": 1,
                    "seed": 42,
                },
                headers={"X-API-KEY": valid_api_key},
            )
            
            assert response.status_code == 201
            data = response.json()
            assert "dataset_id" in data
            assert data["status"] == "ready"
            assert "preview" in data
    
    def test_create_realistic_dataset_multiple_assets(self, client, valid_api_key, mock_market_params):
        """Test creating realistic dataset with multiple assets."""
        with patch("app.routers.v1.market_profiler.get_parameters") as mock_get:
            mock_get.return_value = mock_market_params
            
            response = client.post(
                "/v1/datasets/create/realistic",
                json={
                    "project": "multi-asset",
                    "assets": [
                        {"symbol": "AAPL", "region": "US"},
                        {"symbol": "GOOGL", "region": "US"},
                    ],
                    "frequency": "1h",
                    "horizon_days": 1,
                    "seed": 42,
                },
                headers={"X-API-KEY": valid_api_key},
            )
            
            assert response.status_code == 201
            data = response.json()
            assert "dataset_id" in data
            # Check preview has 2 assets
            assert len(data["preview"]["assets"]) == 2
    
    def test_create_realistic_dataset_invalid_frequency(self, client, valid_api_key):
        """Test that invalid frequency returns 400."""
        response = client.post(
            "/v1/datasets/create/realistic",
            json={
                "project": "test",
                "assets": [{"symbol": "AAPL", "region": "US"}],
                "frequency": "invalid",
                "horizon_days": 1,
            },
            headers={"X-API-KEY": valid_api_key},
        )
        
        assert response.status_code == 400
        assert "Invalid frequency" in response.json()["detail"]
    
    def test_create_realistic_dataset_asset_not_found(self, client, valid_api_key):
        """Test that unknown asset returns 404."""
        from app.exceptions import AssetNotFound
        
        with patch("app.routers.v1.market_profiler.get_parameters") as mock_get:
            mock_get.side_effect = AssetNotFound("INVALID", "US")
            
            response = client.post(
                "/v1/datasets/create/realistic",
                json={
                    "project": "test",
                    "assets": [{"symbol": "INVALID", "region": "US"}],
                    "frequency": "1h",
                    "horizon_days": 1,
                },
                headers={"X-API-KEY": valid_api_key},
            )
            
            assert response.status_code == 404
    
    def test_create_realistic_requires_auth(self, client):
        """Test that realistic endpoint requires authentication."""
        response = client.post(
            "/v1/datasets/create/realistic",
            json={
                "project": "test",
                "assets": [{"symbol": "AAPL", "region": "US"}],
                "frequency": "1h",
                "horizon_days": 1,
            },
        )
        
        assert response.status_code == 401
