# Connector Setup Guide

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

```bash
# Configure a Datadog connector
curl -X POST http://localhost:8000/api/v1/admin/connectors \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connector_type": "datadog",
    "env_label": "production",
    "credentials": {
      "api_key": "YOUR_DATADOG_API_KEY",
      "app_key": "YOUR_DATADOG_APP_KEY",
      "base_url": "https://api.datadoghq.com"
    }
  }'
```

Credentials are encrypted at rest using Fernet symmetric encryption before being stored in the database. The plaintext key is never persisted.

See [`fixtures/sample_configs/sample_connector_config.yaml`](../fixtures/sample_configs/sample_connector_config.yaml) for a complete example.

---

## Datadog

### Required credentials

| Field | Description |
|-------|-------------|
| `api_key` | Datadog API key (read-only is sufficient) |
| `app_key` | Datadog Application key |
| `base_url` | US: `https://api.datadoghq.com` · EU: `https://api.datadoghq.eu` |
| `service_tag` | (Optional) Default Datadog service tag filter |

### Capabilities

| Capability | API endpoint used |
|-----------|-------------------|
| `LOGS` | `POST /api/v2/logs/events/search` with `service:NAME` filter |
| `METRICS` | `GET /api/v1/query` — CPU user, request rate |
| `TRACES` | `GET /api/v2/spans/events` for the service |
| `ALERTS` | `GET /api/v1/monitor` filtered by service tag |

### Minimum Datadog permissions

- `logs_read_data`
- `metrics_read`
- `apm_read`
- `monitors_read`

---

## Grafana

### Required credentials

| Field | Description |
|-------|-------------|
| `base_url` | Grafana instance URL (e.g. `https://grafana.example.com`) |
| `api_token` | Service account token (Viewer role) |
| `datasource_uid` | (Optional) Prometheus datasource UID; auto-discovered if omitted |

### Capabilities

| Capability | API endpoint used |
|-----------|-------------------|
| `METRICS` | `/api/datasources/proxy/:uid/api/v1/query_range` |
| `ALERTS` | `/api/v1/provisioning/alert-rules` |

### Setup

1. Grafana → Administration → Service accounts → Create service account (Viewer role).
2. Generate a service account token.
3. Copy your Prometheus datasource UID from Administration → Data sources.

---

## AWS CloudWatch

### Required credentials

| Field | Description |
|-------|-------------|
| `access_key_id` | AWS access key ID |
| `secret_access_key` | AWS secret access key |
| `region` | AWS region (e.g. `us-east-1`) |
| `log_group_prefix` | (Optional) CloudWatch log group name or prefix |

### Capabilities

| Capability | AWS API used |
|-----------|--------------|
| `LOGS` | `StartQuery` + `GetQueryResults` (CloudWatch Insights) |
| `METRICS` | `GetMetricData` (CPUUtilization, RequestCount) |
| `ALERTS` | `DescribeAlarms` (state=ALARM) |

### Minimum IAM permissions

```json
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
```

> BugPilot uses manual SigV4 signing (no boto3) to keep the image minimal. For production, prefer an IAM role on your EC2/ECS instance.

---

## GitHub

### Required credentials

| Field | Description |
|-------|-------------|
| `token` | Personal access token or GitHub App installation token |
| `owner` | GitHub organisation or username |
| `repo` | Default repository name |

### Capabilities

| Capability | API endpoint used |
|-----------|-------------------|
| `CODE_CHANGES` | `GET /repos/{owner}/{repo}/commits` with since/until |
| `DEPLOYMENTS` | `GET /repos/{owner}/{repo}/deployments` |

### Minimum token scopes

- `repo:status` (read commit statuses)
- `read:repo_hook` (optional, deployment events)

> **Tip:** Pass `owner/repo` as the service name in `investigate create` to target a specific repository.

---

## Kubernetes

### Required credentials

| Field | Description |
|-------|-------------|
| `base_url` | API server URL (e.g. `https://k8s.example.com:6443`) |
| `token` | Service account bearer token |
| `namespace` | Namespace to query (default: `default`) |
| `ca_cert_pem` | (Optional) PEM CA cert for TLS verification |
| `verify_ssl` | `false` to skip TLS (not recommended in production) |

### Capabilities

| Capability | Kubernetes resources |
|-----------|---------------------|
| `INFRASTRUCTURE_STATE` | Pods, Nodes, Events (namespaced) |
| `DEPLOYMENTS` | `apps/v1` Deployments matching service label |

### Creating a read-only service account

```bash
kubectl create serviceaccount bugpilot-reader -n default

kubectl create clusterrole bugpilot-reader \
  --verb=get,list \
  --resource=pods,nodes,events,deployments

kubectl create clusterrolebinding bugpilot-reader \
  --clusterrole=bugpilot-reader \
  --serviceaccount=default:bugpilot-reader

# Get a long-lived token
kubectl create token bugpilot-reader -n default --duration=8760h
```

---

## PagerDuty

### Required credentials

| Field | Description |
|-------|-------------|
| `api_key` | PagerDuty REST API key (read-only) |
| `service_id` | (Optional) Filter incidents to one service |

### Capabilities

| Capability | API endpoint used |
|-----------|-------------------|
| `INCIDENTS` | `GET /incidents` filtered by service and date range |
| `ALERTS` | `GET /incidents/{id}/alerts` for each matching incident |

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

```
  grafana/metrics   —   degraded: connection timeout after 45s
```

---

## Validating Connector Connectivity

```bash
curl http://localhost:8000/api/v1/admin/connectors/validate \
  -H "Authorization: Bearer $TOKEN"

# [
#   {"connector_id":"c1d9...","type":"datadog","valid":true,"latency_ms":210},
#   {"connector_id":"a2f8...","type":"grafana","valid":false,"error":"401 Unauthorized"}
# ]
```

---

## Adding a Custom Connector

Subclass `BaseConnector` from `app.connectors.base`:

```python
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
```

Register it in `ConnectorType` enum (`app/models/all_models.py`) and add factory logic in the connector admin router.
