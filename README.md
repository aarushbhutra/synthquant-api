# SynthQuant API

A modular, lightweight FastAPI backend that serves synthetic market data using Geometric Brownian Motion (GBM) simulation.

## 🚀 Features

- **Synthetic Data Generation**: Generate realistic price paths using GBM
- **Real Market Profiling**: Fetch real stock data to calibrate GBM parameters
- **Synthesis Engine**: Generate synthetic data calibrated to real market behavior
- **Event Injection**: Scenario stress testing with IPO, Crash, and Earnings events
- **Volatility/Drift Control**: Fine-tune synthetic data with multipliers
- **Deterministic Output**: Same seed produces identical results
- **API Key Authentication**: Header-based authentication with `X-API-KEY`
- **Rate Limiting**: 10 requests per minute per API key
- **In-Memory Storage**: Thread-safe storage with no external dependencies
- **Clean Architecture**: Modular code structure with separation of concerns
- **Admin Interface**: Hidden endpoint for dynamic API key creation
- **CI/CD Pipeline**: Automated testing with GitHub Actions
- **Multi-Market Support**: US and Indian (NSE) stock markets via yfinance
- **Multiple Frequencies**: Support for 1m, 5m, 15m, 30m, 1h, 4h, 1d intervals

## 📁 Project Structure

```
/app
  ├── main.py            # Entry point, app initialization with lifespan
  ├── config.py          # Settings, API Keys, Constants
  ├── models.py          # Pydantic schemas (Request/Response objects)
  ├── store.py           # In-memory database singleton
  ├── security.py        # API Key validation & Rate Limiting logic
  ├── exceptions.py      # Custom exception classes
  ├── services/
  │   ├── __init__.py        # Service exports
  │   ├── data_generator.py  # Basic GBM data generation
  │   ├── market_profiler.py # Real market data fetching via yfinance
  │   ├── generator.py       # Synthesis engine (realistic GBM generator)
  │   └── event_manager.py   # Event injection for stress testing
  └── routers/
      ├── v1.py          # API Route definitions
      └── admin.py       # Hidden admin endpoints
/tests
  ├── conftest.py        # Pytest fixtures
  ├── test_main.py       # Main test suite
  ├── test_generator.py  # Synthesis engine tests
  └── test_events.py     # Event injection tests
/.github
  └── workflows/
      └── test.yaml      # CI pipeline
requirements.txt
README.md
```

## 🛠️ Installation

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   
   # On Windows
   .\venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 🏃 Running the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🧪 Running Tests

```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest -v
```

## 🔑 Authentication

All protected endpoints require an `X-API-KEY` header.

### Available API Keys (Development)

- `sk-synthquant-dev-001`
- `sk-synthquant-dev-002`
- `sk-synthquant-test-001`

### Example Request

```bash
curl -X GET "http://localhost:8000/v1/datasets" \
  -H "X-API-KEY: sk-synthquant-dev-001"
```

## 📡 API Endpoints

### Public Endpoints

#### GET /v1/status
Check service status.

```bash
curl http://localhost:8000/v1/status
```

Response:
```json
{
  "service": "ok",
  "timestamp": "2024-01-15T10:30:00Z",
  "note": "Simulation Mode"
}
```

#### POST /v1/apikeys/verify
Verify an API key and check rate limit status.

```bash
curl -X POST "http://localhost:8000/v1/apikeys/verify" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-synthquant-dev-001"}'
```

Response:
```json
{
  "valid": true,
  "quota_remaining": 10,
  "limit": 10
}
```

### Protected Endpoints (Require X-API-KEY)

#### GET /v1/datasets
List all generated datasets.

```bash
curl -X GET "http://localhost:8000/v1/datasets" \
  -H "X-API-KEY: sk-synthquant-dev-001"
```

#### GET /v1/datasets/{dataset_id}
Get dataset details with preview.

```bash
curl -X GET "http://localhost:8000/v1/datasets/ds-000001" \
  -H "X-API-KEY: sk-synthquant-dev-001"
```

#### POST /v1/datasets/create
Create a new synthetic dataset.

```bash
curl -X POST "http://localhost:8000/v1/datasets/create" \
  -H "X-API-KEY: sk-synthquant-dev-001" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "crypto-backtest",
    "assets": [
      {"symbol": "BTC", "start_price": 45000.0},
      {"symbol": "ETH", "start_price": 2500.0}
    ],
    "frequency": "1h",
    "horizon_days": 30,
    "seed": 42
  }'
```

Response:
```json
{
  "dataset_id": "ds-000001",
  "status": "ready",
  "realism_score": 92.5,
  "download_url": "http://localhost:8000/v1/datasets/ds-000001/download",
  "preview": {
    "assets": [
      {
        "symbol": "BTC",
        "timestamps": ["2024-01-15T10:00:00Z", ...],
        "prices": [45000.0, 44987.23, ...]
      }
    ]
  }
}
```

