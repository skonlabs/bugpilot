# Getting Started with BugPilot

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

```bash
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
```

After `activate` you will see:

```
✓ License activated
  Org:        acme-corp
  Tier:       pro
  Seats:      10 / 10 available
  Expires:    2027-01-15
  Device ID:  dev_a3f8c...
```

You are now authenticated. The CLI stores credentials at `~/.config/bugpilot/credentials.json` (mode 600).

---

## Manual Installation (without Docker)

### 1. Database

```bash
createdb bugpilot
```

### 2. Backend

```bash
cd backend
pip install -e .
pip install -e ".[dev]"   # include test dependencies

# Set required environment variables
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/bugpilot"
export JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export FERNET_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. CLI

```bash
cd cli
pip install -e .
bugpilot --version
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL DSN (`postgresql+asyncpg://...`) |
| `JWT_SECRET` | Yes | — | 32+ byte hex secret for JWT signing |
| `FERNET_KEY` | Yes | — | Fernet key for encrypting connector credentials |
| `BUGPILOT_API_URL` | CLI only | `http://localhost:8000` | Backend URL the CLI connects to |
| `LOG_LEVEL` | No | `info` | `debug` / `info` / `warning` / `error` |
| `EVIDENCE_TTL_MINUTES` | No | `10080` (7 days) | Default evidence raw-payload TTL |
| `LLM_PROVIDER` | No | — | `openai` / `anthropic` / `azure_openai` / `ollama` |
| `OPENAI_API_KEY` | If using OpenAI | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | — | Anthropic API key |
| `AZURE_OPENAI_ENDPOINT` | If using Azure | — | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_API_KEY` | If using Azure | — | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | If using Azure | — | Deployment name |
| `OLLAMA_BASE_URL` | If using Ollama | `http://localhost:11434` | Ollama server URL |

---

## Your First Investigation

```bash
# Start a new investigation
bugpilot investigate create \
  --title "High error rate on payment-service" \
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
```

---

## Next Steps

- [CLI Reference](./cli-reference.md) — complete command documentation
- [Connector Setup](./connectors.md) — configure Datadog, Grafana, CloudWatch, etc.
- [Architecture Overview](./architecture.md) — how evidence, graphs, and hypotheses work
- [API Reference](./api-reference.md) — REST API for programmatic use
- [Deployment Guide](./deployment.md) — production deployment on Kubernetes / ECS
