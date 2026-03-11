# Self-Hosting BugPilot

> **Note:** This guide is for teams that want to run BugPilot on their own infrastructure. If you are using the hosted service at bugpilot.io, you do not need this guide — just [download the CLI](./getting-started.md) and activate it.

BugPilot's backend is a stateless FastAPI service backed by PostgreSQL, making it straightforward to deploy on any container platform.

---

## Prerequisites

- PostgreSQL 14+
- Docker and Docker Compose (for the quick start)
- A Fernet key and JWT secret (generated below)
- Optional: an LLM API key (OpenAI, Anthropic, Azure OpenAI, Gemini, Ollama, or OpenAI-compatible)

---

## Generating Required Secrets

Before deploying, generate the two required secrets:

```bash
# JWT_SECRET — 64-character hex string
python3 -c 'import secrets; print(secrets.token_hex(32))'

# FERNET_KEY — symmetric encryption key for connector credentials
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Store these in a secrets manager (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault, etc.). Do not commit them to source control.

---

## Docker Compose (Single Host / Staging)

```bash
# 1. Set environment variables
export DATABASE_URL="postgresql+asyncpg://bugpilot:yourpassword@postgres:5432/bugpilot"
export JWT_SECRET="your-64-char-hex-string"
export FERNET_KEY="your-fernet-key"

# 2. Start the services
docker compose up -d

# 3. Apply database migrations
docker compose exec backend alembic upgrade head

# 4. Verify the service is healthy
curl http://localhost:8000/health
# {"status": "ok"}
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | `postgresql+asyncpg://user:pass@host/db` |
| `JWT_SECRET` | Yes | — | 64-char hex string for JWT signing |
| `FERNET_KEY` | Yes | — | Fernet key for encrypting connector credentials |
| `LOG_LEVEL` | No | `info` | `debug` / `info` / `warning` / `error` |
| `EVIDENCE_TTL_MINUTES` | No | `10080` | Raw payload TTL (default: 7 days) |
| `LLM_PROVIDER` | No | — | `openai` / `anthropic` / `azure_openai` / `gemini` / `ollama` / `openai_compatible` |
| `LLM_API_KEY` | If using a cloud LLM | — | API key for the configured LLM provider |
| `LLM_MODEL` | No | provider default | Model name override |
| `LLM_BASE_URL` | If using Azure / Ollama / openai_compatible | — | Base URL for the LLM endpoint |
| `LLM_AZURE_DEPLOYMENT` | If using Azure OpenAI | — | Azure deployment name |
| `LLM_AZURE_API_VERSION` | If using Azure OpenAI | — | Azure API version |

---

## Kubernetes

### Namespace and Secrets

```bash
kubectl create namespace bugpilot

kubectl create secret generic bugpilot-secrets \
  --namespace bugpilot \
  --from-literal=DATABASE_URL="postgresql+asyncpg://bugpilot:$DB_PASS@postgres:5432/bugpilot" \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=FERNET_KEY="$FERNET_KEY"
```

### API Deployment

```yaml
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
```

### Migration Job

```yaml
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
```

### Daily Retention Purge CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bugpilot-retention
  namespace: bugpilot
spec:
  schedule: "0 2 * * *"
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
```

---

## AWS ECS (Fargate)

```json
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
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/DATABASE_URL"},
        {"name": "JWT_SECRET",   "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/JWT_SECRET"},
        {"name": "FERNET_KEY",   "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/FERNET_KEY"}
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

---

## PostgreSQL

### Recommended Settings

```sql
-- Increase max connections for asyncpg connection pool
ALTER SYSTEM SET max_connections = 200;

-- Enable query monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### Managed Database Options

| Platform | Recommended service |
|----------|-------------------|
| AWS | RDS PostgreSQL 14+ or Aurora PostgreSQL |
| GCP | Cloud SQL for PostgreSQL |
| Azure | Azure Database for PostgreSQL |
| Self-hosted | PostgreSQL 14+ |

Ensure the connection string uses asyncpg SSL mode for managed databases:

```
postgresql+asyncpg://user:pass@host/db?ssl=require
```

---

## Prometheus Scraping

```yaml
scrape_configs:
  - job_name: bugpilot
    static_configs:
      - targets: ['bugpilot-api:8000']
    metrics_path: /metrics
    scrape_interval: 15s
```

---

## Pointing the CLI at Your Self-Hosted Instance

When using a self-hosted backend, set the API URL before activating:

```bash
export BUGPILOT_API_URL=https://your-bugpilot-instance.example.com
bugpilot auth activate --key bp_YOUR_LICENSE_KEY
```

Or pass it per-command:

```bash
bugpilot --api-url https://your-bugpilot-instance.example.com auth whoami
```

---

## Security Checklist

Before going to production:

- [ ] `JWT_SECRET` is at least 32 bytes and stored in a secrets manager (not in `.env` files)
- [ ] `FERNET_KEY` is stored in a secrets manager and rotated on a schedule
- [ ] PostgreSQL is not publicly accessible — use a private subnet or VPC
- [ ] TLS is terminated at the load balancer (ALB / nginx / ingress controller)
- [ ] Webhook secrets are rotated periodically using the dual-secret grace window
- [ ] `/metrics` and `/health` endpoints are not publicly accessible
- [ ] Database credentials use a least-privilege role (SELECT, INSERT, UPDATE, DELETE only — no DDL)
- [ ] `LOG_LEVEL=info` in production (not `debug`, which may log request bodies)
- [ ] Org isolation verified — no cross-tenant queries are possible through the API
