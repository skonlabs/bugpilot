# Deployment Guide

This guide covers production deployment of BugPilot. The architecture is stateless (API) + stateful (PostgreSQL), making it straightforward to run on any container platform.

---

## Docker Compose (Single-host / Staging)

The included `docker-compose.yml` is suitable for a single-host staging deployment.

```bash
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
```

### Generating required secrets

```bash
# JWT_SECRET (32+ byte hex)
python3 -c 'import secrets; print(secrets.token_hex(32))'

# FERNET_KEY
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@host/db` |
| `JWT_SECRET` | Yes | 64-char hex string for JWT signing |
| `FERNET_KEY` | Yes | Fernet key for credential encryption |
| `LOG_LEVEL` | No | `debug` / `info` / `warning` / `error` |
| `EVIDENCE_TTL_MINUTES` | No | Raw payload TTL (default: 10080 = 7 days) |
| `LLM_PROVIDER` | No | `openai` / `anthropic` / `azure_openai` / `ollama` |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Anthropic API key |
| `AZURE_OPENAI_ENDPOINT` | If using Azure | Azure resource endpoint |
| `AZURE_OPENAI_API_KEY` | If using Azure | Azure API key |
| `AZURE_OPENAI_DEPLOYMENT` | If using Azure | Deployment name |
| `OLLAMA_BASE_URL` | If using Ollama | Default: `http://localhost:11434` |

---

## Kubernetes

### Namespace and secrets

```bash
kubectl create namespace bugpilot

kubectl create secret generic bugpilot-secrets \
  --namespace bugpilot \
  --from-literal=DATABASE_URL="postgresql+asyncpg://bugpilot:$DB_PASS@postgres:5432/bugpilot" \
  --from-literal=JWT_SECRET="$JWT_SECRET" \
  --from-literal=FERNET_KEY="$FERNET_KEY" \
  --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY"
```

### Deployment manifest

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

### Running migrations as a Job

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

---

## AWS ECS (Fargate)

### Task definition highlights

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
```

---

## Database: PostgreSQL

### Recommended settings

```sql
-- Increase max connections for asyncpg pool
ALTER SYSTEM SET max_connections = 200;

-- Enable pg_stat_statements for query monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Recommended indexes (all created by migration 0001)
-- investigations(org_id, status)
-- evidence_items(investigation_id)
-- evidence_items(fetched_at)  -- for retention purge
-- audit_logs(org_id, occurred_at)
```

### Managed database options

| Platform | Service |
|----------|---------|
| AWS | RDS PostgreSQL 14+ or Aurora PostgreSQL |
| GCP | Cloud SQL for PostgreSQL |
| Azure | Azure Database for PostgreSQL |
| Self-hosted | PostgreSQL 14+ with asyncpg-compatible SSL |

Ensure `asyncpg` SSL mode is set correctly:

```
postgresql+asyncpg://user:pass@host/db?ssl=require
```

---

## Retention Purge Job

BugPilot's retention service must be called on a schedule. Add a cron job or scheduled task:

```bash
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
```

---

## Prometheus Scraping

Add BugPilot to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: bugpilot
    static_configs:
      - targets: ['bugpilot-api:8000']
    metrics_path: /metrics
    scrape_interval: 15s
```

### Recommended alerts

```yaml
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
```

---

## Security Checklist

Before going to production:

- [ ] `JWT_SECRET` is at least 32 bytes and stored in a secrets manager (not in `.env` files)
- [ ] `FERNET_KEY` is rotated regularly and stored in a secrets manager
- [ ] PostgreSQL is not publicly accessible — use a private subnet
- [ ] TLS is terminated at the load balancer (SSL certificate on ALB/nginx/ingress)
- [ ] Webhook secrets are rotated using the dual-secret grace window feature
- [ ] Log output (`/metrics`, `/health`) is not exposed publicly
- [ ] Database credentials use a least-privilege role (SELECT, INSERT, UPDATE, DELETE — no DDL)
- [ ] `LOG_LEVEL=info` in production (not `debug`, which may log request bodies)
- [ ] Org isolation tested — no cross-tenant queries possible through the API
