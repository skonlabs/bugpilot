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

## Configuring Connectors

All connector credentials are stored in `~/.config/bugpilot/config.yaml` (permissions `600`). Credentials are never sent anywhere except the BugPilot service for evidence collection.

### Option A: Interactive wizard (recommended)

```bash
bugpilot connector add datadog
bugpilot connector add grafana
bugpilot connector add cloudwatch
bugpilot connector add github
bugpilot connector add kubernetes
bugpilot connector add pagerduty
```

Each command prompts for the required fields. Secret values are masked during input.

### Option B: Edit config.yaml directly

Generate a starter file:

```bash
bugpilot config init
```

Then edit `~/.config/bugpilot/config.yaml`. Use `${VAR_NAME}` to pull values from environment variables.

### Listing and removing connectors

```bash
bugpilot connector list          # show all configured connectors (secrets masked)
bugpilot connector remove datadog  # remove a connector
bugpilot connector test          # test all connectors
bugpilot connector test grafana  # test a specific connector
```

### Checking your config for errors

```bash
bugpilot config validate
bugpilot config show
```

---

## Datadog

**Capabilities:** Logs, Metrics, Traces, Alerts

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `api_key` | Yes | Datadog API key |
| `app_key` | Yes | Datadog Application key |
| `site` | No | Your Datadog site — default: `datadoghq.com` |

### Required permissions

Your API key must have:
- `logs_read_data`
- `metrics_read`
- `apm_read`
- `monitors_read`

### Config file example

```yaml
connectors:
  datadog:
    api_key: "${DD_API_KEY}"
    app_key: "${DD_APP_KEY}"
    site: "datadoghq.com"
```

---

## Grafana

**Capabilities:** Metrics, Alerts

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `url` | Yes | Your Grafana instance URL (e.g. `https://grafana.example.com`) |
| `api_token` | Yes | Service account token (Viewer role minimum) |
| `org_id` | No | Grafana org ID — default: `1` |
| `prometheus_datasource_uid` | No | UID of your Prometheus datasource (auto-discovered if omitted) |

### Creating a service account token

1. Go to **Administration → Service Accounts → Add service account**
2. Set role to **Viewer**
3. Click **Add token** — copy the token immediately

### Config file example

```yaml
connectors:
  grafana:
    url: "https://grafana.example.com"
    api_token: "${GRAFANA_TOKEN}"
    org_id: "1"
```

---

## AWS CloudWatch

**Capabilities:** Logs, Metrics, Alarms

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `aws_access_key_id` | Yes | IAM access key ID |
| `aws_secret_access_key` | Yes | IAM secret access key |
| `region` | Yes | AWS region (e.g. `us-east-1`) |
| `log_group_names` | No | List of CloudWatch log group names to query |

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

### Config file example

```yaml
connectors:
  cloudwatch:
    aws_access_key_id: "${AWS_ACCESS_KEY_ID}"
    aws_secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
    region: "us-east-1"
    log_group_names:
      - "/aws/lambda/payment-service"
      - "/ecs/checkout-service"
```

---

## GitHub

**Capabilities:** Code changes, Deployments

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `token` | Yes | Personal access token or GitHub App installation token |
| `org` | Yes | GitHub organization name |
| `repos` | No | List of repository names to watch |

### Token scopes required

- `repo:status`
- `read:repo_hook`

### Creating a personal access token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Generate new token with `repo:status` and `read:repo_hook` scopes

### Config file example

```yaml
connectors:
  github:
    token: "${GITHUB_TOKEN}"
    org: "mycompany"
    repos:
      - "payment-service"
      - "checkout-service"
```

---

## Kubernetes

**Capabilities:** Pod state, Events, Logs

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `api_server` | Yes | Kubernetes API server URL |
| `token` | Yes | Service account bearer token |
| `namespace` | No | Primary namespace — default: `production` |
| `extra_namespaces` | No | Additional namespaces to watch |
| `ca_cert_path` | No | Path to CA certificate for TLS verification |

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

### Config file example

```yaml
connectors:
  kubernetes:
    api_server: "https://kubernetes.example.com:6443"
    token: "${K8S_TOKEN}"
    namespace: "production"
    extra_namespaces:
      - "staging"
```

---

## PagerDuty

**Capabilities:** Incidents, Alerts

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `api_key` | Yes | PagerDuty REST API key (read-only) |
| `from_email` | Yes | Email address for API requests |
| `service_ids` | No | Limit to specific PagerDuty service IDs |

### Creating a read-only API key

1. Go to **PagerDuty → Integrations → API Access Keys**
2. Create a key with **Read-only** access

### Config file example

```yaml
connectors:
  pagerduty:
    api_key: "${PD_API_KEY}"
    from_email: "oncall@example.com"
    service_ids:
      - "PXXXXXX"
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
