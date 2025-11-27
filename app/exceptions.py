"""
Custom exceptions for SynthQuant API.
"""


class SynthQuantError(Exception):
    """Base exception for SynthQuant API."""
    pass


class AssetNotFound(SynthQuantError):
    """Raised when an asset/ticker cannot be found or data is unavailable."""
    
    def __init__(self, symbol: str, region: str = "US", message: str = None):
        self.symbol = symbol
        self.region = region
        self.message = message or f"Asset '{symbol}' not found in region '{region}'"
        super().__init__(self.message)


class InsufficientDataError(SynthQuantError):
    """Raised when there is not enough historical data for analysis."""
    
    def __init__(self, symbol: str, required: int, available: int):
        self.symbol = symbol
        self.required = required
        self.available = available
        self.message = f"Insufficient data for '{symbol}': required {required} points, got {available}"
        super().__init__(self.message)
