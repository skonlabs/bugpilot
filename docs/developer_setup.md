# Developer Setup

## Prerequisites

- Python 3.11 or higher (`python3 --version`)
- Docker and Docker Compose (`docker --version`, `docker compose version`)
- pip 23+ (`pip --version`)
- git (`git --version`)

---

## Step-by-Step Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/bugpilot.git
cd bugpilot
```

### 2. Start PostgreSQL

```bash
docker-compose up -d postgres
```

Verify PostgreSQL is running:
```bash
docker-compose ps
# Should show postgres as "Up" and healthy
```

### 3. Install backend dependencies

```bash
cd backend
pip install -e ".[dev]"
```

This installs the backend package in editable mode plus development dependencies:
`pytest`, `pytest-asyncio`, `respx`, `pytest-cov`, `httpx`.

### 4. Set required environment variables

Copy the example env file and edit it:
```bash
cp ../.env.example .env   # if .env.example exists, otherwise create .env
```

Minimum required variables for local development:

```bash
# .env (backend directory)

# Database
DATABASE_URL=postgresql+asyncpg://bugpilot:bugpilot@localhost:5432/bugpilot

# JWT signing secret - CHANGE THIS in production
JWT_SECRET=dev-jwt-secret-change-me-in-production

# JWT settings
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Fernet encryption key for connector credentials
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# If empty, a new key is generated on each startup (dev only - credentials lost on restart)
FERNET_KEY=

# CORS - allowed origins for the API
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8080"]

# Rate limiting
ACTIVATION_RATE_LIMIT_PER_HOUR=10

# Evidence retention
EVIDENCE_TTL_MINUTES=10

# Connector settings
CONNECTOR_TIMEOUT_SECONDS=30
CONNECTOR_MAX_RETRIES=3

# LLM providers (optional - needed for LLM hypothesis generation)
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
# OLLAMA_BASE_URL=http://localhost:11434
```

### 5. Run database migrations

```bash
cd backend   # if not already there
alembic upgrade head
```

Verify migrations applied:
```bash
alembic current
# Should show the latest revision as (head)
```

### 6. Start the backend API

```bash
uvicorn app.main:app --reload --port 8000
```

The API is available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
- Health: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

### 7. Install the CLI

```bash
cd ../cli
pip install -e .
```

Verify the CLI is installed:
```bash
bugpilot --help
```

### 8. Create a license and activate the CLI

First, create a development license via the API:
```bash
curl -X POST http://localhost:8000/api/v1/license \
  -H "Content-Type: application/json" \
  -d '{
    "org_slug": "dev-org",
    "org_display_name": "Development Organisation",
    "tier": "team",
    "seat_limit": 10
  }'
# Note the license_key from the response
```

Then activate the CLI:
```bash
bugpilot auth activate
# Enter your license key and email when prompted
```

Or pass directly:
```bash
bugpilot auth activate --key <license_key> --email you@example.com
```

### 9. Verify the setup

```bash
bugpilot auth status
# Should show: Authenticated as you@example.com (investigator)

bugpilot investigate list
# Should show: No investigations found
```

### 10. Run the tests

```bash
cd ../backend   # from cli directory, go back to backend
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

Run a specific test file:
```bash
pytest tests/test_rbac.py -v
pytest tests/test_webhooks.py -v
pytest tests/test_connectors.py -v
```

### 11. Export the OpenAPI schema

With the backend running:
```bash
curl http://localhost:8000/openapi.json > openapi/bugpilot_v1.yaml
```

Or in JSON format:
```bash
curl http://localhost:8000/openapi.json | python -m json.tool > openapi/bugpilot_v1.json
```

---