### Debug Endpoints (Require X-API-KEY)

#### POST /v1/datasets/create/realistic
Create a synthetic dataset calibrated to real market parameters. This endpoint fetches real market data from Yahoo Finance and uses the statistical properties (mu, sigma, last_price) to generate synthetic data that mimics real asset behavior.

```bash
curl -X POST "http://localhost:8000/v1/datasets/create/realistic" \
  -H "X-API-KEY: sk-synthquant-dev-001" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "realistic-backtest",
    "assets": [
      {
        "symbol": "AAPL",
        "region": "US",
        "volatility_multiplier": 1.0,
        "drift_multiplier": 1.0
      },
      {
        "symbol": "RELIANCE",
        "region": "IN",
        "volatility_multiplier": 1.5,
        "drift_multiplier": 0.8
      }
    ],
    "frequency": "1h",
    "horizon_days": 7,
    "seed": 42
  }'
```

**Parameters:**
- `volatility_multiplier`: Scale real volatility (2.0 = 2x more volatile)
- `drift_multiplier`: Scale real drift (0.5 = half the trend)
- `region`: "US" for US stocks, "IN" for Indian NSE stocks

Response:
```json
{
  "id": "abc123-...",
  "project": "realistic-backtest",
  "created_at": "2024-01-15T10:30:00Z",
  "row_count": 337,
  "preview": [...]
}
```

#### POST /v1/debug/profile
Profile a real market asset to get GBM parameters. Supports US and Indian (NSE) markets.

```bash
# US Stock
curl -X POST "http://localhost:8000/v1/debug/profile" \
  -H "X-API-KEY: sk-synthquant-dev-001" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "region": "US"}'

# Indian Stock (NSE)
curl -X POST "http://localhost:8000/v1/debug/profile" \
  -H "X-API-KEY: sk-synthquant-dev-001" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "RELIANCE", "region": "IN"}'
```

Response:
```json
{
  "symbol": "AAPL",
  "region": "US",
  "mu": 0.00089532,
  "sigma": 0.01823456,
  "last_price": 178.52,
  "data_points": 252,
  "fetched_at": "2025-11-27T10:30:00Z",
  "annualized_return": 0.2256,
  "annualized_volatility": 0.2894
}
```

**Parameters:**
- `mu`: Daily drift (mean log return)
- `sigma`: Daily volatility (std dev of log returns)
- `annualized_return`: mu × 252 trading days
- `annualized_volatility`: sigma × √252

## 🎯 Event Injection (Stress Testing)

SynthQuant supports **scenario-based stress testing** through event injection. Events are market shocks that can be injected into synthetic data at specific time steps to simulate real-world scenarios like IPOs, market crashes, and earnings surprises.

### Event Types

| Event Type | Description | Parameters |
|------------|-------------|------------|
| `ipo` | Simulates an IPO by setting all prices before `trigger_step` to `null` | `trigger_step` |
| `crash` | Gradual price decline over duration, permanent price reduction | `trigger_step`, `magnitude`, `duration` |
| `earnings` | Instant price jump/drop at trigger step (gap up/down) | `trigger_step`, `magnitude` |

### Event Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | One of: `ipo`, `crash`, `earnings` |
| `trigger_step` | integer | The data row index where the event triggers |
| `magnitude` | float | Size of impact (e.g., `0.3` = 30% change). Positive = increase, negative = decrease |
| `duration` | integer | For `crash`: number of steps over which the decline occurs (default: 5) |

### Example: IPO Event

Simulate a stock that IPOs mid-dataset (first 10 data points are pre-IPO):

```bash
curl -X POST "http://localhost:8000/v1/datasets/create" \
  -H "X-API-KEY: sk-synthquant-dev-001" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "ipo-simulation",
    "assets": [{"symbol": "NEWCO", "start_price": 25.0}],
    "frequency": "1h",
    "horizon_days": 2,
    "seed": 42,
    "events": [
      {"type": "ipo", "trigger_step": 10}
    ]
  }'
```

**Result:** Prices at indices 0-9 will be `null`, prices from index 10 onward will have values.

### Example: Market Crash Event

Simulate a 30% crash occurring at step 50, spread over 10 time steps:

```bash
curl -X POST "http://localhost:8000/v1/datasets/create/realistic" \
  -H "X-API-KEY: sk-synthquant-dev-001" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "crash-stress-test",
    "assets": [{"symbol": "AAPL", "region": "US"}],
    "frequency": "1h",
    "horizon_days": 7,
    "seed": 42,
    "events": [
      {"type": "crash", "trigger_step": 50, "magnitude": 0.3, "duration": 10}
    ]
  }'
```

