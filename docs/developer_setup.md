# Developer Setup Guide

This guide covers setting up a full local development environment for contributing to BugPilot.

---

## Repository Structure

```
bugpilot/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/             # Route handlers
│   │   ├── connectors/         # Evidence source integrations
│   │   │   ├── datadog/
│   │   │   ├── grafana/
│   │   │   ├── cloudwatch/
│   │   │   ├── github/
│   │   │   ├── kubernetes/
│   │   │   └── pagerduty/
│   │   ├── core/               # Config, DB, security, RBAC, logging
│   │   ├── graph/              # Investigation graph engine
│   │   ├── hypothesis/         # 6-pass hypothesis pipeline
│   │   ├── llm/                # LLM providers and service layer
│   │   │   └── providers/      # OpenAI, Anthropic, Azure, Ollama
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── privacy/            # PII redaction pipeline
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Domain services (dedup, retention, export…)
│   │   ├── webhooks/           # Webhook handlers and router
│   │   └── workers/            # Evidence collector
│   ├── migrations/             # Alembic migration files
│   │   └── versions/
│   ├── tests/                  # Test suite (pytest + pytest-asyncio)
│   └── pyproject.toml
├── cli/                        # typer CLI
│   ├── bugpilot/
│   │   ├── auth/               # License activation
│   │   ├── commands/           # All CLI command groups
│   │   └── output/             # human / json / verbose formatters
│   ├── tests/
│   └── pyproject.toml
├── docs/                       # This documentation
├── fixtures/                   # Sample configs and payloads
│   └── sample_configs/
└── docker-compose.yml
```

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or Docker)
- Git

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/skonlabs/bugpilot.git
cd bugpilot
```

### 2. Backend

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Create a .env file
cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/bugpilot_dev
JWT_SECRET=dev-only-secret-do-not-use-in-production-1234567890abcdef
FERNET_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
LOG_LEVEL=debug
EOF

# Apply it
export $(cat .env | xargs)

# Create the database
createdb bugpilot_dev

# Run migrations
alembic upgrade head

# Start the API with live reload
uvicorn app.main:app --reload --port 8000
```

### 3. CLI

```bash
cd cli
pip install -e .

# Point at local backend
export BUGPILOT_API_URL=http://localhost:8000
```

---

## Running Tests

Tests use an in-memory SQLite database — no running PostgreSQL needed.

```bash
cd backend

# Run all tests
pytest

# Run specific test file
pytest tests/test_hypothesis.py -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run only tests matching a keyword
pytest -k "test_dedup" -v

# Run with verbose output and no capture (useful for debugging)
pytest tests/test_retention.py -v -s
```

### Test database

The test suite uses `sqlite+aiosqlite:///:memory:` configured in `tests/conftest.py`. A cross-dialect `JSONB` TypeDecorator in `app/models/all_models.py` ensures models work with both PostgreSQL (production) and SQLite (tests).

### Writing tests

Follow the patterns in `tests/test_hypothesis.py` and `tests/test_dedup.py`:

```python
import pytest
from app.hypothesis.engine import HypothesisEngine

@pytest.mark.asyncio
async def test_my_feature():
    engine = HypothesisEngine(use_llm=False)
    result = await engine.generate(
        evidence=[{"id": "ev1", "kind": "log_snapshot", ...}],
        context={"service": "my-service"},
    )
    assert len(result) >= 1
    assert result[0].confidence_score > 0
```

For tests that need the database, use the `db_session` fixture from `conftest.py`:

```python
@pytest.mark.asyncio
async def test_db_feature(db_session):
    from app.models.all_models import Investigation, InvestigationStatus
    inv = Investigation(title="test", status=InvestigationStatus.open, ...)
    db_session.add(inv)
    await db_session.flush()
    assert inv.id is not None
```

---

## Code Style

BugPilot uses standard Python conventions:

- **Type hints** on all function signatures
- **Async/await** throughout (no sync blocking calls in API handlers or connectors)
- **structlog** for all logging (never `print()`)
- **Pydantic v2** with `ConfigDict` (not class-based `Config`)
- **SQLAlchemy 2.0** declarative style with `Mapped` / `mapped_column`