## All Required Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://bugpilot:bugpilot@localhost:5432/bugpilot` | Yes | PostgreSQL async connection string |
| `JWT_SECRET` | `change-me-in-production` | Yes | HS256 JWT signing secret (min 32 chars in production) |
| `JWT_ALGORITHM` | `HS256` | No | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `60` | No | Access token TTL in minutes |
| `FERNET_KEY` | (auto-generated) | Recommended | Fernet key for encrypting connector credentials at rest |
| `ALLOWED_ORIGINS` | `["http://localhost:3000","http://localhost:8080"]` | No | JSON array of CORS-allowed origins |
| `ACTIVATION_RATE_LIMIT_PER_HOUR` | `10` | No | Max license activation attempts per hour per IP |
| `SECRET_GRACE_PERIOD_HOURS` | `24` | No | Hours the previous webhook secret is still accepted after rotation |
| `CONNECTOR_TIMEOUT_SECONDS` | `30` | No | HTTP timeout for connector requests |
| `CONNECTOR_MAX_RETRIES` | `3` | No | Maximum retry attempts for connector requests |
| `EVIDENCE_TTL_MINUTES` | `10` | No | Minutes before evidence raw payload is nulled (0 = keep forever) |
| `ANTHROPIC_API_KEY` | - | For LLM | Anthropic API key |
| `OPENAI_API_KEY` | - | For LLM | OpenAI API key |
| `AZURE_OPENAI_API_KEY` | - | For LLM | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | - | For LLM | Azure OpenAI endpoint URL |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | For local LLM | Ollama base URL |

### CLI (`~/.config/bugpilot/config`)

| Variable | Default | Description |
|----------|---------|-------------|
| `BUGPILOT_API_URL` | `http://localhost:8000` | Backend API base URL |
| `BUGPILOT_LICENSE_KEY` | (none) | License key (alternative to interactive prompt) |
| `BUGPILOT_OUTPUT` | `human` | Output format: `human` \| `json` \| `verbose` |

---

## Code Structure

```
bugpilot/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # FastAPI route handlers (auth, investigations, evidence, etc.)
│   │   ├── connectors/       # External system integrations (datadog, grafana, k8s, etc.)
│   │   ├── core/             # Config, DB engine, security, RBAC, logging
│   │   ├── graph/            # Investigation graph types and service
│   │   ├── hypothesis/       # Hypothesis generation engine
│   │   ├── llm/              # LLM provider abstraction (4 providers)
│   │   ├── models/           # SQLAlchemy ORM models (21 tables)
│   │   ├── privacy/          # PII redaction utilities
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic layer
│   │   ├── webhooks/         # Webhook intake handlers and router
│   │   ├── workers/          # Background task workers
│   │   └── main.py           # FastAPI app factory
│   ├── migrations/           # Alembic migration scripts
│   ├── tests/                # pytest test suite
│   ├── Dockerfile            # Production Docker image
│   └── pyproject.toml
│
├── cli/
│   ├── bugpilot/
│   │   ├── auth/             # License activation client
│   │   ├── commands/         # CLI command implementations
│   │   ├── output/           # Output formatters (human, JSON, verbose)
│   │   ├── context.py        # Shared app context (API URL, auth headers)
│   │   ├── session.py        # Session token storage and refresh
│   │   └── main.py           # Click CLI entry point
│   └── pyproject.toml
│
├── docs/                     # Architecture and connector documentation
├── fixtures/                 # Sample configs and webhook payloads
├── openapi/                  # Exported OpenAPI specs
└── docker-compose.yml
```

---

## Generating Alembic Migrations

After changing SQLAlchemy models in `app/models/all_models.py`:

```bash
cd backend
alembic revision --autogenerate -m "add retention_policy column to investigations"
alembic upgrade head
```

Always review the auto-generated migration before applying it in production.

---

## Docker Compose (Full Stack)

Start all services:
```bash
docker-compose up -d
```

This starts:
- PostgreSQL 16 on port 5432
- Backend API on port 8000 (when backend service is defined)

Stop all services:
```bash
docker-compose down
```

Destroy volumes (full reset):
```bash
docker-compose down -v
```

---

## Common Issues

**`asyncpg` connection refused**: Ensure PostgreSQL is running with `docker-compose ps`.

**`FERNET_KEY` warning on startup**: Generate a persistent key with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Add it to `.env` as `FERNET_KEY=<generated_key>`.

**`alembic` not found**: Ensure you ran `pip install -e ".[dev]"` in the `backend/` directory.

**Tests fail with `aiosqlite` import error**: Install the dev dependencies: `pip install -e ".[dev]"`.