**Result:** Starting at index 50, prices gradually decline by 30% over 10 steps. Prices after step 60 remain at the reduced level.

### Example: Earnings Shock Event

Simulate a +15% gap up on positive earnings at step 30:

```bash
curl -X POST "http://localhost:8000/v1/datasets/create" \
  -H "X-API-KEY: sk-synthquant-dev-001" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "earnings-gap",
    "assets": [{"symbol": "TECH", "start_price": 100.0}],
    "frequency": "1h",
    "horizon_days": 3,
    "seed": 42,
    "events": [
      {"type": "earnings", "trigger_step": 30, "magnitude": 0.15}
    ]
  }'
```

**Result:** Price instantly jumps 15% at index 30, all subsequent prices are 15% higher.

For a negative earnings shock (gap down), use negative magnitude:
```json
{"type": "earnings", "trigger_step": 30, "magnitude": -0.20}
```

### Example: Multiple Events

Combine events to create complex scenarios:

```bash
curl -X POST "http://localhost:8000/v1/datasets/create" \
  -H "X-API-KEY: sk-synthquant-dev-001" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "complex-scenario",
    "assets": [{"symbol": "STOCK", "start_price": 50.0}],
    "frequency": "1h",
    "horizon_days": 10,
    "seed": 42,
    "events": [
      {"type": "ipo", "trigger_step": 5},
      {"type": "earnings", "trigger_step": 50, "magnitude": 0.10},
      {"type": "crash", "trigger_step": 100, "magnitude": 0.25, "duration": 8}
    ]
  }'
```

**Timeline:**
1. Steps 0-4: No data (pre-IPO)
2. Steps 5-49: Normal price movement
3. Step 50: +10% gap up (earnings)
4. Steps 51-99: Normal movement at elevated level
5. Steps 100-107: Gradual 25% crash
6. Steps 108+: Prices at reduced level

### Notes

- Events are applied **in the order specified** in the array
- `trigger_step` is 0-indexed (first data point = 0)
- If `trigger_step` exceeds data length, the event is ignored
- Events apply to **all assets** in the dataset
- IPO events with `trigger_step=0` have no effect (all data is post-IPO)

### Admin Endpoints (Hidden - Require X-ADMIN-SECRET)

#### POST /internal/apikeys/create
Create a new API key dynamically. This endpoint is hidden from OpenAPI documentation.

```bash
curl -X POST "http://localhost:8000/internal/apikeys/create" \
  -H "X-ADMIN-SECRET: your_admin_secret"
```

Response:
```json
{
  "new_key": "sk-synthquant-a1b2c3d4e5f67890",
  "created_at": "2024-01-15T10:30:00Z",
  "note": "Save this, it will not be shown again."
}
```

## ⚙️ Configuration

Configuration is managed in `app/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `RATE_LIMIT_REQUESTS` | 10 | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 | Rate limit window (seconds) |
| `DEFAULT_VOLATILITY` | 0.02 | GBM volatility parameter |
| `DEFAULT_DRIFT` | 0.0001 | GBM drift parameter |
| `ADMIN_SECRET` | (set in config) | Secret for admin endpoints |

## 🔄 CI/CD Pipeline

This project includes a GitHub Actions workflow that runs on every push to `main` and every pull request.

### GitHub Secrets Required

Add these secrets in your repository settings (**Settings → Secrets and variables → Actions**):

| Secret Name | Description |
|-------------|-------------|
| `ADMIN_SECRET` | Admin endpoint authentication secret |
| `INITIAL_API_KEY` | Valid API key for running tests |

### Pipeline Features

- ✅ Runs on Python 3.13
- ✅ Executes full test suite with pytest
- ✅ Secrets injected via environment variables
- ✅ API keys redacted in logs

## 📊 Supported Frequencies

- `1m` - 1 minute
- `5m` - 5 minutes
- `15m` - 15 minutes
- `30m` - 30 minutes
- `1h` - 1 hour
- `4h` - 4 hours
- `1d` - 1 day

## 🧮 GBM Algorithm

The Geometric Brownian Motion model used:

$$dS = \mu S dt + \sigma S dW$$

Where:
- $S$ = Asset price
- $\mu$ = Drift coefficient
- $\sigma$ = Volatility
- $dW$ = Wiener process

Discrete approximation:
$$S(t+dt) = S(t) \cdot \exp\left((\mu - \frac{\sigma^2}{2})dt + \sigma\sqrt{dt}Z\right)$$

Where $Z \sim N(0,1)$

## 📝 License

See [LICENSE](LICENSE) file for details.