---

## Adding a New API Endpoint

1. Add a route handler to the appropriate file in `app/api/v1/`
2. Add request/response Pydantic schemas to `app/schemas/base.py`
3. Mount the router in `app/main.py` if it's a new file
4. Write tests in `backend/tests/`

```python
# app/api/v1/my_feature.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.rbac import TokenPayload, require_role, Role

router = APIRouter(prefix="/my-feature", tags=["my-feature"])

class MyFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str

@router.get("/{item_id}", response_model=MyFeatureResponse)
async def get_item(
    item_id: str,
    current_user: TokenPayload = Depends(require_role(Role.viewer)),
    db: AsyncSession = Depends(get_db),
):
    ...
```

---

## Adding a New Connector

1. Create a directory: `app/connectors/myplatform/`
2. Create `__init__.py` and `connector.py`
3. Subclass `BaseConnector` from `app.connectors.base`
4. Add a value to the `ConnectorType` enum in `app/models/all_models.py`
5. Register the connector in the admin connector factory
6. Add sample credentials to `fixtures/sample_configs/sample_connector_config.yaml`
7. Write tests in `backend/tests/test_connectors.py`

---

## Database Migrations

When you modify `app/models/all_models.py`, generate a new Alembic migration:

```bash
cd backend

# Auto-generate based on model diff
alembic revision --autogenerate -m "add_my_new_column"

# Review the generated file in migrations/versions/
# Always check autogenerated migrations before applying

# Apply
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## Debugging Tips

### View SQL queries

```bash
# In .env
LOG_LEVEL=debug

# Or set SQLAlchemy echo
# In app/core/db.py, change:
engine = create_async_engine(settings.database_url, echo=True)
```

### Test a specific connector locally

```python
# In a Python REPL or script
import asyncio
from app.connectors.datadog.connector import DatadogConnector
from datetime import datetime, timezone, timedelta
from app.connectors.base import ConnectorCapability

async def test():
    connector = DatadogConnector({
        "api_key": "YOUR_API_KEY",
        "app_key": "YOUR_APP_KEY",
        "base_url": "https://api.datadoghq.com",
    })
    result = await connector.validate()
    print(result)

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    until = datetime.now(timezone.utc)
    items = await connector.fetch_evidence(
        ConnectorCapability.LOGS, "payment-service", since, until
    )
    print(f"Got {len(items)} items")

asyncio.run(test())
```

### Inspect the hypothesis engine

```python
import asyncio
from app.hypothesis.engine import HypothesisEngine

async def test():
    engine = HypothesisEngine(use_llm=False)
    hypotheses = await engine.generate(
        evidence=[
            {"id": "ev1", "kind": "log_snapshot", "summary": "OOMKilled"},
            {"id": "ev2", "kind": "metric_snapshot", "summary": "memory spike"},
        ],
        context={"service": "payment-service"},
    )
    for h in hypotheses:
        print(f"{h.rank}. [{h.confidence_score:.0%}] {h.title}")

asyncio.run(test())
```

---

## Common Issues

### `FERNET_KEY` is not valid

Generate a proper key:

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### `asyncpg` SSL error

Add `?ssl=disable` for local development:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/bugpilot_dev?ssl=disable
```

### SQLite JSONB error in tests

Ensure the `JSONB` TypeDecorator is imported from `app.models.all_models`, not from `sqlalchemy.dialects.postgresql` directly. The TypeDecorator routes to `JSON` on SQLite automatically.

### `aiosqlite` not found

```bash
pip install aiosqlite
```

---

## Pull Request Guidelines

1. Run the full test suite before submitting: `pytest`
2. Add tests for any new feature or bug fix
3. Keep changes focused — one feature or fix per PR
4. Update the relevant doc file if your change affects user-facing behaviour
5. Ensure no Pydantic deprecation warnings (`class Config` → `model_config = ConfigDict(...)`)
