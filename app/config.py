"""
Configuration settings for SynthQuant API.
Loads sensitive values from environment variables for security.
"""

import os
from typing import Set

# Application Settings
APP_NAME = "SynthQuant API"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Synthetic Market Data Generation Service"

# API Key Configuration
# Load from environment variable or use defaults for development
_initial_api_key = os.environ.get("INITIAL_API_KEY", "")
_default_keys = {"sk-synthquant-dev-001", "sk-synthquant-dev-002", "sk-synthquant-test-001"}

VALID_API_KEYS: Set[str] = _default_keys.copy()
if _initial_api_key:
    VALID_API_KEYS.add(_initial_api_key)

# Admin Configuration (for internal endpoints)
# MUST be set via environment variable in production
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "dev_admin_secret_change_in_production")

# Rate Limiting Configuration
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Data Generation Configuration
DEFAULT_FREQUENCY = "1h"
SUPPORTED_FREQUENCIES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}

# GBM (Geometric Brownian Motion) Default Parameters
DEFAULT_VOLATILITY = 0.02  # 2% daily volatility
DEFAULT_DRIFT = 0.0001  # Small positive drift

# API Base URL (for generating download URLs)
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

# External API Keys
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")