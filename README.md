# SynthQuant API

A modular, lightweight FastAPI backend that serves synthetic market data using Geometric Brownian Motion (GBM) simulation.

## 🚀 Features

- **Synthetic Data Generation**: Generate realistic price paths using GBM
- **Real Market Profiling**: Fetch real stock data to calibrate GBM parameters
- **Deterministic Output**: Same seed produces identical results
- **API Key Authentication**: Header-based authentication with `X-API-KEY`
- **Rate Limiting**: 10 requests per minute per API key
- **In-Memory Storage**: Thread-safe storage with no external dependencies
- **Clean Architecture**: Modular code structure with separation of concerns
- **Admin Interface**: Hidden endpoint for dynamic API key creation
- **CI/CD Pipeline**: Automated testing with GitHub Actions
- **Multi-Market Support**: US and Indian (NSE) stock markets via yfinance

## 📁 Project Structure

```
/app
  ├── main.py            # Entry point, app initialization
  ├── config.py          # Settings, API Keys, Constants
  ├── models.py          # Pydantic schemas (Request/Response objects)
  ├── store.py           # In-memory database singleton
  ├── security.py        # API Key validation & Rate Limiting logic
  ├── exceptions.py      # Custom exception classes
  ├── services.py        # The "Engine" (Dummy Data Generation logic)
  ├── services/
  │   └── market_profiler.py  # Real market data fetching & analysis
  └── routers/
      ├── v1.py          # API Route definitions
      └── admin.py       # Hidden admin endpoints
/tests
  ├── conftest.py        # Pytest fixtures
  └── test_main.py       # Test suite
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
