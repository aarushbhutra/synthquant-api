"""
SynthQuant API Example: Fetching Realistic Data with Market Crash

This script demonstrates how to:
1. Connect to the SynthQuant API
2. Generate synthetic market data calibrated to real AAPL parameters
3. Inject a market crash event
4. Visualize the results with matplotlib

Requirements:
    pip install requests matplotlib pandas

Usage:
    1. Start the SynthQuant API server: uvicorn app.main:app --reload
    2. Run this script: python examples/fetch_crash_data.py
"""

import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

API_BASE_URL = "http://localhost:8000"
API_KEY = "sk-synthquant-dev-001"

# =============================================================================
# API CLIENT FUNCTIONS
# =============================================================================

def check_api_status() -> bool:
    """Check if the API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/v1/status")
        return response.status_code == 200
    except requests.ConnectionError:
        return False


def create_crash_dataset(
    symbol: str = "AAPL",
    region: str = "US",
    horizon_days: int = 30,
    frequency: str = "1h",
    crash_step: int = 300,
    crash_magnitude: float = 0.35,
    crash_duration: int = 20,
    volatility_multiplier: float = 1.0,
    drift_multiplier: float = 1.0,
    seed: int = None,
) -> dict:
    """
    Create a synthetic dataset with a market crash event.
    
    Args:
        symbol: Stock symbol to calibrate against (uses real market params)
        region: Market region ("US" or "IN" for India)
        horizon_days: Number of days to generate
        frequency: Data frequency ("1m", "5m", "15m", "30m", "1h", "4h", "1d")
        crash_step: Time step where crash begins
        crash_magnitude: Size of crash (0.35 = 35% drop)
        crash_duration: Number of steps over which crash unfolds
        volatility_multiplier: Scale volatility (2.0 = 2x more volatile)
        drift_multiplier: Scale drift/trend (0.5 = half the trend)
        seed: Random seed (None = random each time for different shapes)
    
    Returns:
        API response with dataset details and preview
    """
    import time
    
    # Use timestamp-based seed if not provided (different each run)
    if seed is None:
        seed = int(time.time() * 1000) % (2**31 - 1)
    
    payload = {
        "project": f"crash-demo-{seed}",
        "assets": [
            {
                "symbol": symbol,
                "region": region,
                "volatility_multiplier": volatility_multiplier,
                "drift_multiplier": drift_multiplier,
            }
        ],
        "frequency": frequency,
        "horizon_days": horizon_days,
        "seed": seed,  # Different seed = different base price path
        "events": [
            {
                "type": "crash",
                "trigger_step": crash_step,
                "magnitude": crash_magnitude,
                "duration": crash_duration,
            }
        ],
    }
    
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }
    
    response = requests.post(
        f"{API_BASE_URL}/v1/datasets/create/realistic",
        json=payload,
        headers=headers,
    )
    
    if response.status_code != 201:
        raise Exception(f"API Error: {response.status_code} - {response.text}")
    
    return response.json()


def download_full_dataset(dataset_id: str) -> dict:
    """
    Download the complete dataset with all price data.
    
    Args:
        dataset_id: The ID returned from create_crash_dataset
    
    Returns:
        Full dataset with all timestamps and prices
    """
    headers = {"X-API-KEY": API_KEY}
    response = requests.get(
        f"{API_BASE_URL}/v1/datasets/{dataset_id}/download",
        headers=headers,
    )
    
    if response.status_code != 200:
        raise Exception(f"Download Error: {response.status_code} - {response.text}")
    
    return response.json()


# =============================================================================
# VISUALIZATION
# =============================================================================

def plot_crash_data(data: dict, crash_step: int = 300):
    """
    Create a visualization of the price data with crash highlighted.
    
    Args:
        data: Full dataset response from download endpoint
        crash_step: Step where crash begins (for annotation)
    """
    # Extract full data (from download endpoint)
    assets = data.get("assets", [])
    
    if not assets:
        print("No asset data found in response!")
        return
    
    asset = assets[0]
    symbol = asset["symbol"]
    timestamps = asset["timestamps"]
    prices = asset["prices"]
    
    # Convert to pandas for easier manipulation
    # Fix malformed timestamps (e.g., "2025-11-28T05:15:00+00:00Z" -> remove trailing Z)
    cleaned_timestamps = [ts.replace("+00:00Z", "+00:00").replace("Z", "") for ts in timestamps]
    
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(cleaned_timestamps, utc=True),
        "price": prices,
    })
    
    # Filter out any NaN values (pre-IPO if applicable)
    df = df.dropna(subset=["price"])
    df = df.reset_index(drop=True)
    
    data_len = len(df)
    print(f"   Plotting {data_len} data points")
    
    # Adjust crash_step if it exceeds data length
    if crash_step >= data_len:
        crash_step = max(data_len // 3, 1)  # Put crash at 1/3 of the data
        print(f"   Adjusted crash_step to {crash_step} (data has {data_len} points)")
    
    # Create the figure with a dark style
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[3, 1])
    
    # ===================
    # Main Price Chart
    # ===================
    
    # Plot the price line
    ax1.plot(
        df["timestamp"], 
        df["price"], 
        color="#2E86AB",
        linewidth=1.5,
        label=f"{symbol} Price",
    )
    
    # Highlight the crash zone
    if crash_step < len(df):
        crash_start_time = df["timestamp"].iloc[crash_step]
        crash_end_time = df["timestamp"].iloc[min(crash_step + 50, len(df) - 1)]
        
        ax1.axvspan(
            crash_start_time, 
            crash_end_time, 
            alpha=0.3, 
            color='red',
            label='Crash Zone',
        )
        
        # Add crash annotation
        crash_price = df["price"].iloc[crash_step]
        ax1.annotate(
            '📉 CRASH EVENT',
            xy=(crash_start_time, crash_price),
            xytext=(crash_start_time, crash_price * 1.1),
            fontsize=12,
            fontweight='bold',
            color='red',
            ha='center',
            arrowprops=dict(arrowstyle='->', color='red', lw=2),
        )
    
    # Calculate statistics (handle small datasets)
    if crash_step > 0 and crash_step < len(df):
        pre_crash_price = df["price"].iloc[crash_step - 1]
    else:
        pre_crash_price = df["price"].iloc[0]
    post_crash_price = df["price"].iloc[-1]
    total_drop = (post_crash_price - pre_crash_price) / pre_crash_price * 100
    
    # Add statistics text box
    stats_text = (
        f"Pre-Crash: ${pre_crash_price:.2f}\n"
        f"Post-Crash: ${post_crash_price:.2f}\n"
        f"Total Change: {total_drop:.1f}%"
    )
    ax1.text(
        0.02, 0.98, stats_text,
        transform=ax1.transAxes,
        fontsize=11,
        verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
    )
    
    ax1.set_title(
        f"SynthQuant: Synthetic {symbol} with 35% Market Crash Simulation",
        fontsize=16,
        fontweight='bold',
        pad=20,
    )
    ax1.set_ylabel("Price ($)", fontsize=12)
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    
    # ===================
    # Returns Chart
    # ===================
    
    # Calculate returns
    df["returns"] = df["price"].pct_change() * 100
    
    # Color bars based on positive/negative
    colors = ['green' if r >= 0 else 'red' for r in df["returns"].fillna(0)]
    
    ax2.bar(
        df["timestamp"],
        df["returns"].fillna(0),
        color=colors,
        alpha=0.7,
        width=0.02,
    )
    
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_xlabel("Date", fontsize=12)
    ax2.set_ylabel("Hourly Returns (%)", fontsize=12)
    ax2.set_title("Price Returns Distribution", fontsize=12)
    ax2.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    
    plt.tight_layout()
    
    # Save the figure
    output_path = "examples/crash_simulation.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Chart saved to: {output_path}")
    
    # Show the plot
    plt.show()


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("SynthQuant Market Crash Simulation Demo")
    print("=" * 60)
    
    # Check API status
    print("\n🔍 Checking API status...")
    if not check_api_status():
        print("❌ API is not running!")
        print("   Start it with: uvicorn app.main:app --reload")
        return
    print("✅ API is running")
    
    # ===========================================
    # CONFIGURATION - Customize these settings!
    # ===========================================
    SYMBOL = "AAPL"           # Stock to simulate (AAPL, GOOGL, MSFT, etc.)
    REGION = "US"             # "US" or "IN" (India/NSE)
    HORIZON_DAYS = 30         # Total days of data
    FREQUENCY = "1h"          # "1m", "5m", "15m", "30m", "1h", "4h", "1d"
    
    # Crash settings
    CRASH_STEP = 200          # When crash starts (in time steps)
    CRASH_MAGNITUDE = 0.40    # Total drop (0.40 = 40%)
    CRASH_DURATION = 96       # Duration in steps (96h = 4 days)
    
    # Volatility/trend adjustments
    VOLATILITY_MULT = 1.2     # 1.2 = 20% more volatile than real market
    DRIFT_MULT = 0.8          # 0.8 = 80% of real market trend
    
    # Set to None for random each run, or a number for reproducibility
    RANDOM_SEED = None
    # ===========================================
    
    total_steps = HORIZON_DAYS * (24 if FREQUENCY == "1h" else 1)
    
    print(f"\n📈 Generating synthetic {SYMBOL} data...")
    print(f"   Symbol: {SYMBOL} ({REGION})")
    print(f"   Duration: {HORIZON_DAYS} days @ {FREQUENCY} frequency")
    print(f"   Volatility: {VOLATILITY_MULT}x | Drift: {DRIFT_MULT}x")
    print(f"   Crash: {int(CRASH_MAGNITUDE*100)}% drop starting at step {CRASH_STEP}")
    print(f"   Crash duration: {CRASH_DURATION} steps (~{CRASH_DURATION // 24} days)")
    print(f"   Seed: {'Random (different each run)' if RANDOM_SEED is None else RANDOM_SEED}")
    
    try:
        # Step 1: Create the dataset
        create_response = create_crash_dataset(
            symbol=SYMBOL,
            region=REGION,
            horizon_days=HORIZON_DAYS,
            frequency=FREQUENCY,
            crash_step=CRASH_STEP,
            crash_magnitude=CRASH_MAGNITUDE,
            crash_duration=CRASH_DURATION,
            volatility_multiplier=VOLATILITY_MULT,
            drift_multiplier=DRIFT_MULT,
            seed=RANDOM_SEED,
        )
        
        dataset_id = create_response.get("dataset_id")
        print(f"\n✅ Dataset created: {dataset_id}")
        print(f"   Realism Score: {create_response.get('realism_score', 'N/A')}")
        
        # Step 2: Download the FULL dataset (not just preview)
        print("\n📥 Downloading full dataset...")
        full_data = download_full_dataset(dataset_id)
        
        assets = full_data.get("assets", [])
        if assets:
            total_points = len(assets[0].get("prices", []))
            print(f"   Downloaded {total_points} data points")
        
        # Step 3: Plot the full data
        print("\n🎨 Generating visualization (each run looks different!)...")
        plot_crash_data(full_data, crash_step=CRASH_STEP)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
