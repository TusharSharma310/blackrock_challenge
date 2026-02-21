# Retirement Savings API

A production-grade REST API for automated retirement savings through expense-based micro-investments.

## Overview

This API enables automated savings by:
1. Rounding expenses up to the next multiple of 100 (saving the "remanent")
2. Applying configurable rules for fixed amounts (q periods) and extras (p periods)
3. Grouping savings into evaluation periods (k periods)
4. Calculating compound investment returns for NPS or NIFTY 50 Index Fund
5. Adjusting returns for inflation to provide real-value projections

## Architecture

```
blackrock-api/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── models/
│   │   └── schemas.py             # Pydantic request/response models
│   ├── services/
│   │   ├── transaction_service.py # Core business logic (q/p/k rules)
│   │   ├── returns_service.py     # Financial calculations (NPS/Index)
│   │   └── performance_service.py # System metrics tracking
│   └── routers/
│       ├── transactions.py        # Transaction endpoints
│       ├── returns.py             # Returns calculation endpoints
│       └── performance.py         # Performance metrics endpoint
├── tests/
│   ├── test_transactions.py       # Transaction unit + integration tests
│   ├── test_returns.py            # Returns unit + integration tests
│   └── test_performance_load.py   # Load and stress tests
├── Dockerfile
├── compose.yaml
├── requirements.txt
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/blackrock/challenge/v1/transactions:parse` | Calculate ceiling & remanent |
| POST | `/blackrock/challenge/v1/transactions:validator` | Validate transactions |
| POST | `/blackrock/challenge/v1/transactions:filter` | Apply q/p/k period rules |
| POST | `/blackrock/challenge/v1/returns:nps` | NPS investment returns (7.11%) |
| POST | `/blackrock/challenge/v1/returns:index` | Index Fund returns (14.49%) |
| GET  | `/blackrock/challenge/v1/performance` | System performance metrics |
| GET  | `/health` | Health check |
| GET  | `/docs` | Interactive Swagger UI |

## Setup & Running

### Prerequisites
- Docker and Docker Compose (recommended)
- OR Python 3.11+

---

### Option 1: Docker Compose (Recommended)

```bash
# Build and run
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### Option 2: Docker (Manual)

```bash
# Build image
docker build -t blk-hacking-ind-name-lastname .

# Run container
docker run -d -p 5477:5477 blk-hacking-ind-name-lastname

# Check status
docker ps

# View logs
docker logs <container-id>
```

### Option 3: Local Python

```bash
# Create virtual environment
python3 -m venv venv
#source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 5477 --reload
```

---

## Testing

```bash
# Install test dependencies (included in requirements.txt)
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_transactions.py -v
pytest tests/test_returns.py -v
pytest tests/test_performance_load.py -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=term-missing

# Run only unit tests
pytest tests/ -v -m unit

# Run only integration tests
pytest tests/ -v -m integration
```

---

## API Usage Examples

### 1. Parse Expenses

```bash
curl -X POST http://localhost:5477/blackrock/challenge/v1/transactions:parse \
  -H "Content-Type: application/json" \
  -d '[
    {"date": "2023-10-12 20:15:30", "amount": 250},
    {"date": "2023-02-28 15:49:20", "amount": 375},
    {"date": "2023-07-01 21:59:00", "amount": 620},
    {"date": "2023-12-17 08:09:45", "amount": 480}
  ]'
```

**Response:**
```json
{
  "transactions": [
    {"date": "2023-10-12 20:15:30", "amount": 250.0, "ceiling": 300.0, "remanent": 50.0},
    {"date": "2023-02-28 15:49:20", "amount": 375.0, "ceiling": 400.0, "remanent": 25.0},
    {"date": "2023-07-01 21:59:00", "amount": 620.0, "ceiling": 700.0, "remanent": 80.0},
    {"date": "2023-12-17 08:09:45", "amount": 480.0, "ceiling": 500.0, "remanent": 20.0}
  ],
  "totalAmount": 1725.0,
  "totalCeiling": 1900.0,
  "totalRemanent": 175.0
}
```

### 2. Validate Transactions

```bash
curl -X POST http://localhost:5477/blackrock/challenge/v1/transactions:validator \
  -H "Content-Type: application/json" \
  -d '{
    "wage": 50000,
    "transactions": [
      {"date": "2023-01-15 10:30:00", "amount": 2000, "ceiling": 2100, "remanent": 100},
      {"date": "2023-07-10 09:15:00", "amount": -250, "ceiling": 200, "remanent": 30}
    ]
  }'
```

### 3. Filter with Period Rules

```bash
curl -X POST http://localhost:5477/blackrock/challenge/v1/transactions:filter \
  -H "Content-Type: application/json" \
  -d '{
    "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
    "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:59"}],
    "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
    "wage": 50000,
    "transactions": [
      {"date": "2023-02-28 15:49:20", "amount": 375},
      {"date": "2023-07-01 21:59:00", "amount": 620},
      {"date": "2023-10-12 20:15:30", "amount": 250},
      {"date": "2023-12-17 08:09:45", "amount": 480}
    ]
  }'
