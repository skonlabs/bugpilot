# Connector Setup Guide

BugPilot collects evidence from your existing observability tools through **connectors**. Each connector maps to a monitoring platform and exposes one or more **capabilities** (logs, metrics, traces, alerts, incidents, deployments, infrastructure state, code changes).

The more connectors you configure, the better BugPilot's hypotheses will be. Single-source investigations are marked as **single-lane** and confidence scores are capped at 40% until additional sources are added.

---

## Supported Connectors

| Connector | Capabilities | Auth method |
|-----------|-------------|-------------|
| Datadog | Logs, Metrics, Traces, Alerts | API key + App key |
| Grafana | Metrics, Alerts | Service account token |
| AWS CloudWatch | Logs, Metrics, Alarms | IAM access key + secret |
| GitHub | Code changes, Deployments | Personal access token or GitHub App |
| Kubernetes | Pod state, Events, Logs | Service account bearer token |
| PagerDuty | Incidents, Alerts | REST API key |

---

## Adding a Connector

Connectors are configured by your admin in the dashboard under **Settings → Connectors**. Credentials are encrypted at rest using Fernet encryption and never returned in API responses.

You can also manage connectors via the API:

```bash
# Add a connector
curl -X POST https://api.bugpilot.io/api/v1/admin/connectors \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connector_type": "datadog",
    "env_label": "production",
    "credentials": { ... }
  }'

# List configured connectors
curl https://api.bugpilot.io/api/v1/admin/connectors \
  -H "Authorization: Bearer $TOKEN"

# Validate all connectors
curl https://api.bugpilot.io/api/v1/admin/connectors/validate \
  -H "Authorization: Bearer $TOKEN"
```

---

## Datadog

**Capabilities:** Logs, Metrics, Traces, Alerts

### Credentials

| Field | Description |
|-------|-------------|
| `api_key` | Datadog API key |
| `app_key` | Datadog Application key |
| `site` | Your Datadog site: `datadoghq.com`, `datadoghq.eu`, `us3.datadoghq.com` |

### Required permissions

Your API key must have:
- `logs_read_data`
- `metrics_read`
- `apm_read`
- `monitors_read`

### Example credentials object

```json
{
  "api_key": "your_datadog_api_key",
  "app_key": "your_datadog_app_key",
  "site": "datadoghq.com"
}
```

---

## Grafana

**Capabilities:** Metrics, Alerts

### Credentials

| Field | Description |
|-------|-------------|
| `url` | Your Grafana instance URL (e.g. `https://grafana.example.com`) |
| `api_token` | Service account token (Viewer role) |
| `org_id` | Grafana org ID (default: 1) |
| `prometheus_datasource_uid` | UID of your Prometheus datasource (auto-discovered if omitted) |

### Creating a service account token

1. Go to **Administration → Service Accounts → Add service account**
2. Set role to **Viewer**
3. Click **Add token** — copy the token immediately

### Example credentials object

```json
{
  "url": "https://grafana.example.com",
  "api_token": "glsa_example_token",
  "org_id": 1
}
```

---

## AWS CloudWatch

**Capabilities:** Logs, Metrics, Alarms

### Credentials

| Field | Description |
|-------|-------------|
| `aws_access_key_id` | IAM access key ID |
| `aws_secret_access_key` | IAM secret access key |
| `region` | AWS region (e.g. `us-east-1`) |
| `log_group_names` | List of CloudWatch log group names to query |
| `role_arn` | (Optional) IAM role ARN to assume |

### Required IAM permissions

```json
{
  "Effect": "Allow",
  "Action": [
    "logs:StartQuery",
    "logs:GetQueryResults",
    "logs:DescribeLogGroups",
    "cloudwatch:GetMetricData",
    "cloudwatch:DescribeAlarms"
  ],
  "Resource": "*"
}
```

### Example credentials object

```json
{
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "region": "us-east-1",
  "log_group_names": [
    "/aws/lambda/payment-service",
    "/ecs/checkout-service"
  ]
}
```

---

## GitHub

**Capabilities:** Code changes, Deployments

### Credentials

| Field | Description |
|-------|-------------|
| `token` | Personal access token or GitHub App installation token |
| `org` | GitHub organization name |
| `repos` | List of repository names to watch |
| `api_base_url` | (Optional) GitHub Enterprise base URL |

### Token scopes required

- `repo:status`
- `read:repo_hook`

### Creating a personal access token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Generate new token with `repo:status` and `read:repo_hook` scopes

### Example credentials object

```json
{
  "token": "ghp_example_token",
  "org": "mycompany",
  "repos": ["payment-service", "checkout-service", "auth-service"]
}
```

---

## Kubernetes

**Capabilities:** Pod state, Events, Logs

### Credentials

| Field | Description |
|-------|-------------|
| `api_server` | Kubernetes API server URL |
| `token` | Service account bearer token |
| `namespace` | Primary namespace to watch |
| `extra_namespaces` | (Optional) Additional namespaces |
| `ca_cert_path` | (Optional) Path to CA certificate |

### Creating a service account

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: bugpilot
  namespace: production
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: bugpilot-reader
rules:
- apiGroups: ["", "apps"]
  resources: ["pods", "nodes", "events", "deployments"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: bugpilot-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: bugpilot-reader
subjects:
- kind: ServiceAccount
  name: bugpilot
  namespace: production
```

Get the token:

```bash
kubectl create token bugpilot -n production
```

### Example credentials object

```json
{
  "api_server": "https://kubernetes.example.com:6443",
  "token": "eyJhbGciOiJSUzI1NiJ9...",
  "namespace": "production",
  "extra_namespaces": ["staging"]
}
```

---

## PagerDuty

**Capabilities:** Incidents, Alerts

### Credentials

| Field | Description |
|-------|-------------|
| `api_key` | PagerDuty REST API key (read-only) |
| `from_email` | Email address for API requests |
| `service_ids` | (Optional) Limit to specific PagerDuty service IDs |

### Creating a read-only API key

1. Go to **PagerDuty → Integrations → API Access Keys**
2. Create a key with **Read-only** access

### Example credentials object

```json
{
  "api_key": "u+xxxxxxxxxxxxxxxxxxxx",
  "from_email": "oncall@example.com",
  "service_ids": ["PXXXXXX", "PYYYYYY"]
}
```

---

## Connection Behaviour

| Setting | Value |
|---------|-------|
| Request timeout per connector | 30 seconds |
| Max collection time per connector | 45 seconds |
| Retry on HTTP status | 429, 500, 502, 503, 504 |
| Max retry attempts | 3 |
| Retry backoff | Exponential with jitter |

If a connector times out or errors, BugPilot marks it **degraded** for that run and continues with the remaining connectors. Results are partial rather than blocked.

---

## Validating Connectors

After adding connectors, validate all credentials are working:

```bash
curl https://api.bugpilot.io/api/v1/admin/connectors/validate \
  -H "Authorization: Bearer $TOKEN"
```

Returns a per-connector status: `ok`, `degraded`, or `error` with a message.
