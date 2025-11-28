# SynthQuant API Examples

This folder contains example scripts demonstrating how to use the SynthQuant API.

## Prerequisites

```bash
pip install requests matplotlib pandas
```

## Examples

### 1. Market Crash Simulation (`fetch_crash_data.py`)

Demonstrates fetching synthetic market data with an injected crash event and visualizing it.

**Features:**
- Connects to the local SynthQuant API
- Generates AAPL-calibrated synthetic data
- Injects a 35% market crash at a specific time step
- Creates a dual-panel visualization (price + returns)

**Usage:**
```bash
# 1. Start the API server (from project root)
uvicorn app.main:app --reload

# 2. Run the example (in another terminal)
python examples/fetch_crash_data.py
```

**Output:**
- Console output showing API status and dataset info
- `crash_simulation.png` - Saved visualization

## Adding Your Own Examples

Feel free to add more example scripts here! Some ideas:
- IPO event simulation
- Earnings shock scenarios
- Multi-asset portfolio stress testing
- Backtesting strategy visualization
