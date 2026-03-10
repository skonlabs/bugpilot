export interface DocPage {
  slug: string;
  title: string;
  category: string;
  content: string;
}

export const docsCategories = [
  { label: "Getting Started", items: ["introduction", "getting-started"] },
  { label: "Investigating Incidents", items: ["how-to-investigate", "webhooks", "connectors"] },
  { label: "Configuration", items: ["llm-providers"] },
  { label: "Administration", items: ["rbac", "data-retention"] },
  { label: "Reference", items: ["cli-reference", "api-reference", "architecture"] },
  { label: "Self-Hosting", items: ["deployment", "developer-setup"] },
  { label: "Support", items: ["troubleshooting"] },
];

export const docsPages: Record<string, DocPage> = {
  introduction: {
    slug: "introduction",
    title: "Introduction",
    category: "Getting Started",
    content: `# BugPilot Documentation

BugPilot is a CLI-first debugging and investigation platform. It connects to your existing monitoring tools, collects evidence automatically, and uses a multi-pass engine (rule-based + graph correlation + AI synthesis) to generate ranked, actionable root cause hypotheses.

---

## Getting Started

| Guide | Description |
|-------|-------------|
| [Getting Started](/docs/getting-started) | Install, configure, and run your first investigation in 5 minutes |
| [Developer Setup](/docs/developer-setup) | Full local dev environment setup for contributors |
| [Deployment](/docs/deployment) | Docker Compose, Kubernetes, and AWS ECS deployment |

---

## How-To Guides

| Guide | Description |
|-------|-------------|
| [Investigate an Incident](/docs/how-to-investigate) | End-to-end walkthrough: alert → evidence → hypotheses → fix → close |
| [Configure Connectors](/docs/connectors) | Datadog, Grafana, CloudWatch, GitHub, Kubernetes, PagerDuty |
| [Configure Webhooks](/docs/webhooks) | Auto-triage from Datadog, Grafana, CloudWatch, PagerDuty alerts |
| [Configure LLM Providers](/docs/llm-providers) | OpenAI, Anthropic, Azure OpenAI, Ollama |
| [Manage Users and Roles](/docs/rbac) | RBAC roles, approval workflow, audit log |
| [Configure Data Retention](/docs/data-retention) | Retention phases, compliance configurations |

---

## Reference

| Reference | Description |
|-----------|-------------|
| [CLI Reference](/docs/cli-reference) | Complete documentation for every CLI command |
| [API Reference](/docs/api-reference) | REST API endpoints, request/response schemas |
| [Architecture](/docs/architecture) | System design, data flow, and key decisions |

---

## Support

| Resource | Link |
|----------|------|
| Issues | https://github.com/skonlabs/bugpilot/issues |
| API Docs (local) | http://localhost:8000/docs |
| Troubleshooting | [Troubleshooting Guide](/docs/troubleshooting) |

---

## Platform at a Glance

\`\`\`
Symptom → [Evidence Collection] → [Investigation Graph] → [Hypothesis Engine] → [Safe Actions]
               │                                                    │
               ▼                                                    ▼
    6 connectors, concurrent            Rule-based + Graph correlation + LLM synthesis
    45s timeout, graceful degradation   Dedup, rank, single-lane detection
\`\`\`

**Tech stack:** Python 3.11, FastAPI, PostgreSQL 14, asyncpg, SQLAlchemy 2, Alembic, Pydantic v2, structlog, Prometheus, typer, Rich.`,
  },
  "getting-started": {
    slug: "getting-started",
    title: "Getting Started",
    category: "Getting Started",
    content: `# Getting Started with BugPilot

BugPilot is a CLI-first debugging and investigation platform. In under five minutes you can connect BugPilot to your observability stack, activate a license, and start an investigation that automatically gathers correlated evidence from every connected tool — turning a vague symptom into ranked, actionable hypotheses.

---

## Prerequisites

| Requirement | Minimum version |
|-------------|----------------|
| Python      | 3.11 |
| PostgreSQL  | 14 |
| Docker + Compose | any recent |
| pip         | 23+ |

You will also need credentials for at least one connector (Datadog, Grafana, CloudWatch, GitHub, Kubernetes, or PagerDuty). BugPilot works with one connector, but produces the best hypotheses when evidence comes from multiple sources.

---

## Quick Start (Docker Compose)

The fastest way to run BugPilot locally is with Docker Compose.

\`\`\`bash
# 1. Clone the repository
git clone https://github.com/skonlabs/bugpilot.git
cd bugpilot

# 2. Copy and edit environment variables
cp backend/.env.example backend/.env
$EDITOR backend/.env          # set FERNET_KEY, JWT_SECRET at minimum

# 3. Start PostgreSQL + API
docker compose up -d

# 4. Apply database migrations
docker compose exec backend alembic upgrade head

# 5. Install the CLI
pip install -e ./cli

# 6. Verify the API is healthy
curl http://localhost:8000/health
# {"status":"ok"}

# 7. Activate your license
bugpilot auth activate --license-key bp_YOUR_KEY_HERE
\`\`\`

After \`activate\` you will see:

\`\`\`
✓ License activated
  Org:        acme-corp
  Tier:       pro
  Seats:      10 / 10 available
  Expires:    2027-01-15
  Device ID:  dev_a3f8c...
\`\`\`

You are now authenticated. The CLI stores credentials at \`~/.config/bugpilot/credentials.json\` (mode 600).

---

## Manual Installation (without Docker)

### 1. Database

\`\`\`bash
createdb bugpilot
\`\`\`

### 2. Backend

\`\`\`bash
cd backend
pip install -e .
pip install -e ".[dev]"   # include test dependencies

# Set required environment variables
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/bugpilot"
export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export FERNET_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

alembic upgrade head
uvicorn app.main:app --reload --port 8000
\`\`\`

### 3. CLI

\`\`\`bash
cd cli
pip install -e .
bugpilot --version
\`\`\`

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| \`DATABASE_URL\` | Yes | — | PostgreSQL DSN (\`postgresql+asyncpg://...\`) |
| \`JWT_SECRET\` | Yes | — | 32+ byte hex secret for JWT signing |
| \`FERNET_KEY\` | Yes | — | Fernet key for encrypting connector credentials |
| \`BUGPILOT_API_URL\` | CLI only | \`http://localhost:8000\` | Backend URL the CLI connects to |
| \`LOG_LEVEL\` | No | \`info\` | \`debug\` / \`info\` / \`warning\` / \`error\` |
| \`EVIDENCE_TTL_MINUTES\` | No | \`10080\` (7 days) | Default evidence raw-payload TTL |
| \`LLM_PROVIDER\` | No | — | \`openai\` / \`anthropic\` / \`azure_openai\` / \`ollama\` |
| \`OPENAI_API_KEY\` | If using OpenAI | — | OpenAI API key |
| \`ANTHROPIC_API_KEY\` | If using Anthropic | — | Anthropic API key |
| \`AZURE_OPENAI_ENDPOINT\` | If using Azure | — | Azure OpenAI resource endpoint |
| \`AZURE_OPENAI_API_KEY\` | If using Azure | — | Azure OpenAI API key |
| \`AZURE_OPENAI_DEPLOYMENT\` | If using Azure | — | Deployment name |
| \`OLLAMA_BASE_URL\` | If using Ollama | \`http://localhost:11434\` | Ollama server URL |

---

## Your First Investigation

\`\`\`bash
# Start a new investigation
bugpilot investigate create \\
  --title "High error rate on payment-service" \\
  --service payment-service

# BugPilot prints:
# ✓ Investigation created: inv_7f3a2b...
#   Title:    High error rate on payment-service
#   Service:  payment-service
#   Status:   open
#   Branch:   main

# Collect evidence from all configured connectors
bugpilot evidence collect inv_7f3a2b --since 2h

# View generated hypotheses
bugpilot hypotheses list inv_7f3a2b

# Get the top hypothesis and suggested fixes
bugpilot fix suggest inv_7f3a2b hyp_c9e1...

# Run a safe dry-run of the recommended action
bugpilot fix run act_d2f4... --dry-run
\`\`\`

---

## Next Steps

- [CLI Reference](/docs/cli-reference) — complete command documentation
- [Connector Setup](/docs/connectors) — configure Datadog, Grafana, CloudWatch, etc.
- [Architecture Overview](/docs/architecture) — how evidence, graphs, and hypotheses work
- [API Reference](/docs/api-reference) — REST API for programmatic use
- [Deployment Guide](/docs/deployment) — production deployment on Kubernetes / ECS`,
  },
  "developer-setup": {
    slug: "developer-setup",
    title: "Developer Setup",
    category: "Getting Started",
    content: `# Developer Setup Guide

This guide covers setting up a full local development environment for contributing to BugPilot.

---

## Repository Structure

\`\`\`
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
\`\`\`

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or Docker)
- Git

---

## Setup

### 1. Clone the repository

\`\`\`bash
git clone https://github.com/skonlabs/bugpilot.git
cd bugpilot
\`\`\`

### 2. Backend

\`\`\`bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate

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
\`\`\`

### 3. CLI

\`\`\`bash
cd cli
pip install -e .

# Point at local backend
export BUGPILOT_API_URL=http://localhost:8000
\`\`\`

---

## Running Tests

Tests use an in-memory SQLite database — no running PostgreSQL needed.

\`\`\`bash
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
\`\`\`

### Test database

The test suite uses \`sqlite+aiosqlite:///:memory:\` configured in \`tests/conftest.py\`. A cross-dialect \`JSONB\` TypeDecorator in \`app/models/all_models.py\` ensures models work with both PostgreSQL (production) and SQLite (tests).

### Writing tests

Follow the patterns in \`tests/test_hypothesis.py\` and \`tests/test_dedup.py\`:

\`\`\`python
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
\`\`\`

For tests that need the database, use the \`db_session\` fixture from \`conftest.py\`:

\`\`\`python
@pytest.mark.asyncio
async def test_db_feature(db_session):
    from app.models.all_models import Investigation, InvestigationStatus
    inv = Investigation(title="test", status=InvestigationStatus.open, ...)
    db_session.add(inv)
    await db_session.flush()
    assert inv.id is not None
\`\`\`

---

## Code Style

BugPilot uses standard Python conventions:

- **Type hints** on all function signatures
- **Async/await** throughout (no sync blocking calls in API handlers or connectors)
- **structlog** for all logging (never \`print()\`)
- **Pydantic v2** with \`ConfigDict\` (not class-based \`Config\`)
- **SQLAlchemy 2.0** declarative style with \`Mapped\` / \`mapped_column\`

---

## Adding a New API Endpoint

1. Add a route handler to the appropriate file in \`app/api/v1/\`
2. Add request/response Pydantic schemas to \`app/schemas/base.py\`
3. Mount the router in \`app/main.py\` if it's a new file
4. Write tests in \`backend/tests/\`

\`\`\`python
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
\`\`\`

---

## Adding a New Connector

1. Create a directory: \`app/connectors/myplatform/\`
2. Create \`__init__.py\` and \`connector.py\`
3. Subclass \`BaseConnector\` from \`app.connectors.base\`
4. Add a value to the \`ConnectorType\` enum in \`app/models/all_models.py\`
5. Register the connector in the admin connector factory
6. Add sample credentials to \`fixtures/sample_configs/sample_connector_config.yaml\`
7. Write tests in \`backend/tests/test_connectors.py\`

---

## Database Migrations

When you modify \`app/models/all_models.py\`, generate a new Alembic migration:

\`\`\`bash
cd backend

# Auto-generate based on model diff
alembic revision --autogenerate -m "add_my_new_column"

# Review the generated file in migrations/versions/
# Always check autogenerated migrations before applying

# Apply
alembic upgrade head

# Rollback one step
alembic downgrade -1
\`\`\`

---

## Debugging Tips

### View SQL queries

\`\`\`bash
# In .env
LOG_LEVEL=debug

# Or set SQLAlchemy echo
# In app/core/db.py, change:
engine = create_async_engine(settings.database_url, echo=True)
\`\`\`

### Test a specific connector locally

\`\`\`python
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
\`\`\`

### Inspect the hypothesis engine

\`\`\`python
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
\`\`\`

---

## Common Issues

### \`FERNET_KEY\` is not valid

Generate a proper key:

\`\`\`python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
\`\`\`

### \`asyncpg\` SSL error

Add \`?ssl=disable\` for local development:

\`\`\`
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/bugpilot_dev?ssl=disable
\`\`\`

### SQLite JSONB error in tests

Ensure the \`JSONB\` TypeDecorator is imported from \`app.models.all_models\`, not from \`sqlalchemy.dialects.postgresql\` directly. The TypeDecorator routes to \`JSON\` on SQLite automatically.

### \`aiosqlite\` not found

\`\`\`bash
pip install aiosqlite
\`\`\`

---

## Pull Request Guidelines

1. Run the full test suite before submitting: \`pytest\`
2. Add tests for any new feature or bug fix
3. Keep changes focused — one feature or fix per PR
4. Update the relevant doc file if your change affects user-facing behaviour
5. Ensure no Pydantic deprecation warnings (\`class Config\` → \`model_config = ConfigDict(...)\`)`,
  },
  deployment: {
    slug: "deployment",
    title: "Deployment",
    category: "Getting Started",
    content: `# Deployment Guide

This guide covers production deployment of BugPilot. The architecture is stateless (API) + stateful (PostgreSQL), making it straightforward to run on any container platform.

---

## Docker Compose (Single-host / Staging)

The included \`docker-compose.yml\` is suitable for a single-host staging deployment.

\`\`\`bash
# 1. Clone and configure
git clone https://github.com/skonlabs/bugpilot.git
cd bugpilot
cp backend/.env.example backend/.env

# 2. Edit required secrets
$EDITOR backend/.env

# 3. Start services
docker compose up -d

# 4. Apply migrations
docker compose exec backend alembic upgrade head

# 5. Tail logs
docker compose logs -f backend
\`\`\`

### Generating required secrets

\`\`\`bash
# JWT_SECRET (32+ byte hex)
python3 -c 'import secrets; print(secrets.token_hex(32))'

# FERNET_KEY
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
\`\`\`

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| \`DATABASE_URL\` | Yes | \`postgresql+asyncpg://user:pass@host/db\` |
| \`JWT_SECRET\` | Yes | 64-char hex string for JWT signing |
| \`FERNET_KEY\` | Yes | Fernet key for credential encryption |
| \`LOG_LEVEL\` | No | \`debug\` / \`info\` / \`warning\` / \`error\` |
| \`EVIDENCE_TTL_MINUTES\` | No | Raw payload TTL (default: 10080 = 7 days) |
| \`LLM_PROVIDER\` | No | \`openai\` / \`anthropic\` / \`azure_openai\` / \`ollama\` |
| \`OPENAI_API_KEY\` | If using OpenAI | OpenAI API key |
| \`ANTHROPIC_API_KEY\` | If using Anthropic | Anthropic API key |
| \`AZURE_OPENAI_ENDPOINT\` | If using Azure | Azure resource endpoint |
| \`AZURE_OPENAI_API_KEY\` | If using Azure | Azure API key |
| \`AZURE_OPENAI_DEPLOYMENT\` | If using Azure | Deployment name |
| \`OLLAMA_BASE_URL\` | If using Ollama | Default: \`http://localhost:11434\` |

---

## Kubernetes

### Namespace and secrets

\`\`\`bash
kubectl create namespace bugpilot

kubectl create secret generic bugpilot-secrets \\
  --namespace bugpilot \\
  --from-literal=DATABASE_URL="postgresql+asyncpg://bugpilot:$DB_PASS@postgres:5432/bugpilot" \\
  --from-literal=JWT_SECRET="$JWT_SECRET" \\
  --from-literal=FERNET_KEY="$FERNET_KEY" \\
  --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY"
\`\`\`

### Deployment manifest

\`\`\`yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bugpilot-api
  namespace: bugpilot
spec:
  replicas: 2
  selector:
    matchLabels:
      app: bugpilot-api
  template:
    metadata:
      labels:
        app: bugpilot-api
    spec:
      containers:
      - name: api
        image: your-registry/bugpilot-backend:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: bugpilot-secrets
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "1000m"
            memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: bugpilot-api
  namespace: bugpilot
spec:
  selector:
    app: bugpilot-api
  ports:
  - port: 80
    targetPort: 8000
\`\`\`

### Running migrations as a Job

\`\`\`yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: bugpilot-migrate
  namespace: bugpilot
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
      - name: migrate
        image: your-registry/bugpilot-backend:latest
        command: ["alembic", "upgrade", "head"]
        envFrom:
        - secretRef:
            name: bugpilot-secrets
\`\`\`

---

## AWS ECS (Fargate)

### Task definition highlights

\`\`\`json
{
  "family": "bugpilot-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "your-registry/bugpilot-backend:latest",
      "portMappings": [{"containerPort": 8000}],
      "secrets": [
        {"name": "DATABASE_URL",  "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/DATABASE_URL"},
        {"name": "JWT_SECRET",    "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/JWT_SECRET"},
        {"name": "FERNET_KEY",    "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/FERNET_KEY"}
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 30
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/bugpilot",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "api"
        }
      }
    }
  ]
}
\`\`\`

---

## Database: PostgreSQL

### Recommended settings

\`\`\`sql
-- Increase max connections for asyncpg pool
ALTER SYSTEM SET max_connections = 200;

-- Enable pg_stat_statements for query monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Recommended indexes (all created by migration 0001)
-- investigations(org_id, status)
-- evidence_items(investigation_id)
-- evidence_items(fetched_at)  -- for retention purge
-- audit_logs(org_id, occurred_at)
\`\`\`

### Managed database options

| Platform | Service |
|----------|---------|
| AWS | RDS PostgreSQL 14+ or Aurora PostgreSQL |
| GCP | Cloud SQL for PostgreSQL |
| Azure | Azure Database for PostgreSQL |
| Self-hosted | PostgreSQL 14+ with asyncpg-compatible SSL |

Ensure \`asyncpg\` SSL mode is set correctly:

\`\`\`
postgresql+asyncpg://user:pass@host/db?ssl=require
\`\`\`

---

## Retention Purge Job

BugPilot's retention service must be called on a schedule. Add a cron job or scheduled task:

\`\`\`bash
# Kubernetes CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bugpilot-retention
  namespace: bugpilot
spec:
  schedule: "0 2 * * *"   # 02:00 UTC daily
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: retention
            image: your-registry/bugpilot-backend:latest
            command: ["python3", "-m", "app.services.retention_service"]
            envFrom:
            - secretRef:
                name: bugpilot-secrets
\`\`\`

---

## Prometheus Scraping

Add BugPilot to your \`prometheus.yml\`:

\`\`\`yaml
scrape_configs:
  - job_name: bugpilot
    static_configs:
      - targets: ['bugpilot-api:8000']
    metrics_path: /metrics
    scrape_interval: 15s
\`\`\`

### Recommended alerts

\`\`\`yaml
groups:
- name: bugpilot
  rules:
  - alert: BugPilotAPIDown
    expr: up{job="bugpilot"} == 0
    for: 2m
    labels:
      severity: critical

  - alert: BugPilotWebhookVerificationFailures
    expr: increase(bugpilot_webhook_verification_failures_total[5m]) > 10
    labels:
      severity: warning
    annotations:
      summary: "High webhook verification failure rate — possible replay attack"

  - alert: BugPilotConnectorErrors
    expr: increase(bugpilot_connector_errors_total[10m]) > 20
    labels:
      severity: warning
    annotations:
      summary: "Connector {{ $labels.connector }} has elevated error rate"
\`\`\`

---

## Security Checklist

Before going to production:

- \`JWT_SECRET\` is at least 32 bytes and stored in a secrets manager (not in \`.env\` files)
- \`FERNET_KEY\` is rotated regularly and stored in a secrets manager
- PostgreSQL is not publicly accessible — use a private subnet
- TLS is terminated at the load balancer (SSL certificate on ALB/nginx/ingress)
- Webhook secrets are rotated using the dual-secret grace window feature
- Log output (\`/metrics\`, \`/health\`) is not exposed publicly
- Database credentials use a least-privilege role (SELECT, INSERT, UPDATE, DELETE — no DDL)
- \`LOG_LEVEL=info\` in production (not \`debug\`, which may log request bodies)
- Org isolation tested — no cross-tenant queries possible through the API`,
  },
  "how-to-investigate": {
    slug: "how-to-investigate",
    title: "Investigate an Incident",
    category: "Investigating Incidents",
    content: `# How to Investigate an Incident with BugPilot

This guide walks through a realistic incident scenario from alert to resolution using BugPilot.

---

## Scenario

At 14:31 UTC your monitoring fires: **payment-service HTTP 5xx rate > 5%**. The on-call engineer opens a terminal.

---

## Step 1 — Authenticate

If this is your first time on this machine:

\`\`\`bash
bugpilot auth activate --license-key bp_YOUR_LICENSE_KEY
\`\`\`

Check who you're logged in as:

\`\`\`bash
bugpilot auth whoami
\`\`\`

\`\`\`
  User:  alice@acme.com
  Role:  investigator
  Org:   acme-corp
\`\`\`

---

## Step 2 — Triage (recommended: let BugPilot handle it)

The \`incident triage\` command does the most in one step: deduplication check, investigation creation, evidence collection, and initial hypothesis generation.

\`\`\`bash
bugpilot incident triage \\
  --service payment-service \\
  --alert-name "HTTP 5xx rate > 5%" \\
  --severity critical \\
  --since 2h
\`\`\`

\`\`\`
  ⚡ Dedup check: No similar open investigations found
  ✓ Investigation created: inv_7f3a2b
  ↓ Collecting evidence (5 connectors)...
    ✓ datadog/logs         47 items   0.34s
    ✓ datadog/metrics      12 items   0.41s
    ✓ datadog/alerts        3 items   0.28s
    ✗ grafana/metrics       —         degraded: timeout after 45s
    ✓ github/deployments    2 items   0.19s
  ✓ Hypotheses generated (3)

  TOP HYPOTHESIS
  ──────────────────────────────────────────────────────────────
  Rank 1  │  Bad Deployment Introduced Regression          ▓▓▓▓▓▓▓▒ 72%
          │  Deployment a3f8c2d at 14:23 UTC correlates with the
          │  onset of 5xx errors. Commit message: "Update Stripe
          │  SDK to v4". Affected evidence: 12 items.
  ──────────────────────────────────────────────────────────────

  Investigation ID: inv_7f3a2b
  Run: bugpilot hypotheses list inv_7f3a2b   for all hypotheses
  Run: bugpilot fix suggest inv_7f3a2b       for remediation options
\`\`\`

:::info
BugPilot detected that Grafana timed out but continued with the other 4 connectors. It notes the degraded source and still produced useful hypotheses from logs + metrics + deployment data.
:::

---

## Step 3 — Review All Hypotheses

\`\`\`bash
bugpilot hypotheses list inv_7f3a2b
\`\`\`

\`\`\`
  RANK  HYPOTHESIS                              CONFIDENCE  STATUS  SOURCE
  ────  ──────────────────────────────────────  ──────────  ──────  ──────
  1     Bad Deployment Introduced Regression    72%         active  rule
  2     Memory Exhaustion                       58%         active  rule
  3     Upstream Dependency Degradation         41%         active  graph

  3 hypotheses  │  Evidence from 3 capabilities (LOGS, METRICS, DEPLOYMENTS)
\`\`\`

Each hypothesis shows:
- **Confidence score** — derived from evidence strength and correlation
- **Source** — \`rule\` (pattern matching), \`graph\` (graph analysis), or \`llm\` (AI synthesis)

---

## Step 4 — Investigate a Hypothesis

Check the evidence linked to the top hypothesis:

\`\`\`bash
bugpilot evidence list inv_7f3a2b --capability deployments
\`\`\`

\`\`\`
  ID           SOURCE         CAPABILITY    SUMMARY                          RELIABILITY
  ev_d1e2f3   github         DEPLOYMENTS   Merge commit a3f8c2d: "Update     0.98
                                           Stripe SDK to v4" by alice, 14:23
  ev_a4b5c6   datadog        DEPLOYMENTS   Deployment: payment-service →      0.95
                                           v2.14.0, duration: 3m12s, 14:23
\`\`\`

Timeline view to see the sequence of events:

\`\`\`bash
bugpilot investigate get inv_7f3a2b
\`\`\`

\`\`\`
  TIMELINE
  ─────────────────────────────────────────────────────────────
  14:23:00  DEPLOYMENT    Deploy a3f8c2d — payment-service v2.14.0
  14:31:12  SYMPTOM       HTTP 5xx rate spike — 7.2% error rate
  14:31:45  ALERT         PagerDuty: P1 incident created
  14:33:00  SYMPTOM       Latency p99 increased to 8.2s
  ─────────────────────────────────────────────────────────────
\`\`\`

The 8-minute gap between deployment and error onset strongly suggests the deployment is the cause.

---

## Step 5 — Reject Unlikely Hypotheses

After reviewing the evidence, hypothesis #2 (Memory Exhaustion) looks unlikely — memory metrics are stable.

\`\`\`bash
bugpilot hypotheses reject hyp_mem456 \\
  --reason "Memory metrics stable at 62% usage throughout the incident window"
\`\`\`

---

## Step 6 — Get Remediation Options

\`\`\`bash
bugpilot fix suggest inv_7f3a2b
\`\`\`

\`\`\`
  SUGGESTED ACTIONS

  #1  Rollback deployment a3f8c2d                                  RISK: low
      Rationale:   Deployment correlates with 5xx onset at 14:31
      Effect:      Restore payment-service to v2.13.0 (stable 3 days)
      Rollback:    git revert a3f8c2d && trigger CI/CD pipeline
      Approval:    Not required

  #2  Disable Stripe SDK v4 feature flag                          RISK: low
      Rationale:   New SDK may have breaking API changes
      Effect:      Bypass v4 code path without a full rollback
      Rollback:    Re-enable feature flag
      Approval:    Not required

  #3  Increase memory limit to 1Gi                                RISK: medium
      Rationale:   Memory headroom of 38% — guard against spikes
      Effect:      Prevent potential OOMKill under load
      Rollback:    Revert resource quota change
      Approval:    Required (approver role)
\`\`\`

---

## Step 7 — Dry Run a Safe Action

Always dry-run before executing:

\`\`\`bash
bugpilot fix run act_rollback123 --dry-run
\`\`\`

\`\`\`
  DRY RUN: Rollback deployment a3f8c2d
  ─────────────────────────────────────────────────────────────
  Would execute:
    1. Trigger rollback pipeline for payment-service
    2. Set image: payment-service → v2.13.0
    3. Wait for rollout (estimated: 2-3 minutes)

  Estimated downtime:    0s  (rolling update strategy)
  Previous version age:  3 days (stable, no incidents)
  Risk assessment:       LOW

  To execute: bugpilot fix run act_rollback123
\`\`\`

---

## Step 8 — Execute the Action

\`\`\`bash
bugpilot fix run act_rollback123
\`\`\`

\`\`\`
  ✓ Action executed: Rollback deployment a3f8c2d
    Status:   completed
    Output:   Rolling update complete. 3/3 pods ready.
    Duration: 2m41s
\`\`\`

---

## Step 9 — Confirm the Root Cause and Close

Once the 5xx rate drops back to baseline, confirm the hypothesis and close the investigation.

\`\`\`bash
# Confirm the root cause
bugpilot hypotheses confirm hyp_deploy789

# Close the investigation with root cause summary
bugpilot investigate close inv_7f3a2b \\
  --root-cause "Stripe SDK v4 introduced a breaking change in the charge() API. Rolled back to v2.13.0. SDK upgrade to be re-attempted with proper integration tests."
\`\`\`

\`\`\`
  ✓ Investigation closed
    Duration:     47 minutes
    Root cause:   Stripe SDK v4 introduced a breaking change...
    Actions:      1 executed (rollback a3f8c2d)
    Evidence:     65 items from 4 sources
\`\`\`

---

## Step 10 — Export the Incident Report

\`\`\`bash
bugpilot export markdown inv_7f3a2b --output-file incident-report.md
\`\`\`

The generated Markdown report includes: timeline, root cause, evidence summary, actions taken (with approvals), and outcome. Ready to paste into Confluence, Notion, or a GitHub issue.

---

## Tips and Patterns

### Parallel hypothesis testing

Use branches to test multiple hypotheses in parallel without polluting the main investigation:

\`\`\`bash
# Create a branch to test the memory hypothesis separately
bugpilot investigate update inv_7f3a2b --create-branch memory-investigation
\`\`\`

### Multi-service incidents

When multiple services are affected, add them to the investigation:

\`\`\`bash
bugpilot investigate update inv_7f3a2b \\
  --service checkout-service \\
  --service stripe-gateway
\`\`\`

BugPilot will collect evidence for all linked services and look for cross-service causal chains.

### Automating triage from CI/CD

\`\`\`bash
# Trigger triage automatically after a failed deployment
if [ "$DEPLOY_STATUS" = "failed" ]; then
  bugpilot incident triage \\
    --service "$SERVICE_NAME" \\
    --alert-name "Deployment smoke test failed: $BUILD_ID" \\
    --severity high \\
    --since 15m \\
    --output json > /tmp/triage.json

  # Print top hypothesis to CI logs
  cat /tmp/triage.json | python3 -c "
  import json,sys
  r = json.load(sys.stdin)
  h = r.get('top_hypothesis')
  if h:
      print(f'Top hypothesis: {h[\"title\"]} ({h[\"confidence_score\"]*100:.0f}% confidence)')
  "
fi
\`\`\`

### When evidence is thin (single-lane warning)

If you see \`⚠ Evidence from single source only\` — this means only one connector provided data. Confidence scores are capped at 40%.

To improve hypothesis quality:
1. Check that other connectors are properly configured: \`bugpilot auth whoami\`
2. Validate connector health: \`curl /api/v1/admin/connectors/validate\`
3. Re-collect with explicit capabilities: \`bugpilot evidence collect inv_7f3a2b --since 2h\``,
  },
  connectors: {
    slug: "connectors",
    title: "Connector Setup",
    category: "Investigating Incidents",
    content: `# Connector Setup Guide

BugPilot collects evidence from your existing observability tools through **connectors**. Each connector maps to a real-world monitoring platform and exposes one or more **capabilities** (logs, metrics, traces, alerts, incidents, deployments, infrastructure state, or code changes).

The more connectors you configure, the better BugPilot's hypotheses will be. A single-source investigation is marked as a **single-lane investigation** and confidence scores are automatically capped at 40% — prompting you to add more evidence sources.

---

## Overview

| Connector | Capabilities | Auth method |
|-----------|-------------|-------------|
| Datadog | Logs, Metrics, Traces, Alerts | API key + App key |
| Grafana | Metrics, Alerts | API token |
| AWS CloudWatch | Logs, Metrics, Alerts | Access key + Secret key |
| GitHub | Code changes, Deployments | Personal access token |
| Kubernetes | Infrastructure state, Deployments | Bearer token |
| PagerDuty | Incidents, Alerts | REST API key |

---

## Configuring Connectors via the Admin API

\`\`\`bash
# Configure a Datadog connector
curl -X POST http://localhost:8000/api/v1/admin/connectors \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "connector_type": "datadog",
    "env_label": "production",
    "credentials": {
      "api_key": "YOUR_DATADOG_API_KEY",
      "app_key": "YOUR_DATADOG_APP_KEY",
      "base_url": "https://api.datadoghq.com"
    }
  }'
\`\`\`

Credentials are encrypted at rest using Fernet symmetric encryption before being stored in the database. The plaintext key is never persisted.

---

## Datadog

### Required credentials

| Field | Description |
|-------|-------------|
| \`api_key\` | Datadog API key (read-only is sufficient) |
| \`app_key\` | Datadog Application key |
| \`base_url\` | US: \`https://api.datadoghq.com\` · EU: \`https://api.datadoghq.eu\` |
| \`service_tag\` | (Optional) Default Datadog service tag filter |

### Capabilities

| Capability | API endpoint used |
|-----------|-------------------|
| \`LOGS\` | \`POST /api/v2/logs/events/search\` with \`service:NAME\` filter |
| \`METRICS\` | \`GET /api/v1/query\` — CPU user, request rate |
| \`TRACES\` | \`GET /api/v2/spans/events\` for the service |
| \`ALERTS\` | \`GET /api/v1/monitor\` filtered by service tag |

### Minimum Datadog permissions

- \`logs_read_data\`
- \`metrics_read\`
- \`apm_read\`
- \`monitors_read\`

---

## Grafana

### Required credentials

| Field | Description |
|-------|-------------|
| \`base_url\` | Grafana instance URL (e.g. \`https://grafana.example.com\`) |
| \`api_token\` | Service account token (Viewer role) |
| \`datasource_uid\` | (Optional) Prometheus datasource UID; auto-discovered if omitted |

### Capabilities

| Capability | API endpoint used |
|-----------|-------------------|
| \`METRICS\` | \`/api/datasources/proxy/:uid/api/v1/query_range\` |
| \`ALERTS\` | \`/api/v1/provisioning/alert-rules\` |

### Setup

1. Grafana → Administration → Service accounts → Create service account (Viewer role).
2. Generate a service account token.
3. Copy your Prometheus datasource UID from Administration → Data sources.

---

## AWS CloudWatch

### Required credentials

| Field | Description |
|-------|-------------|
| \`access_key_id\` | AWS access key ID |
| \`secret_access_key\` | AWS secret access key |
| \`region\` | AWS region (e.g. \`us-east-1\`) |
| \`log_group_prefix\` | (Optional) CloudWatch log group name or prefix |

### Capabilities

| Capability | AWS API used |
|-----------|--------------|
| \`LOGS\` | \`StartQuery\` + \`GetQueryResults\` (CloudWatch Insights) |
| \`METRICS\` | \`GetMetricData\` (CPUUtilization, RequestCount) |
| \`ALERTS\` | \`DescribeAlarms\` (state=ALARM) |

### Minimum IAM permissions

\`\`\`json
{
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "logs:StartQuery",
      "logs:GetQueryResults",
      "cloudwatch:GetMetricData",
      "cloudwatch:DescribeAlarms"
    ],
    "Resource": "*"
  }]
}
\`\`\`

:::info
BugPilot uses manual SigV4 signing (no boto3) to keep the image minimal. For production, prefer an IAM role on your EC2/ECS instance.
:::

---

## GitHub

### Required credentials

| Field | Description |
|-------|-------------|
| \`token\` | Personal access token or GitHub App installation token |
| \`owner\` | GitHub organisation or username |
| \`repo\` | Default repository name |

### Capabilities

| Capability | API endpoint used |
|-----------|-------------------|
| \`CODE_CHANGES\` | \`GET /repos/{owner}/{repo}/commits\` with since/until |
| \`DEPLOYMENTS\` | \`GET /repos/{owner}/{repo}/deployments\` |

### Minimum token scopes

- \`repo:status\` (read commit statuses)
- \`read:repo_hook\` (optional, deployment events)

:::info
Pass \`owner/repo\` as the service name in \`investigate create\` to target a specific repository.
:::

---

## Kubernetes

### Required credentials

| Field | Description |
|-------|-------------|
| \`base_url\` | API server URL (e.g. \`https://k8s.example.com:6443\`) |
| \`token\` | Service account bearer token |
| \`namespace\` | Namespace to query (default: \`default\`) |
| \`ca_cert_pem\` | (Optional) PEM CA cert for TLS verification |
| \`verify_ssl\` | \`false\` to skip TLS (not recommended in production) |

### Capabilities

| Capability | Kubernetes resources |
|-----------|---------------------|
| \`INFRASTRUCTURE_STATE\` | Pods, Nodes, Events (namespaced) |
| \`DEPLOYMENTS\` | \`apps/v1\` Deployments matching service label |

### Creating a read-only service account

\`\`\`bash
kubectl create serviceaccount bugpilot-reader -n default

kubectl create clusterrole bugpilot-reader \\
  --verb=get,list \\
  --resource=pods,nodes,events,deployments

kubectl create clusterrolebinding bugpilot-reader \\
  --clusterrole=bugpilot-reader \\
  --serviceaccount=default:bugpilot-reader

# Get a long-lived token
kubectl create token bugpilot-reader -n default --duration=8760h
\`\`\`

---

## PagerDuty

### Required credentials

| Field | Description |
|-------|-------------|
| \`api_key\` | PagerDuty REST API key (read-only) |
| \`service_id\` | (Optional) Filter incidents to one service |

### Capabilities

| Capability | API endpoint used |
|-----------|-------------------|
| \`INCIDENTS\` | \`GET /incidents\` filtered by service and date range |
| \`ALERTS\` | \`GET /incidents/{id}/alerts\` for each matching incident |

---

## Retry and Timeout Behaviour

All connectors share a consistent policy:

| Setting | Value |
|---------|-------|
| Request timeout | 30 seconds |
| Collection timeout (per connector) | 45 seconds |
| Retry on | 429, 500, 502, 503, 504 |
| Max attempts | 3 |
| Backoff strategy | Exponential with jitter |
| Retry-After header | Respected |

If a connector exceeds the collection timeout or exhausts retries, it is marked **degraded**. The investigation continues with data from other connectors. Degraded connectors are listed in evidence output:

\`\`\`
  grafana/metrics   —   degraded: connection timeout after 45s
\`\`\`

---

## Validating Connector Connectivity

\`\`\`bash
curl http://localhost:8000/api/v1/admin/connectors/validate \\
  -H "Authorization: Bearer $TOKEN"

# [
#   {"connector_id":"c1d9...","type":"datadog","valid":true,"latency_ms":210},
#   {"connector_id":"a2f8...","type":"grafana","valid":false,"error":"401 Unauthorized"}
# ]
\`\`\`

---

## Adding a Custom Connector

Subclass \`BaseConnector\` from \`app.connectors.base\`:

\`\`\`python
from app.connectors.base import (
    BaseConnector, ConnectorCapability, RawEvidenceItem, ValidationResult
)
from datetime import datetime

class MyConnector(BaseConnector):
    def __init__(self, config: dict):
        self.base_url = config["base_url"]
        self.api_key  = config["api_key"]

    def capabilities(self) -> list[ConnectorCapability]:
        return [ConnectorCapability.LOGS]

    async def validate(self) -> ValidationResult:
        import httpx
        async with httpx.AsyncClient() as c:
            try:
                r = await c.get(f"{self.base_url}/health",
                                headers={"X-Api-Key": self.api_key}, timeout=5)
                return ValidationResult(
                    is_valid=(r.status_code == 200),
                    latency_ms=r.elapsed.total_seconds() * 1000,
                )
            except Exception as e:
                return ValidationResult(is_valid=False, error=str(e))

    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        # implement per capability
        return []
\`\`\`

Register it in \`ConnectorType\` enum (\`app/models/all_models.py\`) and add factory logic in the connector admin router.`,
  },
  webhooks: {
    slug: "webhooks",
    title: "Configure Webhooks",
    category: "Investigating Incidents",
    content: `# How to Configure Webhooks

BugPilot can receive webhooks from monitoring platforms to automatically create and triage investigations when alerts fire — eliminating the manual step of opening an investigation.

---

## How It Works

\`\`\`
Monitoring platform fires alert
        │
        ▼
POST /api/v1/webhooks/{source}
        │
        ▼
BugPilot verifies HMAC-SHA256 signature
        │
        ├── invalid signature → 401, metric incremented, logged
        │
        ▼
Dedup check: is there already an open investigation?
        │
        ├── duplicate found → attach evidence to existing investigation
        │
        ▼
Create new investigation (if no duplicate)
        │
        ▼
Enqueue evidence collection
\`\`\`

---

## Supported Webhook Sources

| Source | Path | Signature header |
|--------|------|-----------------|
| Datadog | \`/api/v1/webhooks/datadog\` | \`X-Hub-Signature\` (hex HMAC) |
| Grafana | \`/api/v1/webhooks/grafana\` | \`X-Grafana-Signature\` (\`sha256=HMAC\`) |
| AWS CloudWatch (SNS) | \`/api/v1/webhooks/cloudwatch\` | Certificate-based SNS signature |
| PagerDuty | \`/api/v1/webhooks/pagerduty\` | \`X-PagerDuty-Signature\` (\`v1=HMAC\`) |

---

## Registering a Webhook Secret

\`\`\`bash
# Register a new webhook for Datadog
curl -X POST http://localhost:8000/api/v1/admin/webhooks \\
  -H "Authorization: Bearer $ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "source": "datadog",
    "secret": "YOUR_SHARED_SECRET_MIN_32_CHARS",
    "description": "Production Datadog webhook"
  }'

# Returns: { "webhook_id": "wh_abc123", "source": "datadog" }
\`\`\`

---

## Setting Up Each Source

### Datadog

1. In Datadog → Integrations → Webhooks → Add Webhook
2. **URL:** \`https://your-bugpilot.example.com/api/v1/webhooks/datadog?org_id=YOUR_ORG_ID\`
3. **Payload:** Default (or custom JSON)
4. **Custom Headers:**
   \`\`\`
   X-Hub-Signature: sha256=\${signature}
   \`\`\`
5. In Datadog, set the Webhook secret to match the one you registered with BugPilot

**Sample payload sent by Datadog:**

\`\`\`json
{
  "title": "High 5xx error rate on payment-service",
  "alert_id": "1234567",
  "severity": "critical",
  "tags": ["service:payment-service", "env:production"],
  "date": 1705330271,
  "org": { "id": "abc123", "name": "ACME Corp" }
}
\`\`\`

---

### Grafana

1. In Grafana → Alerting → Contact points → Add contact point
2. **Integration:** Webhook
3. **URL:** \`https://your-bugpilot.example.com/api/v1/webhooks/grafana?org_id=YOUR_ORG_ID\`
4. **Authorization Header:** Leave blank (Grafana uses \`X-Grafana-Signature\`)
5. Under **Settings** → **Webhook secret**, set the same secret registered in BugPilot

**Sample payload:**

\`\`\`json
{
  "alerts": [
    {
      "status": "firing",
      "labels": { "alertname": "HighLatency", "service": "checkout-svc" },
      "annotations": { "summary": "p99 latency > 5s" },
      "startsAt": "2024-01-15T14:31:00Z",
      "fingerprint": "abc123def456"
    }
  ],
  "receiver": "bugpilot",
  "externalURL": "https://grafana.example.com"
}
\`\`\`

The \`fingerprint\` field is used for deduplication.

---

### AWS CloudWatch (via SNS)

1. In AWS → SNS → Create topic → HTTPS subscription
2. **Endpoint:** \`https://your-bugpilot.example.com/api/v1/webhooks/cloudwatch?org_id=YOUR_ORG_ID\`
3. Confirm the SNS subscription (BugPilot auto-confirms \`SubscriptionConfirmation\` messages)
4. Attach the SNS topic to your CloudWatch alarm

BugPilot verifies SNS messages using AWS certificate-based signature validation. The certificate URL must match \`*.amazonaws.com\` to prevent SSRF attacks.

**Sample alarm notification:**

\`\`\`json
{
  "Type": "Notification",
  "MessageId": "abc123",
  "Subject": "ALARM: \\"payment-service-5xx\\" in us-east-1",
  "Message": "{\\"AlarmName\\":\\"payment-service-5xx\\",\\"NewStateValue\\":\\"ALARM\\",\\"NewStateReason\\":\\"Threshold Crossed: 1 out of the last 1 datapoints (7.8%) was greater than the threshold (5.0%)\\"}",
  "Timestamp": "2024-01-15T14:31:00.000Z",
  "Signature": "...",
  "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-..."
}
\`\`\`

---

### PagerDuty

1. In PagerDuty → Service → Webhooks → Add Webhook
2. **Delivery URL:** \`https://your-bugpilot.example.com/api/v1/webhooks/pagerduty?org_id=YOUR_ORG_ID\`
3. **Event types:** \`incident.triggered\`, \`incident.acknowledged\`, \`incident.resolved\`
4. Copy the webhook secret from PagerDuty and register it in BugPilot

PagerDuty sends multiple signatures in a comma-separated header for key rotation. BugPilot accepts any valid signature from the list.

**Sample payload:**

\`\`\`json
{
  "event": {
    "id": "evt_abc",
    "event_type": "incident.triggered",
    "data": {
      "id": "P1ABC12",
      "title": "High 5xx rate - payment-service",
      "urgency": "high",
      "service": { "id": "SVC001", "summary": "payment-service" },
      "created_at": "2024-01-15T14:31:00Z"
    }
  }
}
\`\`\`

---

## Secret Rotation (Zero-downtime)

BugPilot supports a **dual-secret grace window** for rotating webhook secrets without downtime:

\`\`\`bash
# 1. Register the new secret as the "previous" secret on your webhook
curl -X PATCH http://localhost:8000/api/v1/admin/webhooks/wh_abc123 \\
  -H "Authorization: Bearer $ADMIN_TOKEN" \\
  -d '{"secret": "NEW_SECRET", "previous_secret": "OLD_SECRET"}'

# 2. Update the secret in your monitoring platform

# 3. After all platforms are updated, clear the previous secret
curl -X PATCH http://localhost:8000/api/v1/admin/webhooks/wh_abc123 \\
  -H "Authorization: Bearer $ADMIN_TOKEN" \\
  -d '{"previous_secret": null}'
\`\`\`

During the grace window, BugPilot accepts signatures from either the current or previous secret.

---

## Rate Limiting

Webhook endpoints enforce **100 requests per minute per source IP + org combination**. When exceeded, BugPilot returns \`429 Too Many Requests\` and logs the event.

Legitimate monitoring platforms typically send far fewer webhooks than this limit. If you exceed it, consider consolidating multiple alert rules into fewer webhook calls.

---

## Testing Webhooks Locally

Use the sample payloads in \`fixtures/sample_configs/sample_webhook_payloads/\`:

\`\`\`bash
# Test Datadog webhook locally
SIGNATURE=$(echo -n '{"title":"Test Alert"}' | openssl dgst -sha256 -hmac "YOUR_SECRET" | awk '{print $2}')

curl -X POST http://localhost:8000/api/v1/webhooks/datadog?org_id=YOUR_ORG_ID \\
  -H "Content-Type: application/json" \\
  -H "X-Hub-Signature: sha256=$SIGNATURE" \\
  -d @fixtures/sample_configs/sample_webhook_payloads/datadog.json
\`\`\`

---

## Webhook Verification Failures

If a webhook fails signature verification, BugPilot:
1. Returns \`401 Unauthorized\`
2. Increments \`bugpilot_webhook_verification_failures_total{source="datadog"}\` Prometheus counter
3. Logs at \`warning\` level with \`event=webhook_verification_failed\`

Monitor for verification failures to detect misconfigured secrets or potential replay attacks:

\`\`\`yaml
# Prometheus alert
- alert: WebhookVerificationFailures
  expr: increase(bugpilot_webhook_verification_failures_total[5m]) > 10
  labels:
    severity: warning
  annotations:
    summary: "Webhook signature verification failures — check secret configuration"
\`\`\``,
  },
  "llm-providers": {
    slug: "llm-providers",
    title: "LLM Providers",
    category: "Configuration",
    content: `# How to Configure LLM Providers

BugPilot uses LLMs to synthesize additional hypotheses when evidence is complex or when rule-based patterns don't fully explain an incident. LLM usage is **optional** — BugPilot works without one using its rule-based and graph correlation engines.

---

## Overview

When an LLM is configured, BugPilot uses it in the 4th pass of the hypothesis pipeline:

1. Rule-based pass (always runs)
2. Graph correlation pass (always runs)
3. Historical reranking (runs if DB context available)
4. **LLM synthesis** ← only runs if configured and slice is redacted
5. Dedup + rank (always runs)

The LLM is given the redacted investigation graph and asked to suggest hypotheses not already identified by earlier passes. **No raw evidence, no PII, no secrets are ever sent to the LLM.**

---

## Supported Providers

| Provider | Model | Notes |
|----------|-------|-------|
| OpenAI | gpt-4o (default) | Best hypothesis quality |
| Anthropic | claude-sonnet-4-6 (default) | Strong reasoning, supports prompt caching |
| Azure OpenAI | Your deployment | GPT-4 family via your Azure resource |
| Ollama | Any local model | No external API calls; privacy-first |

---

## OpenAI

\`\`\`bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
\`\`\`

Or in \`backend/.env\`:

\`\`\`env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...
\`\`\`

**Supported models:** \`gpt-4o\`, \`gpt-4o-mini\`, \`gpt-4-turbo\`. Default: \`gpt-4o\`.

To change the model, set \`LLM_MODEL=gpt-4o-mini\` in your environment.

---

## Anthropic

\`\`\`env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
\`\`\`

**Supported models:** \`claude-opus-4-6\`, \`claude-sonnet-4-6\`, \`claude-haiku-4-5-20251001\`. Default: \`claude-sonnet-4-6\`.

BugPilot takes advantage of Anthropic's **prompt caching** for repeated investigation context, reducing token costs on follow-up hypothesis refinements.

---

## Azure OpenAI

\`\`\`env
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment
\`\`\`

Azure OpenAI is recommended for organisations with data residency requirements or enterprise agreements.

---

## Ollama (Local / Air-gapped)

For privacy-sensitive environments where data cannot leave your network:

\`\`\`bash
# Install and start Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2

# Configure BugPilot
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export LLM_MODEL=llama3.2
\`\`\`

**Recommended models for hypothesis generation:**
- \`llama3.2\` — Good balance of quality and speed
- \`mixtral\` — Higher quality, higher resource usage
- \`codellama\` — Better for code-related incidents

:::info
Ollama models are typically less capable at complex reasoning than GPT-4o or Claude. Consider using them for lower-severity incidents or as a complement to rule-based hypotheses.
:::

---

## Privacy Guarantee

Regardless of which LLM provider you use, BugPilot enforces a strict privacy boundary in code:

\`\`\`python
# In app/llm/llm_service.py — enforced at runtime, not configuration
if not getattr(slice, 'is_redacted', False):
    raise ValueError(
        "SECURITY: Attempted to send non-redacted GraphSlice to LLM provider."
    )
\`\`\`

Before a \`GraphSlice\` is sent to any LLM, the privacy pipeline:
1. Scrubs emails, phone numbers, JWTs, bearer tokens, payment cards, AWS keys, PEM keys
2. Sets \`is_redacted=True\` on the slice
3. Records a \`RedactionManifest\` with what was removed

The LLM never sees raw log lines, actual error messages with PII, or secrets.

---

## Token Budget and Caching

BugPilot enforces a **token budget** per LLM call to prevent runaway costs:

| Setting | Default |
|---------|---------|
| Max prompt tokens | 8,000 |
| Max completion tokens | 2,000 |
| Max total tokens per investigation | 40,000 |

The LLM service maintains an **in-memory cache** keyed by a SHA-256 hash of the graph content, task description, model name, and prompt version. Identical investigation states return cached results without a new API call.

Cache entries are invalidated when new evidence is added to an investigation via \`invalidate_cache_for_investigation(investigation_id)\`.

---

## LLM Usage Tracking

All LLM calls are logged to the \`llm_usage_logs\` table:

\`\`\`bash
curl http://localhost:8000/api/v1/admin/llm-usage \\
  -H "Authorization: Bearer $ADMIN_TOKEN"

# {
#   "total_requests": 142,
#   "total_tokens": 287450,
#   "total_cost_usd": 8.62,
#   "by_provider": {
#     "openai": {"requests": 142, "tokens": 287450, "cost_usd": 8.62}
#   }
# }
\`\`\`

A Prometheus counter also tracks usage:

\`\`\`
bugpilot_llm_requests_total{provider="openai"} 142
bugpilot_llm_tokens_total{provider="openai",type="prompt"} 245230
bugpilot_llm_tokens_total{provider="openai",type="completion"} 42220
\`\`\`

---

## Disabling LLM (Rule-based only mode)

To run BugPilot entirely without an LLM:

\`\`\`env
# Simply don't set LLM_PROVIDER
# BugPilot will use rule-based + graph correlation only
\`\`\`

Rule-based and graph correlation hypotheses are available instantly without any API calls, latency, or cost.`,
  },
  rbac: {
    slug: "rbac",
    title: "Users & Roles",
    category: "How-To Guides",
    content: `# How to Manage Users and Roles

BugPilot uses role-based access control (RBAC) with four roles. This guide covers role assignments, permissions, and common administration tasks.

---

## Roles

| Role | Description |
|------|-------------|
| \`viewer\` | Read-only access to investigations, evidence, and hypotheses |
| \`investigator\` | Can create and work investigations, collect evidence, run low-risk actions |
| \`approver\` | Inherits investigator + can approve medium/high/critical risk actions |
| \`admin\` | Full access including connector management, user management, org settings |

---

## Permission Matrix

| Permission | viewer | investigator | approver | admin |
|-----------|:------:|:------------:|:--------:|:-----:|
| \`investigations:read\` | ✓ | ✓ | ✓ | ✓ |
| \`investigations:write\` | | ✓ | ✓ | ✓ |
| \`evidence:read\` | ✓ | ✓ | ✓ | ✓ |
| \`evidence:write\` | | ✓ | ✓ | ✓ |
| \`hypotheses:read\` | ✓ | ✓ | ✓ | ✓ |
| \`hypotheses:write\` | | ✓ | ✓ | ✓ |
| \`actions:read\` | ✓ | ✓ | ✓ | ✓ |
| \`actions:write\` | | ✓ | ✓ | ✓ |
| \`actions:approve\` | | | ✓ | ✓ |
| \`admin:manage\` | | | | ✓ |

---

## Listing Users

\`\`\`bash
curl http://localhost:8000/api/v1/admin/users \\
  -H "Authorization: Bearer $ADMIN_TOKEN"

# [
#   {"id": "usr_abc", "email": "alice@acme.com", "role": "investigator", "is_active": true},
#   {"id": "usr_def", "email": "bob@acme.com",   "role": "approver",     "is_active": true},
#   {"id": "usr_ghi", "email": "carol@acme.com", "role": "viewer",       "is_active": true}
# ]
\`\`\`

---

## Changing a User's Role

\`\`\`bash
curl -X PATCH http://localhost:8000/api/v1/admin/users/usr_abc \\
  -H "Authorization: Bearer $ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"role": "approver"}'
\`\`\`

Role changes take effect on the next API request — existing sessions are not invalidated immediately.

---

## Deactivating a User

\`\`\`bash
curl -X DELETE http://localhost:8000/api/v1/admin/users/usr_abc \\
  -H "Authorization: Bearer $ADMIN_TOKEN"
\`\`\`

Deactivated users cannot create new sessions. Existing tokens will be rejected at the next request.

---

## Approval Workflow

When a user runs \`bugpilot fix suggest\`, each action is assigned a risk level. The approval gate:

| Risk level | Approval required | Who can approve |
|-----------|-------------------|-----------------|
| \`low\` | No | Anyone (investigator+) can run immediately |
| \`medium\` | Yes | \`approver\` or \`admin\` role |
| \`high\` | Yes | \`approver\` or \`admin\` role |
| \`critical\` | Yes | \`approver\` or \`admin\` role |

### Approving an action (CLI)

\`\`\`bash
# As a user with approver role:
bugpilot fix approve act_d2f4e1 \\
  --note "Verified rollback path with infra team. Safe to proceed."
\`\`\`

### Approving via API

\`\`\`bash
curl -X POST http://localhost:8000/api/v1/actions/act_d2f4e1/approve \\
  -H "Authorization: Bearer $APPROVER_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"note": "Approved — rollback verified safe."}'
\`\`\`

### What happens after approval

1. The action status changes from \`pending\` → \`approved\`
2. Any \`investigator\` in the org can now run the action
3. The approval is recorded in the \`approvals\` table with approver user ID, timestamp, and note
4. The action execution is also logged to \`audit_logs\`

---

## Audit Log

All write operations are logged to the audit trail. Query it:

\`\`\`bash
curl "http://localhost:8000/api/v1/admin/audit-logs?limit=50" \\
  -H "Authorization: Bearer $ADMIN_TOKEN"

# [
#   {
#     "id": "aud_abc",
#     "event_type": "action_approved",
#     "entity_type": "action",
#     "entity_id": "act_d2f4e1",
#     "user_id": "usr_def",
#     "ip_address": "10.0.1.42",
#     "occurred_at": "2024-01-15T15:12:00Z",
#     "metadata": {"note": "Approved — rollback verified safe."}
#   }
# ]
\`\`\`

Audit logs are retained according to the org's retention policy (default: 365 days).

---

## Org Settings

\`\`\`bash
# Get current settings
curl http://localhost:8000/api/v1/admin/org/settings \\
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Update retention policy
curl -X PATCH http://localhost:8000/api/v1/admin/org/settings \\
  -H "Authorization: Bearer $ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "retention": {
      "investigations_days": 180,
      "evidence_metadata_days": 60,
      "raw_payload_days": 14
    }
  }'
\`\`\`

Retention changes apply to the next daily purge run.`,
  },
  "data-retention": {
    slug: "data-retention",
    title: "Data Retention",
    category: "How-To Guides",
    content: `# How to Configure Data Retention

BugPilot implements a three-phase data retention policy that is configurable per organisation. This guide explains the phases, defaults, and how to tune them.

---

## Retention Phases

BugPilot retains data in three progressively smaller windows:

| Phase | Default | What happens |
|-------|---------|-------------|
| **Investigation archive** | 365 days | Resolved/closed investigations are archived after this period |
| **Evidence metadata** | 90 days | Evidence rows (normalized_summary, reliability_score, etc.) are deleted |
| **Raw payload expiry** | 30 days | \`payload_ref\` column is set to \`NULL\` — the actual raw payload in external storage is no longer referenced |

The retention service runs a **three-phase idempotent purge** daily. Each phase writes an \`AuditLog\` entry *before* making any deletions, ensuring full auditability.

---

## Configuring Retention

Set retention policy per organisation via the admin API:

\`\`\`bash
curl -X PATCH http://localhost:8000/api/v1/admin/org/settings \\
  -H "Authorization: Bearer $ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "retention": {
      "investigations_days": 180,
      "evidence_metadata_days": 60,
      "raw_payload_days": 14
    }
  }'
\`\`\`

Changes take effect on the next daily purge run.

---

## Common Retention Configurations

### Compliance-heavy (HIPAA / SOC 2)

\`\`\`json
{
  "investigations_days": 365,
  "evidence_metadata_days": 365,
  "raw_payload_days": 7
}
\`\`\`

Keep investigation and evidence metadata for a full year for audit purposes. Expire raw payloads quickly since they may contain PII.

### Cost-optimised

\`\`\`json
{
  "investigations_days": 90,
  "evidence_metadata_days": 30,
  "raw_payload_days": 7
}
\`\`\`

Shorter windows reduce database size and storage costs.

### Development / testing

\`\`\`json
{
  "investigations_days": 30,
  "evidence_metadata_days": 7,
  "raw_payload_days": 1
}
\`\`\`

Aggressive purging for dev environments.

---

## What Each Phase Deletes

### Phase 1 — Investigation archive

\`\`\`sql
-- Archive investigations resolved > N days ago
UPDATE investigations
SET status = 'archived'
WHERE status IN ('resolved', 'closed')
  AND resolved_at < NOW() - INTERVAL 'N days';
\`\`\`

Before archiving, an \`AuditLog\` entry is written:

\`\`\`json
{
  "event_type": "retention_phase1_archive",
  "entity_type": "investigation",
  "metadata": { "count": 12, "cutoff": "2023-10-12T02:00:00Z" }
}
\`\`\`

### Phase 2 — Evidence metadata deletion

\`\`\`sql
-- Delete evidence for archived investigations older than evidence_metadata_days
DELETE FROM evidence_items
WHERE investigation_id IN (
  SELECT id FROM investigations WHERE status = 'archived'
)
AND fetched_at < NOW() - INTERVAL 'N days';
\`\`\`

### Phase 3 — Raw payload expiry

\`\`\`sql
-- Null the payload_ref for evidence older than raw_payload_days
UPDATE evidence_items
SET payload_ref = NULL
WHERE fetched_at < NOW() - INTERVAL 'N days'
  AND payload_ref IS NOT NULL;
\`\`\`

The evidence row is kept (normalized_summary and metadata are preserved). Only the reference to the external raw payload is cleared.

---

## Running the Purge Manually

\`\`\`bash
# In a container or locally
cd backend
python3 -c "
import asyncio
from app.services.retention_service import RetentionService
from app.core.db import get_async_session

async def run():
    async with get_async_session() as db:
        service = RetentionService(db)
        await service.run_daily_purge()
        print('Purge complete')

asyncio.run(run())
"
\`\`\`

---

## Idempotency

The purge is fully idempotent. Running it twice produces the same result as running it once. This makes it safe to retry on failure or run from multiple processes (with appropriate database-level concurrency controls).

---

## Monitoring Retention

The purge writes to the audit log, which you can query:

\`\`\`bash
curl "http://localhost:8000/api/v1/admin/audit-logs?event_type=retention_phase1_archive" \\
  -H "Authorization: Bearer $ADMIN_TOKEN"
\`\`\`

You can also alert on absence of purge runs:

\`\`\`yaml
# Prometheus — alert if no retention log entries in 25h
- alert: BugPilotRetentionNotRunning
  expr: |
    (time() - bugpilot_last_retention_run_timestamp) > 90000
  labels:
    severity: warning
  annotations:
    summary: "BugPilot retention job has not run in > 25 hours"
\`\`\``,
  },
  "cli-reference": {
    slug: "cli-reference",
    title: "CLI Reference",
    category: "Reference",
    content: `# CLI Reference

The \`bugpilot\` CLI is the primary interface for interacting with the BugPilot platform. Every command supports three output formats via the global \`--output\` / \`-o\` flag.

---

## Global Options

\`\`\`
bugpilot [OPTIONS] COMMAND [ARGS]...
\`\`\`

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| \`--api-url TEXT\` | \`BUGPILOT_API_URL\` | \`http://localhost:8000\` | BugPilot backend URL |
| \`-o, --output TEXT\` | \`BUGPILOT_OUTPUT\` | \`human\` | Output format: \`human\` \\| \`json\` \\| \`verbose\` |
| \`--no-color\` | \`NO_COLOR\` | false | Disable Rich colour output |
| \`-v, --version\` | — | — | Print version and exit |

### Output Formats

**\`human\`** (default) — Rich-formatted tables and panels with colour-coded status and severity. Best for terminal use.

**\`json\`** — Machine-readable JSON on stdout. Every command writes a single JSON object or array. Ideal for scripting and CI pipelines.

\`\`\`bash
bugpilot investigate list -o json | jq '.[] | select(.status == "open")'
\`\`\`

**\`verbose\`** — Includes all fields including internal metadata, formatted with syntax highlighting. Useful for debugging.

---

## \`bugpilot auth\` — Authentication

### \`auth activate\`

Activate a BugPilot license on this device.

\`\`\`bash
bugpilot auth activate --license-key bp_<KEY>
\`\`\`

| Option | Required | Description |
|--------|----------|-------------|
| \`--license-key\` | Yes | License key (format: \`bp_...\`) |

**Example:**

\`\`\`
$ bugpilot auth activate --license-key bp_T7zK9mNvXq...

✓ License activated
  Org:        acme-corp
  Tier:       pro
  Seats:      8 / 10 available
  Expires:    2027-03-01
  Device ID:  dev_a3f8c2d1e9
\`\`\`

Credentials are stored at \`~/.config/bugpilot/credentials.json\` with permissions \`600\`.

---

### \`auth logout\`

Revoke the current session and clear local credentials.

\`\`\`bash
bugpilot auth logout
\`\`\`

---

### \`auth whoami\`

Display the currently authenticated user and org.

\`\`\`bash
bugpilot auth whoami
\`\`\`

\`\`\`
  User:  alice@acme.com
  Role:  investigator
  Org:   acme-corp
  Tier:  pro
\`\`\`

---

## \`bugpilot investigate\` — Investigations

### \`investigate list\`

List all investigations for your org.

\`\`\`bash
bugpilot investigate list [--status STATUS] [--service SERVICE] [--limit N]
\`\`\`

| Option | Description |
|--------|-------------|
| \`--status\` | Filter: \`open\` \\| \`in_progress\` \\| \`resolved\` \\| \`closed\` |
| \`--service\` | Filter by service name |
| \`--limit\` | Max results (default: 20) |

**Example:**

\`\`\`
$ bugpilot investigate list --status open

  ID             TITLE                                 SERVICE           STATUS     STARTED
  inv_7f3a2b...  High error rate on payment-service    payment-service   open       2 hours ago
  inv_c1d9e0...  Database connection pool exhausted    orders-db         open       45 min ago
  inv_8a2f1c...  Latency spike - checkout flow         checkout-svc      open       12 min ago
\`\`\`

---

### \`investigate create\`

Open a new investigation.

\`\`\`bash
bugpilot investigate create \\
  --title "TITLE" \\
  --service SERVICE \\
  [--severity critical|high|medium|low]
\`\`\`

| Option | Required | Description |
|--------|----------|-------------|
| \`--title\` | Yes | Short description of the symptom |
| \`--service\` | Yes | Affected service name (must match connector service labels) |
| \`--severity\` | No | \`critical\` \\| \`high\` \\| \`medium\` \\| \`low\` (default: \`high\`) |

---

### \`investigate get\`

Fetch full details of one investigation.

\`\`\`bash
bugpilot investigate get <INVESTIGATION_ID>
\`\`\`

---

### \`investigate update\`

Update investigation fields.

\`\`\`bash
bugpilot investigate update <INVESTIGATION_ID> \\
  [--title "NEW TITLE"] \\
  [--status in_progress|resolved]
\`\`\`

---

### \`investigate close\`

Mark an investigation as resolved and record the root cause.

\`\`\`bash
bugpilot investigate close <INVESTIGATION_ID> \\
  --root-cause "Description of what caused the issue"
\`\`\`

---

## \`bugpilot incident\` — Incident Triage

### \`incident triage\`

Run automated triage on a new incoming alert or incident. BugPilot checks for existing open investigations (deduplication), creates or updates an investigation, collects initial evidence, and prints the top hypothesis.

\`\`\`bash
bugpilot incident triage \\
  --service SERVICE \\
  --alert-name "ALERT_NAME" \\
  [--severity critical|high|medium|low] \\
  [--since DURATION]
\`\`\`

| Option | Required | Description |
|--------|----------|-------------|
| \`--service\` | Yes | Affected service |
| \`--alert-name\` | Yes | Alert or incident name |
| \`--severity\` | No | Incident severity |
| \`--since\` | No | How far back to look for evidence (e.g. \`2h\`, \`30m\`, \`1d\`). Default: \`1h\` |

**Example:**

\`\`\`
$ bugpilot incident triage \\
    --service payment-service \\
    --alert-name "HTTP 5xx rate > 5%" \\
    --severity critical \\
    --since 2h

  ⚡ Dedup check: No similar open investigations found
  ✓ Investigation created: inv_7f3a2b...
  ↓ Collecting evidence (4 connectors)...
    ✓ datadog/logs      (47 items, 0.3s)
    ✓ datadog/metrics   (12 items, 0.4s)
    ✓ github/deploys    (3 items, 0.2s)
    ✗ grafana/metrics   degraded: connection timeout
  ✓ Hypotheses generated (3)

  TOP HYPOTHESIS
  ───────────────────────────────────────────────────────
  Rank 1  │  Bad Deployment Introduced Regression      ▓▓▓▓▓▓▓▒ 72%
          │  A deployment at 14:23 UTC correlates with the onset
          │  of 5xx errors. Commit a3f8c2d: "Update Stripe SDK v4"
          │  may have introduced a breaking change.
  ───────────────────────────────────────────────────────
  Run: bugpilot fix suggest inv_7f3a2b
\`\`\`

---

### \`incident status\`

Show the current status and summary of an ongoing incident.

\`\`\`bash
bugpilot incident status <INVESTIGATION_ID>
\`\`\`

---

## \`bugpilot evidence\` — Evidence

### \`evidence collect\`

Trigger evidence collection from all configured connectors for a given investigation.

\`\`\`bash
bugpilot evidence collect <INVESTIGATION_ID> \\
  [--since DURATION] \\
  [--until DATETIME] \\
  [--connector CONNECTOR_ID] \\
  [--capability logs|metrics|traces|alerts|incidents|deployments]
\`\`\`

| Option | Description |
|--------|-------------|
| \`--since\` | Duration string: \`30m\`, \`2h\`, \`1d\` (default: \`1h\`) |
| \`--until\` | ISO-8601 datetime. Default: now |
| \`--connector\` | Restrict to one connector ID |
| \`--capability\` | Restrict to one capability type |

**Example output:**

\`\`\`
$ bugpilot evidence collect inv_7f3a2b --since 2h

  Collecting evidence (since 2h ago)...

  CONNECTOR            CAPABILITY    ITEMS    LATENCY    STATUS
  datadog              logs          47       0.34s      ok
  datadog              metrics       12       0.41s      ok
  datadog              alerts        3        0.28s      ok
  grafana              metrics       —        —          degraded: timeout
  github               deployments   2        0.19s      ok
  pagerduty            incidents     1        0.22s      ok

  Total: 65 items collected (1 connector degraded)
\`\`\`

---

### \`evidence list\`

List evidence items for an investigation.

\`\`\`bash
bugpilot evidence list <INVESTIGATION_ID> \\
  [--capability logs|metrics|traces|alerts|incidents|deployments] \\
  [--limit N]
\`\`\`

---

### \`evidence get\`

Show the full normalized evidence item.

\`\`\`bash
bugpilot evidence get <EVIDENCE_ID>
\`\`\`

---

## \`bugpilot hypotheses\` — Hypotheses

### \`hypotheses list\`

List all hypotheses for an investigation, ranked by confidence.

\`\`\`bash
bugpilot hypotheses list <INVESTIGATION_ID> [--status active|confirmed|rejected]
\`\`\`

**Example:**

\`\`\`
$ bugpilot hypotheses list inv_7f3a2b

  RANK  HYPOTHESIS                              CONFIDENCE  STATUS    SOURCE
  1     Bad Deployment Introduced Regression    72%         active    rule
  2     Memory Exhaustion                       58%         active    rule
  3     Upstream Dependency Degradation         41%         active    graph

  ⚠ Evidence from single source only (logs). Confidence scores are capped at 40%.
    Collect metrics or traces to improve hypothesis quality.
\`\`\`

---

### \`hypotheses confirm\`

Mark a hypothesis as confirmed (the root cause).

\`\`\`bash
bugpilot hypotheses confirm <HYPOTHESIS_ID>
\`\`\`

---

### \`hypotheses reject\`

Mark a hypothesis as ruled out.

\`\`\`bash
bugpilot hypotheses reject <HYPOTHESIS_ID> [--reason "REASON"]
\`\`\`

---

## \`bugpilot fix\` — Remediation Actions

### \`fix suggest\`

Generate safe remediation actions for an investigation.

\`\`\`bash
bugpilot fix suggest <INVESTIGATION_ID> [--hypothesis-id HYPOTHESIS_ID]
\`\`\`

**Example:**

\`\`\`
$ bugpilot fix suggest inv_7f3a2b

  SUGGESTED ACTIONS

  #1  Rollback deployment a3f8c2d                         RISK: low
      Expected effect: Restore previous stable version
      Rollback path:   git revert a3f8c2d && redeploy
      Approval needed: No

  #2  Increase memory limit to 1Gi                        RISK: medium
      Expected effect: Prevent OOMKill recurrence
      Rollback path:   Revert resource quota change
      Approval needed: Yes (approver role)

  #3  Temporarily disable Stripe SDK v4 feature flag      RISK: low
      Expected effect: Bypass potentially broken code path
      Rollback path:   Re-enable feature flag
      Approval needed: No
\`\`\`

---

### \`fix approve\`

Approve a medium/high-risk action (requires \`approver\` role).

\`\`\`bash
bugpilot fix approve <ACTION_ID> [--note "APPROVAL_NOTE"]
\`\`\`

---

### \`fix run\`

Execute an approved action.

\`\`\`bash
bugpilot fix run <ACTION_ID> [--dry-run]
\`\`\`

| Option | Description |
|--------|-------------|
| \`--dry-run\` | Simulate the action without making changes. Prints what would happen. |

**Dry-run example:**

\`\`\`
$ bugpilot fix run act_d2f4e1 --dry-run

  DRY RUN: Rollback deployment a3f8c2d
  ─────────────────────────────────────
  Would execute:
    1. git revert a3f8c2d
    2. docker build -t payment-service:rollback .
    3. kubectl set image deployment/payment-service app=payment-service:rollback

  Estimated downtime: 0s (rolling update)
  Risk assessment:    LOW — previous version was stable for 3 days

  To apply: bugpilot fix run act_d2f4e1
\`\`\`

---

### \`fix cancel\`

Cancel a pending or approved action.

\`\`\`bash
bugpilot fix cancel <ACTION_ID>
\`\`\`

---

### \`fix list\`

List all actions for an investigation.

\`\`\`bash
bugpilot fix list <INVESTIGATION_ID> [--status pending|approved|running|completed|cancelled]
\`\`\`

---

## \`bugpilot export\` — Export

### \`export json\`

Export a complete investigation as structured JSON.

\`\`\`bash
bugpilot export json <INVESTIGATION_ID> [--output-file FILE]
\`\`\`

The exported JSON includes: investigation metadata, timeline, evidence summary (redacted, no raw payloads), all hypotheses with rankings, all actions and approval decisions, and outcome.

---

### \`export markdown\`

Export a human-readable incident report in Markdown format suitable for wikis, Confluence, or GitHub.

\`\`\`bash
bugpilot export markdown <INVESTIGATION_ID> [--output-file FILE]
\`\`\`

**Sample output (truncated):**

\`\`\`markdown
# Incident Report: High error rate on payment-service
**ID:** inv_7f3a2b  **Severity:** critical  **Resolved:** 2024-01-15 16:42 UTC

## Timeline
| Time (UTC) | Event |
|------------|-------|
| 14:23      | Deployment a3f8c2d merged by alice@acme.com |
| 14:31      | HTTP 5xx rate exceeded 5% threshold |
| 14:33      | PagerDuty incident created |
| 14:35      | BugPilot investigation opened |

## Root Cause
Bad Deployment Introduced Regression (confidence: 72%)

## Actions Taken
1. ✓ Rollback deployment a3f8c2d (approved by bob@acme.com)
\`\`\`

---

## Shell Completion

\`\`\`bash
# bash
bugpilot --install-completion bash
source ~/.bashrc

# zsh
bugpilot --install-completion zsh
source ~/.zshrc

# fish
bugpilot --install-completion fish
\`\`\`

---

## Using with CI/CD

In CI pipelines, use \`--output json\` and \`BUGPILOT_API_URL\` / \`BUGPILOT_LICENSE_KEY\` environment variables:

\`\`\`yaml
# GitHub Actions example
- name: Triage deployment incident
  env:
    BUGPILOT_API_URL: \${{ secrets.BUGPILOT_URL }}
    BUGPILOT_LICENSE_KEY: \${{ secrets.BUGPILOT_KEY }}
  run: |
    bugpilot auth activate --license-key "$BUGPILOT_LICENSE_KEY"
    bugpilot incident triage \\
      --service "$SERVICE" \\
      --alert-name "Deployment smoke test failed" \\
      --severity high \\
      --since 15m \\
      --output json > triage-result.json
    cat triage-result.json | jq '.top_hypothesis'
\`\`\``,
  },
  "api-reference": {
    slug: "api-reference",
    title: "API Reference",
    category: "Reference",
    content: `# API Reference

The BugPilot REST API follows standard HTTP conventions. All endpoints are versioned under \`/api/v1/\`. Request and response bodies use JSON (\`Content-Type: application/json\`).

---

## Authentication

All endpoints except \`/auth/activate\` require a valid JWT in the Authorization header:

\`\`\`
Authorization: Bearer <jwt_token>
\`\`\`

JWTs expire after 1 hour. Use \`POST /auth/refresh\` with a valid refresh token to obtain a new pair.

---

## Authentication Endpoints

### \`POST /api/v1/auth/activate\`

Activate a license on a device and create a session.

**Request body:**

\`\`\`json
{
  "license_key": "bp_T7zK9mNvXqAbCdEfGhIjKlMnOpQrStUvWxYz",
  "device_fingerprint": "sha256-of-mac-hostname-machine"
}
\`\`\`

**Response \`200\`:**

\`\`\`json
{
  "access_token": "eyJ...",
  "refresh_token": "opaque-64-byte-hex",
  "token_type": "bearer",
  "org_id": "3f8a...",
  "user_id": "9c1b..."
}
\`\`\`

---

### \`POST /api/v1/auth/refresh\`

Rotate the access and refresh tokens.

**Request body:**

\`\`\`json
{
  "refresh_token": "opaque-64-byte-hex"
}
\`\`\`

**Response \`200\`:** Same structure as \`/activate\`.

---

### \`POST /api/v1/auth/logout\`

Revoke the current session.

**Response \`204\`:** No body.

---

### \`GET /api/v1/auth/whoami\`

Return the authenticated user's details.

**Response \`200\`:**

\`\`\`json
{
  "user_id": "9c1b...",
  "email": "alice@acme.com",
  "role": "investigator",
  "org_id": "3f8a...",
  "org_slug": "acme-corp"
}
\`\`\`

---

## Investigation Endpoints

### \`GET /api/v1/investigations\`

List investigations for the authenticated org.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| \`status\` | string | — | \`open\` \\| \`in_progress\` \\| \`resolved\` \\| \`closed\` |
| \`service\` | string | — | Filter by linked service name |
| \`limit\` | int | 20 | Max results |
| \`offset\` | int | 0 | Pagination offset |

**Response \`200\`:**

\`\`\`json
[
  {
    "id": "inv_7f3a2b",
    "title": "High error rate on payment-service",
    "status": "open",
    "linked_services": ["payment-service"],
    "started_at": "2024-01-15T14:35:00Z",
    "resolved_at": null,
    "hypothesis_count": 3,
    "evidence_count": 65
  }
]
\`\`\`

---

### \`POST /api/v1/investigations\`

Create a new investigation.

**Request body:**

\`\`\`json
{
  "title": "High error rate on payment-service",
  "linked_services": ["payment-service"],
  "context": {
    "alert_name": "HTTP 5xx rate > 5%",
    "severity": "critical"
  }
}
\`\`\`

**Response \`201\`:**

\`\`\`json
{
  "id": "inv_7f3a2b",
  "title": "High error rate on payment-service",
  "status": "open",
  "branch_id": "branch_main",
  "linked_services": ["payment-service"],
  "started_at": "2024-01-15T14:35:00Z"
}
\`\`\`

---

### \`GET /api/v1/investigations/{investigation_id}\`

Fetch a single investigation with full detail.

---

### \`PATCH /api/v1/investigations/{investigation_id}\`

Update investigation fields.

**Request body (all fields optional):**

\`\`\`json
{
  "title": "Updated title",
  "status": "in_progress",
  "linked_services": ["payment-service", "stripe-gateway"]
}
\`\`\`

---

### \`DELETE /api/v1/investigations/{investigation_id}\`

Delete an investigation and all associated data. Requires \`admin\` role.

---

## Evidence Endpoints

### \`POST /api/v1/evidence/collect\`

Trigger evidence collection from all configured connectors.

**Request body:**

\`\`\`json
{
  "investigation_id": "inv_7f3a2b",
  "since": "2024-01-15T12:00:00Z",
  "until": "2024-01-15T15:00:00Z",
  "capabilities": ["LOGS", "METRICS", "DEPLOYMENTS"]
}
\`\`\`

**Response \`200\`:**

\`\`\`json
{
  "collected": 65,
  "degraded_connectors": ["grafana"],
  "duration_seconds": 3.2,
  "evidence_ids": ["ev_a1b2...", "..."]
}
\`\`\`

---

### \`GET /api/v1/evidence\`

List evidence for an investigation.

**Query parameters:** \`investigation_id\` (required), \`capability\`, \`limit\`, \`offset\`.

---

### \`GET /api/v1/evidence/{evidence_id}\`

Fetch a single evidence item.

**Response \`200\`:**

\`\`\`json
{
  "id": "ev_a1b2",
  "investigation_id": "inv_7f3a2b",
  "source_system": "datadog",
  "capability": "LOGS",
  "normalized_summary": "ERROR: NullPointerException in PaymentProcessor.charge() at 14:31:42",
  "reliability_score": 0.92,
  "is_redacted": true,
  "fetched_at": "2024-01-15T14:36:10Z",
  "ttl_expires_at": "2024-01-22T14:36:10Z"
}
\`\`\`

---

## Hypothesis Endpoints

### \`GET /api/v1/hypotheses\`

List hypotheses for an investigation.

**Query parameters:** \`investigation_id\` (required), \`status\` (\`active\` \\| \`confirmed\` \\| \`rejected\`).

**Response \`200\`:**

\`\`\`json
[
  {
    "id": "hyp_c9e1",
    "investigation_id": "inv_7f3a2b",
    "title": "Bad Deployment Introduced Regression",
    "description": "A deployment at 14:23 UTC correlates with 5xx onset...",
    "confidence_score": 0.72,
    "rank": 1,
    "status": "active",
    "generated_by": "rule",
    "is_single_lane": false,
    "evidence_ids": ["ev_a1b2", "ev_c3d4"]
  }
]
\`\`\`

---

### \`POST /api/v1/hypotheses/{hypothesis_id}/confirm\`

Mark a hypothesis as confirmed (the root cause).

**Response \`200\`:** Updated hypothesis object.

---

### \`POST /api/v1/hypotheses/{hypothesis_id}/reject\`

Mark a hypothesis as rejected.

**Request body (optional):**

\`\`\`json
{ "reason": "Deployment was rolled back before the spike started" }
\`\`\`

---

## Action Endpoints

### \`POST /api/v1/actions/suggest\`

Generate remediation action candidates for an investigation.

**Request body:**

\`\`\`json
{
  "investigation_id": "inv_7f3a2b",
  "hypothesis_id": "hyp_c9e1"
}
\`\`\`

**Response \`200\`:**

\`\`\`json
[
  {
    "id": "act_d2f4",
    "description": "Rollback deployment a3f8c2d",
    "rationale": "Deployment correlates with 5xx onset",
    "risk_level": "low",
    "expected_effect": "Restore previous stable version",
    "rollback_path": "git revert a3f8c2d && redeploy",
    "status": "pending"
  }
]
\`\`\`

---

### \`POST /api/v1/actions/{action_id}/approve\`

Approve a medium/high/critical risk action. Requires \`approver\` role.

**Request body:**

\`\`\`json
{ "note": "Approved after verifying rollback path with infra team" }
\`\`\`

---

### \`POST /api/v1/actions/{action_id}/run\`

Execute an action. For \`--dry-run\`, pass \`"dry_run": true\`.

**Request body:**

\`\`\`json
{ "dry_run": false }
\`\`\`

**Response \`200\`:**

\`\`\`json
{
  "action_id": "act_d2f4",
  "status": "completed",
  "dry_run": false,
  "output": "Deployment rolled back successfully. Pod restarts: 3/3 ready."
}
\`\`\`

---

## Graph Endpoints

### \`GET /api/v1/graph/timeline/{investigation_id}\`

Return the investigation timeline as a list of events sorted by time.

**Response \`200\`:**

\`\`\`json
[
  {
    "id": "node_1a2b",
    "node_type": "deployment",
    "label": "Deploy a3f8c2d",
    "timestamp": "2024-01-15T14:23:00Z",
    "properties": { "commit": "a3f8c2d", "author": "alice@acme.com" }
  },
  {
    "id": "node_3c4d",
    "node_type": "symptom",
    "label": "HTTP 5xx rate spike",
    "timestamp": "2024-01-15T14:31:00Z"
  }
]
\`\`\`

---

### \`GET /api/v1/graph/causal/{investigation_id}\`

Return the full causal graph as nodes + edges.

**Response \`200\`:**

\`\`\`json
{
  "nodes": [...],
  "edges": [
    {
      "id": "edge_e5f6",
      "from_node_id": "node_3c4d",
      "to_node_id": "node_1a2b",
      "edge_type": "caused_by"
    }
  ]
}
\`\`\`

---

## Webhook Endpoints

### \`POST /api/v1/webhooks/datadog\`

Receive a Datadog webhook. Requires \`X-Datadog-Webhook-ID\` and \`X-Hub-Signature\` headers.

### \`POST /api/v1/webhooks/grafana\`

Receive a Grafana alerting webhook. Requires \`X-Grafana-Signature\` header (format: \`sha256=HMAC\`).

### \`POST /api/v1/webhooks/cloudwatch\`

Receive an AWS SNS/CloudWatch notification. Signature verified against SNS certificate.

### \`POST /api/v1/webhooks/pagerduty\`

Receive a PagerDuty webhook. Requires \`X-PagerDuty-Signature\` header (format: \`v1=HMAC\`). Supports multiple signatures for key rotation.

All webhook handlers:
- Verify the HMAC-SHA256 signature
- Support a dual-secret grace window for key rotation
- Apply per-IP+org rate limiting (100 requests/minute)
- Log verification failures to Prometheus and structlog

---

## Admin Endpoints

Admin endpoints require the \`admin\` role.

| Method | Path | Description |
|--------|------|-------------|
| \`GET\` | \`/api/v1/admin/connectors\` | List configured connectors |
| \`POST\` | \`/api/v1/admin/connectors\` | Add a new connector |
| \`DELETE\` | \`/api/v1/admin/connectors/{id}\` | Remove a connector |
| \`GET\` | \`/api/v1/admin/connectors/validate\` | Test all connector connections |
| \`GET\` | \`/api/v1/admin/users\` | List org users |
| \`PATCH\` | \`/api/v1/admin/users/{id}\` | Update user role |
| \`DELETE\` | \`/api/v1/admin/users/{id}\` | Deactivate user |
| \`GET\` | \`/api/v1/admin/audit-logs\` | Query audit log |
| \`GET\` | \`/api/v1/admin/org/settings\` | Get org settings |
| \`PATCH\` | \`/api/v1/admin/org/settings\` | Update org settings (retention, etc.) |
| \`GET\` | \`/api/v1/admin/webhooks\` | List configured webhooks |
| \`POST\` | \`/api/v1/admin/webhooks\` | Register a new webhook secret |
| \`DELETE\` | \`/api/v1/admin/webhooks/{id}\` | Revoke a webhook |

---

## Health Endpoints

### \`GET /health\`

Liveness probe. Always returns \`200\` if the process is running.

\`\`\`json
{ "status": "ok" }
\`\`\`

### \`GET /health/ready\`

Readiness probe. Returns \`200\` if the database is reachable.

\`\`\`json
{ "status": "ready", "db": "ok" }
\`\`\`

Returns \`503\` with \`{ "status": "not_ready", "db": "error: ..." }\` if the DB is unavailable.

### \`GET /metrics\`

Prometheus metrics in text/plain exposition format.

---

## Error Responses

All errors follow a consistent structure:

\`\`\`json
{
  "detail": "Human-readable error message"
}
\`\`\`

| Status | Meaning |
|--------|---------|
| \`400\` | Bad request / validation error |
| \`401\` | Missing or invalid JWT |
| \`403\` | Insufficient role/permission |
| \`404\` | Resource not found |
| \`409\` | Conflict (e.g. duplicate org slug) |
| \`422\` | Request body validation failed |
| \`429\` | Rate limit exceeded |
| \`500\` | Internal server error |

---

## Rate Limiting

Webhook endpoints are rate-limited to **100 requests per minute per source IP + org combination**. Other API endpoints do not currently enforce client-side rate limits but rely on the database connection pool as a natural backpressure mechanism.

---

## OpenAPI Specification

The full OpenAPI 3.1 spec is served at:

\`\`\`
GET /openapi.json
GET /docs           (Swagger UI)
GET /redoc          (ReDoc)
\`\`\`

To export the spec to a file:

\`\`\`bash
curl http://localhost:8000/openapi.json > openapi/bugpilot_v1.json
\`\`\``,
  },
  architecture: {
    slug: "architecture",
    title: "Architecture",
    category: "Reference",
    content: `# Architecture Overview

BugPilot turns a vague symptom — "payment service is slow" — into ranked, evidence-backed debugging hypotheses with suggested safe actions. This document explains the system architecture, data flow, and key design decisions.

---

## System Diagram

\`\`\`
┌─────────────────────────────────────────────────────────────────────┐
│                          User / CI Pipeline                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ CLI (typer + rich)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BugPilot REST API (FastAPI)                     │
│                                                                     │
│  /auth  /investigations  /evidence  /hypotheses  /actions           │
│  /graph  /webhooks  /service-mappings  /admin  /health  /metrics    │
└──────────┬───────────────────────────────────────────────┬──────────┘
           │                                               │
           ▼                                               ▼
┌──────────────────┐                           ┌──────────────────────┐
│   PostgreSQL     │                           │   Evidence Collector  │
│  (async/asyncpg) │◄──────────────────────────│  (asyncio.gather)    │
└──────────────────┘                           └──────┬───────────────┘
                                                      │ concurrent
           ┌──────────────────────────────────────────┼──────────────────┐
           ▼                 ▼                ▼        ▼       ▼         ▼
     ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────┐  ┌────┐  ┌───────┐
     │ Datadog  │  │   Grafana    │  │CloudWatch│  │ K8s│  │ GH │  │  PD   │
     └──────────┘  └──────────────┘  └──────────┘  └────┘  └────┘  └───────┘
\`\`\`

---

## Core Concepts

### Investigation

An **Investigation** is the top-level container for a debugging session. It is created either manually via CLI/API or automatically when a webhook alert arrives. An investigation tracks:

- The affected service(s)
- A timeline of events
- Evidence collected from connectors
- Hypotheses about the root cause
- Actions taken (with approvals)
- The final outcome

Investigations can be **branched** for parallel hypothesis exploration. Each branch gets its own graph slice without affecting the main investigation.

### Evidence

**Evidence items** are normalised facts collected from connectors. Each item has:

- \`source_system\` — which connector produced it (e.g. \`datadog\`, \`github\`)
- \`capability\` — what kind of data it is (\`LOGS\`, \`METRICS\`, \`DEPLOYMENTS\`, etc.)
- \`normalized_summary\` — a ≤500-character human-readable summary (always kept)
- \`payload_ref\` — reference to the full raw payload in external storage (nulled after TTL)
- \`reliability_score\` — 0-1 score adjusted for staleness and source quality
- \`is_redacted\` — whether PII/secrets have been scrubbed
- \`redaction_manifest\` — a log of what was redacted and why

Evidence is **never sent to an LLM in raw form**. The privacy layer redacts it first.

### Investigation Graph

Every investigation maintains a **graph** (not a simple list) of nodes and edges. Nodes represent symptoms, services, evidence items, and deployment events. Edges represent causal and temporal relationships.

\`\`\`
[Symptom: 5xx rate spike]
       │
       ├──caused_by──► [Evidence: Datadog alert at 14:31]
       │
       └──correlates_with──► [Deployment: a3f8c2d at 14:23]
                                    │
                                    └──code_change──► [GitHub commit: Update Stripe SDK v4]
\`\`\`

The graph is stored as \`GraphNodeModel\` and \`GraphEdgeModel\` rows, and can be queried as a \`GraphSlice\` — a lightweight in-memory snapshot used by the hypothesis engine and LLM layer.

### Hypothesis Engine

The hypothesis engine runs a **6-pass pipeline** on each \`GraphSlice\`:

1. **Rule-based pass** — Pattern matching for known failure modes:
   - OOMKilled / memory spike → Memory Exhaustion hypothesis
   - 5xx errors + recent deployment → Bad Deployment Introduced Regression
   - High latency + multiple services → Upstream Dependency Degradation

2. **Graph correlation pass** — Scores hypotheses by edge density. Symptoms with ≥3 connected edges and related services generate Service Graph Anomaly hypotheses with confidence proportional to edge count.

3. **Historical reranking** — (When DB context is available) Previous investigations with similar evidence patterns adjust confidence scores.

4. **LLM synthesis pass** — If the graph slice is redacted (\`is_redacted=True\`), the LLM is asked to generate additional hypotheses not already covered by rule-based or graph passes. **The LLM never receives raw evidence.**

5. **Merge and deduplicate** — Jaccard word-overlap similarity. Duplicates above the threshold (0.75) are merged, keeping the higher-confidence version.

6. **Rank** — Sorted by confidence_score descending. In single-lane investigations (evidence from only one capability type), all scores are capped at 0.4 and \`is_single_lane=True\` is set.

### Privacy and Redaction

BugPilot enforces a strict privacy boundary. Before any data can be sent to an LLM provider, it must pass through the redaction pipeline:

**Patterns scrubbed:**
- Email addresses
- Phone numbers (E.164 and US formats)
- JSON Web Tokens
- Bearer tokens
- Payment card numbers (Luhn)
- AWS secret access keys
- PEM private keys

The \`LLMService.complete()\` method raises \`ValueError\` if a non-redacted \`GraphSlice\` is passed. This is enforced at the code level, not configuration.

### Deduplication

When a new investigation is created (manually or via webhook), BugPilot checks for existing open investigations with overlapping context using a **weighted similarity score**:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Service overlap | 40% | Jaccard overlap of linked service names |
| Time overlap | 30% | Overlap of evidence time windows |
| Alert signature | 20% | Hash match on alert name / monitor name |
| Symptom text | 10% | Word-overlap on title strings |

If the score exceeds 0.85, the new investigation is flagged as a potential duplicate. BugPilot **never silently merges** — it reports the match and lets the user decide.

### Remediation and Approval

Actions suggested by BugPilot are assigned a risk level. The approval requirement depends on role:

| Risk level | Approval required |
|-----------|-------------------|
| \`low\` | None — any investigator can run |
| \`medium\` | \`approver\` role |
| \`high\` | \`approver\` role |
| \`critical\` | \`approver\` role |

Every action supports a **dry-run mode** that simulates the action and prints what would happen without making any changes.

---

## Database Schema Summary

BugPilot uses 21 PostgreSQL tables:

\`\`\`
organisations → licenses → users → sessions
organisations → investigations → branches
investigations → graph_nodes
investigations → graph_edges
investigations → evidence_items → hypothesis_evidence_links → hypotheses
hypotheses → actions → approvals
investigations → outcomes
organisations → connector_configs
organisations → service_mapping_models
organisations → retention_policies
organisations → audit_logs
organisations → llm_usage_logs
\`\`\`

All primary keys are UUIDs. All timestamps are \`TIMESTAMPTZ\`. JSON columns use PostgreSQL's \`JSONB\` type for indexability. A cross-dialect \`TypeDecorator\` ensures the test suite works with SQLite.

---

## Authentication Flow

\`\`\`
CLI                         API                      DB
 │                           │                        │
 │── POST /auth/activate ───►│                        │
 │   {license_key, device_fp}│                        │
 │                           │── verify license ─────►│
 │                           │── check device count ──►│
 │                           │── create Session ──────►│
 │◄── {jwt_token, refresh} ──│                        │
 │                           │                        │
 │── (on expiry) POST /auth/ │                        │
 │   refresh {refresh_token} │                        │
 │◄── {new_jwt, new_refresh} │                        │
\`\`\`

- JWT tokens are short-lived (1 hour by default)
- Refresh tokens are opaque (stored as bcrypt hashes)
- Each refresh rotates both tokens
- \`logout\` revokes the session row

---

## API Versioning

All routes live under \`/api/v1/\`. The health and metrics endpoints are at the root:

\`\`\`
GET  /health           Liveness probe
GET  /health/ready     Readiness probe (checks DB)
GET  /metrics          Prometheus metrics (text/plain)
\`\`\`

---

## Observability

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| \`bugpilot_activations_total\` | Counter | License activations |
| \`bugpilot_active_investigations\` | Gauge | Open investigations |
| \`bugpilot_investigation_duration_seconds\` | Histogram | Time from open to resolved |
| \`bugpilot_time_to_first_hypothesis_seconds\` | Histogram | Time from open to first hypothesis |
| \`bugpilot_connector_errors_total\` | Counter | Per-connector errors (label: connector) |
| \`bugpilot_connector_rate_limits_total\` | Counter | Per-connector 429s |
| \`bugpilot_webhook_verification_failures_total\` | Counter | Webhook HMAC failures |
| \`bugpilot_llm_requests_total\` | Counter | LLM completions (label: provider) |
| \`bugpilot_llm_tokens_total\` | Counter | LLM tokens used |
| \`bugpilot_http_requests_total\` | Counter | HTTP requests (label: method, path, status) |
| \`bugpilot_http_request_duration_seconds\` | Histogram | HTTP latency |

### Structured Logging

All log output is structured JSON (via structlog) with consistent fields:

\`\`\`json
{
  "timestamp": "2024-01-15T14:31:00.123Z",
  "level": "info",
  "event": "hypothesis_generated",
  "investigation_id": "inv_7f3a2b",
  "count": 3,
  "is_single_lane": false
}
\`\`\`

In development (TTY), logs are printed in a human-readable format with colour.

---

## Retention and Data Lifecycle

BugPilot implements a three-phase retention policy configurable per organisation:

| Phase | Default | Action |
|-------|---------|--------|
| Investigation archive | 365 days | Resolved investigations are archived |
| Evidence metadata | 90 days | Evidence rows are deleted |
| Raw payload expiry | 30 days | \`payload_ref\` is nulled (row kept) |

Each phase writes an \`AuditLog\` entry before any data mutation, making the operation fully auditable and idempotent. A daily purge job runs \`RetentionService.run_daily_purge()\` across all organisations.

---

## Security Design Principles

1. **Credentials never stored plaintext.** Connector credentials are Fernet-encrypted before database storage.
2. **Passwords hashed with bcrypt.** All secrets (license keys, tokens) are stored as bcrypt or SHA-256 hashes.
3. **LLM boundary enforced in code.** \`LLMService\` raises \`ValueError\` for non-redacted input — not a config flag.
4. **Org isolation at every query.** All database queries filter by \`org_id\`. No cross-org data access is possible through the API.
5. **Webhook signatures verified.** All four webhook handlers verify HMAC-SHA256 signatures with a dual-secret grace window for rotation.
6. **Role-based access control.** Four roles (viewer, investigator, approver, admin) with a typed permission matrix. Elevation is never implicit.`,
  },
  troubleshooting: {
    slug: "troubleshooting",
    title: "Troubleshooting",
    category: "Support",
    content: `# Troubleshooting Guide

Common issues and how to resolve them.

---

## CLI Issues

### \`bugpilot: command not found\`

The CLI is not installed or not on \`PATH\`.

\`\`\`bash
pip install -e ./cli
# or
pip install bugpilot
\`\`\`

Check your Python bin directory is on PATH:

\`\`\`bash
python3 -c "import sys; print(sys.prefix + '/bin')"
export PATH="$PATH:$(python3 -c 'import sys; print(sys.prefix + "/bin")')"
\`\`\`

---

### \`Error: Could not connect to BugPilot API at http://localhost:8000\`

The backend is not running or the URL is wrong.

\`\`\`bash
# Check the backend
curl http://localhost:8000/health
# Should return: {"status":"ok"}

# Check what URL the CLI is using
bugpilot auth whoami
# Look for: connecting to: http://...

# Override the URL
export BUGPILOT_API_URL=https://your-bugpilot.example.com
\`\`\`

---

### \`Error: 401 Unauthorized — session expired\`

Your JWT has expired. The CLI automatically refreshes tokens, but if the refresh token has also expired (sessions last 30 days), you need to re-activate.

\`\`\`bash
bugpilot auth activate --license-key bp_YOUR_KEY
\`\`\`

---

### \`Error: 403 Forbidden — insufficient role\`

You don't have the required role for this action.

| Command | Required role |
|---------|--------------|
| \`bugpilot fix approve\` | \`approver\` |
| \`bugpilot auth whoami\` → admin routes | \`admin\` |

Contact your org admin to update your role.

---

## Backend / API Issues

### \`sqlalchemy.exc.OperationalError: could not connect to server\`

PostgreSQL is not reachable.

\`\`\`bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check the connection string
psql "$DATABASE_URL"

# For Docker Compose
docker compose ps postgres
docker compose logs postgres
\`\`\`

---

### \`alembic.util.exc.CommandError: Can't locate revision\`

The database has not been migrated.

\`\`\`bash
cd backend
alembic upgrade head
\`\`\`

---

### \`cryptography.fernet.InvalidToken\`

The \`FERNET_KEY\` in the environment doesn't match the key used to encrypt stored credentials. This happens if you rotated the key without re-encrypting stored data.

\`\`\`bash
# Check the key format
python3 -c "
from cryptography.fernet import Fernet
import base64, os
key = os.environ['FERNET_KEY'].encode()
# Should not raise:
Fernet(key)
print('Key is valid')
"
\`\`\`

If you have changed the key, you need to re-enter credentials for all configured connectors via the admin API.

---

### \`ValueError: SECURITY: Attempted to send non-redacted GraphSlice to LLM provider\`

This is a safety check — BugPilot is preventing raw (potentially sensitive) evidence from being sent to an LLM. This should not appear in normal use. If you see it:

1. Check that evidence collection is calling the redaction pipeline before passing data to the hypothesis engine
2. In tests, ensure \`GraphSlice.is_redacted=True\` when testing LLM-related code paths

---

### Pydantic validation error on startup

\`\`\`
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
\`\`\`

A required environment variable is missing. BugPilot will tell you which one. Common missing variables:

- \`DATABASE_URL\` — PostgreSQL connection string
- \`JWT_SECRET\` — must be at least 32 characters
- \`FERNET_KEY\` — must be a valid Fernet key (base64-encoded 32 bytes)

---

## Connector Issues

### \`Connector degraded: timeout after 45s\`

A connector didn't respond within the 45-second collection window.

**Check:**
1. Is the target system reachable from the BugPilot host?
   \`\`\`bash
   curl -I https://api.datadoghq.com/api/v1/validate -H "DD-API-KEY: $KEY"
   \`\`\`
2. Are credentials valid?
   \`\`\`bash
   curl http://localhost:8000/api/v1/admin/connectors/validate \\
     -H "Authorization: Bearer $TOKEN"
   \`\`\`
3. Is the network allowing outbound HTTPS from the container?

---

### \`401 Unauthorized\` from Datadog/Grafana connector

Credentials have expired or permissions are insufficient.

- **Datadog:** Verify \`DD-API-KEY\` and \`DD-APPLICATION-KEY\` in the Datadog portal. Check that the App key has \`logs_read_data\` and \`metrics_read\` scopes.
- **Grafana:** Check the service account token hasn't expired (Grafana → Administration → Service accounts).

---

### \`CloudWatch: SignatureDoesNotMatch\`

The AWS credentials are invalid or the request is being made too long after the timestamp in the signature.

\`\`\`bash
# Verify your credentials
aws sts get-caller-identity \\
  --access-key-id "$AWS_ACCESS_KEY_ID" \\
  --secret-access-key "$AWS_SECRET_ACCESS_KEY" \\
  --region us-east-1
\`\`\`

Ensure the BugPilot host's system clock is accurate (within 5 minutes of AWS time). Use NTP.

---

## Webhook Issues

### \`401 Unauthorized\` on webhook endpoint

The HMAC signature doesn't match. Common causes:

1. **Wrong secret** — The secret registered in BugPilot doesn't match the one configured in your monitoring platform.
2. **Encoding mismatch** — The payload is being modified in transit (e.g. by a proxy that normalises JSON whitespace). BugPilot computes the HMAC over the exact raw bytes received.
3. **Stale secret** — You rotated the secret in the monitoring platform but forgot to update BugPilot (or vice versa).

Use the dual-secret rotation feature to rotate without downtime.

---

### Webhook received but no investigation created

Check the webhook delivery logs:

\`\`\`bash
curl http://localhost:8000/api/v1/admin/webhooks/deliveries \\
  -H "Authorization: Bearer $ADMIN_TOKEN"
\`\`\`

Also check the structured logs:

\`\`\`bash
docker compose logs backend | grep webhook | jq '.'
\`\`\`

---

## Evidence / Hypothesis Issues

### \`⚠ Evidence from single source only — confidence capped at 40%\`

This is a warning, not an error. BugPilot has evidence from only one connector capability type. The hypothesis engine is working correctly but with less data.

**Fix:** Configure additional connectors (e.g. if you only have Datadog logs, add Datadog metrics, or configure GitHub for deployment data).

---

### No hypotheses generated

The hypothesis engine has minimum requirements before generating:
- At least 1 symptom node in the graph
- At least 1 service/component node
- At least 2 evidence items

Check evidence was collected:

\`\`\`bash
bugpilot evidence list INVESTIGATION_ID
\`\`\`

If evidence is empty, re-collect:

\`\`\`bash
bugpilot evidence collect INVESTIGATION_ID --since 2h
\`\`\`

---

## Performance Issues

### Slow evidence collection

Evidence collection runs concurrently across all connectors. A slow connector drags out the total time. Check which connector is slow:

\`\`\`bash
bugpilot evidence collect INVESTIGATION_ID --since 1h
# Look at per-connector latency in the output table
\`\`\`

If one connector is consistently slow, consider increasing its timeout or investigating the root cause on the source system.

---

### High database memory usage

BugPilot stores JSONB payloads in PostgreSQL. Run the retention purge to clean up old data:

\`\`\`bash
docker compose exec backend python3 -c "
import asyncio
from app.services.retention_service import RetentionService
..."
\`\`\`

---

## Getting Help

- **GitHub Issues:** https://github.com/skonlabs/bugpilot/issues
- **API Docs (local):** http://localhost:8000/docs
- **Health check:** \`curl http://localhost:8000/health/ready\`
- **Verbose logging:** Set \`LOG_LEVEL=debug\` in your environment`,
  },
};

export function getDocPage(slug: string): DocPage | undefined {
  return docsPages[slug];
}

export function getAdjacentPages(slug: string): { prev?: DocPage; next?: DocPage } {
  const allSlugs = docsCategories.flatMap((c) => c.items);
  const idx = allSlugs.indexOf(slug);
  return {
    prev: idx > 0 ? docsPages[allSlugs[idx - 1]] : undefined,
    next: idx < allSlugs.length - 1 ? docsPages[allSlugs[idx + 1]] : undefined,
  };
}