```

### 4. NPS Returns Calculation

```bash
curl -X POST http://localhost:5477/blackrock/challenge/v1/returns:nps \
  -H "Content-Type: application/json" \
  -d '{
    "age": 29,
    "wage": 50000,
    "inflation": 5.5,
    "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
    "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:59"}],
    "k": [
      {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"},
      {"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:59"}
    ],
    "transactions": [
      {"date": "2023-02-28 15:49:20", "amount": 375},
      {"date": "2023-07-01 21:59:00", "amount": 620},
      {"date": "2023-10-12 20:15:30", "amount": 250},
      {"date": "2023-12-17 08:09:45", "amount": 480}
    ]
  }'
```

**Expected Response:**
```json
{
  "totalTransactionAmount": 1725.0,
  "totalCeiling": 1900.0,
  "savingsByDates": [
    {
      "start": "2023-01-01 00:00:00",
      "end": "2023-12-31 23:59:59",
      "amount": 145.0,
      "profit": 86.88,
      "taxBenefit": 0.0
    },
    {
      "start": "2023-03-01 00:00:00",
      "end": "2023-11-30 23:59:59",
      "amount": 75.0,
      "profit": 44.94,
      "taxBenefit": 0.0
    }
  ]
}
```

### 5. Performance Metrics

```bash
curl http://localhost:5477/blackrock/challenge/v1/performance
```

**Response:**
```json
{
  "time": "00:00:00.045",
  "memory": "28.54 MB",
  "threads": 4
}
```

---

## Business Rules Summary

### Rounding (ceiling)
- Every expense is rounded **up** to the next strict multiple of 100
- `ceiling = (floor(amount / 100) + 1) × 100`
- `remanent = ceiling - amount`

### Processing Order
1. Calculate ceiling and remanent
2. Apply **q** rules (if applicable): replace remanent with fixed amount
3. Apply **p** rules (if applicable): add extra to remanent
4. Group by **k** periods: sum remanents within each date range

### Q Period Rules
- Replaces remanent with a fixed amount for transactions within the period
- If multiple q periods match: use the one with the **latest start date**
- Tie-break: **first in the original list**

### P Period Rules
- Adds an extra amount to the remanent
- **All** matching p periods add their extras (cumulative)
- Applied after q rules

### K Period Rules
- Groups transactions for evaluation
- Each transaction can belong to **multiple** k periods
- Each k period calculates its sum independently

### Investment Options
| Option | Rate | Tax Benefit |
|--------|------|-------------|
| NPS | 7.11% annual | Yes (up to ₹2L or 10% income) |
| Index Fund (NIFTY 50) | 14.49% annual | No |

### Formulas
- **Compound Interest**: `A = P × (1 + r)^t`
- **Inflation Adjusted**: `A_real = A / (1 + inflation)^t`
- **Profit**: `profit = A_real - P`
- **Years**: `t = 60 - age` if age < 60, else `t = 5`

### Tax Slabs (Simplified)
| Income Range | Rate |
|-------------|------|
| ₹0 – ₹7,00,000 | 0% |
| ₹7,00,001 – ₹10,00,000 | 10% on amount above ₹7L |
| ₹10,00,001 – ₹12,00,000 | 15% on amount above ₹10L |
| ₹12,00,001 – ₹15,00,000 | 20% on amount above ₹12L |
| Above ₹15,00,000 | 30% on amount above ₹15L |

---

## Design Decisions & Architecture

### Framework Choice: FastAPI
- Native async support for high concurrency
- Automatic OpenAPI/Swagger documentation
- Pydantic v2 for ultra-fast validation
- Production-proven with uvicorn ASGI server

### Security Features
- Non-root Docker user
- Security headers (X-Content-Type-Options, X-Frame-Options, etc.)
- Input validation with Pydantic
- Error messages that don't leak internals
- CORS configuration

### Performance Optimizations
- GZip compression for large responses
- Request tracking middleware (non-blocking)
- Efficient period matching with linear scan (O(n×q))
- Stateless request handling (horizontally scalable)
- Docker layer caching for fast image rebuilds

### Scalability
- Stateless API design (no shared state between requests)
- Docker Compose ready for orchestration
- Configurable worker count via `WORKERS` env var
- Memory-efficient streaming for large datasets

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.115.0 | Web framework |
| uvicorn[standard] | 0.30.6 | ASGI server |
| pydantic | 2.8.2 | Data validation |
| psutil | 6.0.0 | System metrics |
| httpx | 0.27.2 | Async HTTP client |
| pytest | 8.3.2 | Testing framework |
| pytest-asyncio | 0.24.0 | Async test support |

---

## Constraints Compliance

| Constraint | Value | Status |
|-----------|-------|--------|
| Port | 5477 | ✅ |
| OS | Linux (Debian slim) | ✅ |
| Dockerfile format | First line = build command | ✅ |
| Docker image name | `blk-hacking-ind-{name-lastname}` | ✅ |
| Compose file | `compose.yaml` | ✅ |
| Tests folder | `tests/` | ✅ |
| n (transactions) | < 10⁶ | ✅ |
| q, p, k periods | < 10⁶ each | ✅ |
| amount | < 5×10⁵ | ✅ |

---
