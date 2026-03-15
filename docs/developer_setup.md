# Developer Setup Guide

> **This guide is for contributors building BugPilot from source.** If you are a BugPilot user, [download the CLI binary](./getting-started.md) — you do not need this guide.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or Docker)
- Node.js 20+ (for the frontend website)
- Git

---

## Repository Structure

```
bugpilot/
├── src/
│   ├── backend/                  # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/           # Route handlers
│   │   │   ├── connectors/       # Evidence source integrations
│   │   │   │   ├── datadog/
│   │   │   │   ├── grafana/
│   │   │   │   ├── cloudwatch/
│   │   │   │   ├── github/
│   │   │   │   ├── kubernetes/
│   │   │   │   └── pagerduty/
│   │   │   ├── core/             # Config, DB, security, RBAC, logging
│   │   │   ├── graph/            # Investigation graph engine
│   │   │   ├── hypothesis/       # 6-pass hypothesis pipeline
│   │   │   ├── llm/              # LLM providers and service layer
│   │   │   ├── models/           # SQLAlchemy ORM models
│   │   │   ├── privacy/          # PII redaction pipeline
│   │   │   ├── schemas/          # Pydantic request/response schemas
│   │   │   ├── services/         # Domain services
│   │   │   ├── webhooks/         # Webhook handlers
│   │   │   └── workers/          # Evidence collector
│   │   ├── migrations/           # Alembic migrations
│   │   ├── tests/                # pytest test suite
│   │   └── pyproject.toml
│   ├── cli/                      # typer CLI (source for the binary)
│   │   ├── bugpilot/
│   │   │   ├── auth/             # License activation
│   │   │   ├── commands/         # CLI command groups
│   │   │   └── output/           # human / json / verbose formatters
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── docs/                     # Documentation
├── fixtures/                     # Sample configs and webhook payloads
└── docker-compose.yml
```

---

## Backend Setup

```bash
cd src/backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Set required environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost/bugpilot_dev?ssl=disable"
export JWT_SECRET="dev-only-secret-do-not-use-in-production-1234567890abcdef"
export FERNET_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export LOG_LEVEL="debug"

# Create the database
createdb bugpilot_dev

# Run migrations
alembic upgrade head

# Start the API with live reload
uvicorn app.main:app --reload --port 8000
```

The API is now running at `http://localhost:8000`. Swagger UI is at `http://localhost:8000/docs`.

---

## CLI Setup (for development)

```bash
cd src/cli

# Install in editable mode
pip install -e .

# Point at your local backend
export BUGPILOT_API_URL=http://localhost:8000

# Verify
bugpilot --version
```

> The distributed CLI binary is compiled from this source. Users never install from source — they download the pre-built binary from bugpilot.io.

---

## Running Tests

The test suite uses an in-memory SQLite database — no running PostgreSQL needed.

```bash
cd src/backend

# Run all tests
pytest

# Run a specific file
pytest tests/test_hypothesis.py -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run tests matching a keyword
pytest -k "test_dedup" -v
```

The test suite uses `sqlite+aiosqlite:///:memory:` via a cross-dialect `JSONB` TypeDecorator in `app/models/all_models.py` that routes to `JSON` on SQLite automatically.

---

## Code Style

- **Type hints** on all function signatures
- **Async/await** throughout — no sync blocking calls in API handlers or connectors
- **structlog** for all logging — never `print()`
- **Pydantic v2** with `ConfigDict` (not the deprecated `class Config`)
- **SQLAlchemy 2.0** declarative style with `Mapped` / `mapped_column`

---

## Adding a New API Endpoint

1. Add a route handler to the appropriate file in `app/api/v1/`
2. Add request/response Pydantic schemas to `app/schemas/base.py`
3. Mount the router in `app/main.py` if it's a new file
4. Write tests in `backend/tests/`

```python
# app/api/v1/my_feature.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.rbac import TokenPayload, require_role, Role

router = APIRouter(prefix="/my-feature", tags=["my-feature"])

class MyFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str

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

1. Create `app/connectors/myplatform/__init__.py` and `connector.py`
2. Subclass `BaseConnector` from `app.connectors.base`
3. Implement `capabilities()`, `validate()`, and `fetch_evidence()`
4. Add a value to the `ConnectorType` enum in `app/models/all_models.py`
5. Register the connector in the connector factory
6. Add a sample config to `fixtures/sample_configs/sample_connector_config.yaml`
7. Write tests in `backend/tests/test_connectors.py`

---

## Database Migrations

When you modify `app/models/all_models.py`, generate a new Alembic migration:

```bash
cd src/backend

# Auto-generate from model diff
alembic revision --autogenerate -m "add_my_new_column"

# Review the generated file in migrations/versions/
# Always review before applying — autogenerate is not perfect

# Apply
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## Common Issues

### `FERNET_KEY` is not valid

Generate a proper key:

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

### `asyncpg` SSL error on local dev

Add `?ssl=disable` to the local database URL:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/bugpilot_dev?ssl=disable
```

### `aiosqlite` not found (test suite)

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
