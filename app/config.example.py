"""
Configuration settings for SynthQuant API.
Contains API keys, constants, and application settings.
"""

from typing import Set

# Application Settings
APP_NAME = "SynthQuant API"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Synthetic Market Data Generation Service"

# API Key Configuration
# In production, these would come from environment variables or a secure vault
VALID_API_KEYS: Set[str] = {
    "sk-synthquant-dev-001",
    "sk-synthquant-dev-002",
    "sk-synthquant-test-001",
}

# Admin Configuration (for internal endpoints)
ADMIN_SECRET = ""

# Rate Limiting Configuration
RATE_LIMIT_REQUESTS = 10  # Maximum requests per window
RATE_LIMIT_WINDOW_SECONDS = 60  # Time window in seconds (1 minute)

# Data Generation Configuration
DEFAULT_FREQUENCY = "1h"
SUPPORTED_FREQUENCIES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}

# GBM (Geometric Brownian Motion) Default Parameters
DEFAULT_VOLATILITY = 0.02  # 2% daily volatility
DEFAULT_DRIFT = 0.0001  # Small positive drift

# API Base URL (for generating download URLs)
API_BASE_URL = "http://localhost:8000"

ALPHA_VANTAGE_API_KEY = ""