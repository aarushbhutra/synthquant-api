"""
Test suite for SynthQuant API.
Covers public endpoints, admin endpoints, rate limiting, and market profiler.
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from fastapi import status


class TestPublicEndpoints:
    """Tests for public API endpoints."""

    def test_status_endpoint_returns_ok(self, client):
        """GET /v1/status should return 200 OK with service status."""
        response = client.get("/v1/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["service"] == "ok"
        assert "timestamp" in data
        assert data["note"] == "Simulation Mode"

    def test_root_endpoint(self, client):
        """GET / should return API information."""
        response = client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "name" in data
        assert "version" in data

    def test_health_endpoint(self, client):
        """GET /health should return healthy status."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "healthy"


class TestApiKeyVerification:
    """Tests for API key verification endpoint."""

    def test_verify_valid_api_key(self, client, valid_api_key):
        """POST /v1/apikeys/verify with valid key should return valid=True."""
        response = client.post(
            "/v1/apikeys/verify",
            json={"api_key": valid_api_key}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert data["limit"] == 10
        assert "quota_remaining" in data

    def test_verify_invalid_api_key(self, client, invalid_api_key):
        """POST /v1/apikeys/verify with invalid key should return valid=False."""
        response = client.post(
            "/v1/apikeys/verify",
            json={"api_key": invalid_api_key}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert data["quota_remaining"] == 0


class TestProtectedEndpoints:
    """Tests for endpoints requiring API key authentication."""

    def test_list_datasets_without_key(self, client):
        """GET /v1/datasets without API key should return 401."""
        response = client.get("/v1/datasets")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_datasets_with_invalid_key(self, client, invalid_api_key):
        """GET /v1/datasets with invalid key should return 401."""
        response = client.get(
            "/v1/datasets",
            headers={"X-API-KEY": invalid_api_key}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_datasets_with_valid_key(self, client, valid_api_key):
        """GET /v1/datasets with valid key should return 200."""
        response = client.get(
            "/v1/datasets",
            headers={"X-API-KEY": valid_api_key}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "datasets" in data
        assert "total_count" in data

    def test_get_nonexistent_dataset(self, client, valid_api_key):
        """GET /v1/datasets/{id} for non-existent ID should return 404."""
        response = client.get(
            "/v1/datasets/ds-nonexistent",
            headers={"X-API-KEY": valid_api_key}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAdminEndpoints:
    """Tests for hidden admin endpoints."""

    def test_create_api_key_without_secret(self, client):
        """POST /internal/apikeys/create without secret should return 401."""
        response = client.post("/internal/apikeys/create")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_api_key_with_wrong_secret(self, client, wrong_admin_secret):
        """POST /internal/apikeys/create with wrong secret should return 401."""
        response = client.post(
            "/internal/apikeys/create",
            headers={"X-ADMIN-SECRET": wrong_admin_secret}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_api_key_with_correct_secret(self, client, admin_secret):
        """POST /internal/apikeys/create with correct secret should return 201."""
        response = client.post(
            "/internal/apikeys/create",
            headers={"X-ADMIN-SECRET": admin_secret}
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "new_key" in data
        assert data["new_key"].startswith("sk-synthquant-")
        assert "created_at" in data
        assert "note" in data

    def test_created_key_is_immediately_usable(self, client, admin_secret):
        """
        Integration test: A key created via admin endpoint should be
        immediately usable for API authentication.
        """
        # Step 1: Create a new key via admin endpoint
        create_response = client.post(
            "/internal/apikeys/create",
            headers={"X-ADMIN-SECRET": admin_secret}
        )
        
        assert create_response.status_code == status.HTTP_201_CREATED
        new_key = create_response.json()["new_key"]
        
        # Step 2: Verify the new key is valid
        verify_response = client.post(
            "/v1/apikeys/verify",
            json={"api_key": new_key}
        )
        
        assert verify_response.status_code == status.HTTP_200_OK
        verify_data = verify_response.json()
        assert verify_data["valid"] is True
        assert verify_data["quota_remaining"] == 10
        
        # Step 3: Use the new key to access a protected endpoint
        datasets_response = client.get(
            "/v1/datasets",
            headers={"X-API-KEY": new_key}
        )
        
        assert datasets_response.status_code == status.HTTP_200_OK


class TestDatasetCreation:
    """Tests for dataset creation endpoint."""

    def test_create_dataset_success(self, client, valid_api_key):
        """POST /v1/datasets/create should create a dataset successfully."""
        payload = {
            "project": "test-project",
            "assets": [
                {"symbol": "BTC", "start_price": 50000.0},
                {"symbol": "ETH", "start_price": 3000.0}
            ],
            "frequency": "1h",
            "horizon_days": 7,
            "seed": 42
        }
        
        response = client.post(
            "/v1/datasets/create",
            headers={"X-API-KEY": valid_api_key},
            json=payload
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "dataset_id" in data
        assert data["status"] == "ready"
        assert "realism_score" in data
        assert "preview" in data

    def test_create_dataset_deterministic(self, client, valid_api_key):
        """Same seed should produce same results."""
        payload = {
            "project": "determinism-test",
            "assets": [{"symbol": "BTC", "start_price": 50000.0}],
            "frequency": "1h",
            "horizon_days": 1,
            "seed": 12345
        }
        
        # Create first dataset
        response1 = client.post(
            "/v1/datasets/create",
            headers={"X-API-KEY": valid_api_key},
            json=payload
        )
        preview1 = response1.json()["preview"]["assets"][0]["prices"]
        
        # Create second dataset with same seed
        response2 = client.post(
            "/v1/datasets/create",
            headers={"X-API-KEY": valid_api_key},
            json=payload
        )
        preview2 = response2.json()["preview"]["assets"][0]["prices"]
        
        # Prices should be identical
        assert preview1 == preview2

    def test_create_dataset_invalid_frequency(self, client, valid_api_key):
        """Invalid frequency should return 400."""
        payload = {
            "project": "test",
            "assets": [{"symbol": "BTC", "start_price": 50000.0}],
            "frequency": "invalid",
            "horizon_days": 1,
            "seed": 42
        }
        
        response = client.post(
            "/v1/datasets/create",
            headers={"X-API-KEY": valid_api_key},
            json=payload
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limit_enforcement(self, client, valid_api_key):
        """
        Rate limit stress test.
        - 10 requests should succeed (200 OK)
        - 11th request should fail (429 Too Many Requests)
        """
        # Fire 10 requests - all should succeed
        for i in range(10):
            response = client.get(
                "/v1/datasets",
                headers={"X-API-KEY": valid_api_key}
            )
            assert response.status_code == status.HTTP_200_OK, \
                f"Request {i+1} failed unexpectedly with status {response.status_code}"
        
        # 11th request should be rate limited
        response = client.get(
            "/v1/datasets",
            headers={"X-API-KEY": valid_api_key}
        )
        
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Retry-After" in response.headers

    def test_rate_limit_per_api_key(self, client, admin_secret):
        """
        Rate limits should be per API key.
        Creating a new key should have its own quota.
        """
        # Create a new API key
        create_response = client.post(
            "/internal/apikeys/create",
            headers={"X-ADMIN-SECRET": admin_secret}
        )
        new_key = create_response.json()["new_key"]
        
        # Exhaust the new key's quota
        for _ in range(10):
            client.get(
                "/v1/datasets",
                headers={"X-API-KEY": new_key}
            )
        
        # 11th request with new key should fail
        response = client.get(
            "/v1/datasets",
            headers={"X-API-KEY": new_key}
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        
        # Create another key - should have fresh quota
        create_response2 = client.post(
            "/internal/apikeys/create",
            headers={"X-ADMIN-SECRET": admin_secret}
        )
        another_key = create_response2.json()["new_key"]
        
        # This key should work fine
        response = client.get(
            "/v1/datasets",
            headers={"X-API-KEY": another_key}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_verify_endpoint_shows_quota(self, client, valid_api_key):
        """Verify endpoint should show remaining quota."""
        # Make some requests to consume quota
        for _ in range(3):
            client.get(
                "/v1/datasets",
                headers={"X-API-KEY": valid_api_key}
            )
        
        # Check remaining quota
        response = client.post(
            "/v1/apikeys/verify",
            json={"api_key": valid_api_key}
        )
        
        data = response.json()
        assert data["valid"] is True
        assert data["quota_remaining"] == 7  # 10 - 3 = 7
        assert data["limit"] == 10


class TestMarketProfiler:
    """Tests for market profiler debug endpoint."""

    @pytest.fixture
    def mock_price_series(self):
        """Generate a mock price series for testing."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        # Generate realistic-looking prices using random walk
        returns = np.random.normal(0.0005, 0.02, 252)
        prices = 100 * np.exp(np.cumsum(returns))
        return pd.Series(prices, index=dates, name="Close")

    def test_profile_endpoint_without_auth(self, client):
        """POST /v1/debug/profile without API key should return 401."""
        response = client.post(
            "/v1/debug/profile",
            json={"symbol": "AAPL", "region": "US"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_profile_endpoint_with_invalid_region(self, client, valid_api_key):
        """POST /v1/debug/profile with invalid region should return 422."""
        response = client.post(
            "/v1/debug/profile",
            headers={"X-API-KEY": valid_api_key},
            json={"symbol": "AAPL", "region": "INVALID"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_profile_endpoint_success_mocked(self, client, valid_api_key, mock_price_series):
        """POST /v1/debug/profile should return market parameters (mocked)."""
        with patch("app.services.market_profiler.MarketProfiler.fetch_history") as mock_fetch:
            mock_fetch.return_value = mock_price_series
            
            response = client.post(
                "/v1/debug/profile",
                headers={"X-API-KEY": valid_api_key},
                json={"symbol": "AAPL", "region": "US"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Verify response structure
            assert "symbol" in data
            assert "region" in data
            assert "mu" in data
            assert "sigma" in data
            assert "last_price" in data
            assert "data_points" in data
            assert "fetched_at" in data
            assert "annualized_return" in data
            assert "annualized_volatility" in data
            
            # Verify data types
            assert isinstance(data["mu"], float)
            assert isinstance(data["sigma"], float)
            assert isinstance(data["last_price"], float)
            assert data["data_points"] == 252
            
            # Sigma should be positive
            assert data["sigma"] > 0

    def test_profile_endpoint_indian_stock_mocked(self, client, valid_api_key, mock_price_series):
        """POST /v1/debug/profile should handle Indian stocks (mocked)."""
        with patch("app.services.market_profiler.MarketProfiler.fetch_history") as mock_fetch:
            mock_fetch.return_value = mock_price_series
            
            response = client.post(
                "/v1/debug/profile",
                headers={"X-API-KEY": valid_api_key},
                json={"symbol": "RELIANCE", "region": "IN"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["symbol"] == "RELIANCE"
            assert data["region"] == "IN"

    def test_profile_endpoint_asset_not_found(self, client, valid_api_key):
        """POST /v1/debug/profile should return 404 for invalid ticker."""
        with patch("app.services.market_profiler.MarketProfiler.fetch_history") as mock_fetch:
            from app.exceptions import AssetNotFound
            mock_fetch.side_effect = AssetNotFound(
                symbol="INVALIDTICKER",
                region="US",
                message="Asset 'INVALIDTICKER' not found in region 'US'"
            )
            
            response = client.post(
                "/v1/debug/profile",
                headers={"X-API-KEY": valid_api_key},
                json={"symbol": "INVALIDTICKER", "region": "US"}
            )
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()

    def test_profile_caching(self, client, valid_api_key, mock_price_series):
        """Market profiler should cache results."""
        with patch("app.services.market_profiler.MarketProfiler.fetch_history") as mock_fetch:
            mock_fetch.return_value = mock_price_series
            
            # First request
            response1 = client.post(
                "/v1/debug/profile",
                headers={"X-API-KEY": valid_api_key},
                json={"symbol": "CACHE_TEST", "region": "US"}
            )
            
            # Second request (should use cache)
            response2 = client.post(
                "/v1/debug/profile",
                headers={"X-API-KEY": valid_api_key},
                json={"symbol": "CACHE_TEST", "region": "US"}
            )
            
            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_200_OK
            
            # fetch_history should only be called once due to caching
            assert mock_fetch.call_count == 1
