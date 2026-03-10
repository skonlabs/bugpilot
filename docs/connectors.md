# BugPilot Connectors

Connectors integrate BugPilot with external monitoring, logging, ticketing, and infrastructure systems.

## Supported Connectors

| Kind | Module | Category |
|------|--------|----------|
| `datadog` | `app/connectors/datadog/` | Monitoring + Logging + Tracing |
| `grafana` | `app/connectors/grafana/` | Monitoring + Alerting |
| `cloudwatch` | `app/connectors/cloudwatch/` | Cloud Monitoring |
| `github` | `app/connectors/github/` | Source Control |
| `kubernetes` | `app/connectors/kubernetes/` | Infrastructure |
| `pagerduty` | `app/connectors/pagerduty/` | Incident Management |

---

## Datadog Connector

### Capabilities

`LOGS` | `METRICS` | `TRACES` | `ALERTS`

### Required Credentials

| Field | Description | Where to find it |
|-------|-------------|-----------------|
| `api_key` | Datadog API key | Organization Settings → API Keys |
| `app_key` | Datadog application key | Organization Settings → Application Keys |
| `site` | Datadog site (default: `datadoghq.com`) | See [Datadog sites docs](https://docs.datadoghq.com/getting_started/site/) |

### API Endpoints Used

| Capability | Endpoint |
|-----------|----------|
| Validate | `GET /api/v1/validate` |
| LOGS | `POST /api/v2/logs/events/search` |
| METRICS | `GET /api/v1/query` |
| TRACES | `GET /api/v2/spans/events` |
| ALERTS | `GET /api/v1/monitor` |

### Rate Limit Behavior

Datadog enforces per-key rate limits. When a 429 response is received, the connector reads the `Retry-After` header and sleeps for the specified duration before retrying (up to `max_retries=3`). Exponential backoff with jitter applies when no `Retry-After` is present.

### Known Limitations

- Metrics endpoint (`/api/v1/query`) supports only a single query expression per request. Multiple metrics require multiple calls.
- Traces endpoint (`/api/v2/spans/events`) may not return traces older than 15 days on Datadog's retention plan.
- ALERTS endpoint (`/api/v1/monitor`) does not support time-range filtering; all monitors matching the service tag are returned and filtered client-side.

### Example Configuration

```yaml
connectors:
  datadog:
    api_key: "dd_api_key_..."
    app_key: "dd_app_key_..."
    site: "datadoghq.com"
```

---

## Grafana Connector

### Capabilities

`METRICS` | `ALERTS`

### Required Credentials

| Field | Description | Where to find it |
|-------|-------------|-----------------|
| `url` | Base URL of your Grafana instance | e.g., `https://grafana.example.com` |
| `api_token` | Service account token | Administration → Service Accounts → Add Token |
| `org_id` | Grafana organization ID (default: `1`) | Organization settings |

### Optional Configuration

| Field | Description |
|-------|-------------|
| `prometheus_datasource_uid` | UID of the Prometheus datasource to query. If not set, the connector auto-discovers the first Prometheus/Loki datasource. |

### API Endpoints Used

| Capability | Endpoint |
|-----------|----------|
| Validate | `GET /api/health` |
| METRICS | `GET /api/datasources/proxy/{uid}/api/v1/query_range` |
| ALERTS | `GET /api/v1/provisioning/alert-rules` |

### Rate Limit Behavior

Grafana does not enforce strict API rate limits by default. If Grafana is backed by a hosted cloud plan (Grafana Cloud), rate limits may apply. The connector applies standard exponential backoff on 429 responses.

### Known Limitations

- `ALERTS` endpoint (`/api/v1/provisioning/alert-rules`) returns all alert rules without time-range filtering. Rules are annotated with an `adaptation_note` in evidence metadata.
- `METRICS` via the Prometheus datasource proxy requires the datasource to have query access enabled. Read-only service accounts with `Viewer` role are sufficient.
- Loki log queries are not yet implemented (only Prometheus metrics proxy).

### Example Configuration

```yaml
connectors:
  grafana:
    url: "https://grafana.example.com"
    api_token: "glsa_..."
    org_id: 1
    prometheus_datasource_uid: "prometheus-prod"
```

---

## CloudWatch Connector

### Capabilities

`METRICS` | `ALERTS`

### Required Credentials

| Field | Description |
|-------|-------------|
| `aws_access_key_id` | AWS access key ID |
| `aws_secret_access_key` | AWS secret access key |
| `region` | AWS region (e.g., `us-east-1`) |

Alternatively, the connector respects the standard AWS credential chain (environment variables, instance profile, ECS task role) when credentials are not explicitly configured.

### Optional Configuration

| Field | Description |
|-------|-------------|
| `role_arn` | IAM role ARN to assume (for cross-account access) |
| `log_group_names` | List of CloudWatch Log Group names to query |

### Recommended IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "logs:DescribeLogGroups",
        "logs:FilterLogEvents",
        "logs:GetLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### Rate Limit Behavior

AWS SDK enforces service quotas. CloudWatch API calls are throttled at approximately 400 transactions per second (TPS). The connector uses exponential backoff on `ThrottlingException`.

### Known Limitations

- CloudWatch Logs Insights queries (complex analytics) are not yet implemented; only `FilterLogEvents` is used.
- CloudWatch metric resolution is limited to 1-minute granularity for standard metrics; high-resolution metrics (1-second) require a separate API call.
- Cross-region queries require instantiating a separate connector per region.

### Example Configuration

```yaml
connectors:
  cloudwatch:
    aws_access_key_id: "AKIAIOSFODNN7EXAMPLE"
    aws_secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    region: "us-east-1"
    log_group_names:
      - "/aws/lambda/payment-service"
      - "/ecs/checkout-service"
```

---

## GitHub Connector

### Capabilities

`CODE_CHANGES` | `DEPLOYMENTS`

### Required Credentials

| Field | Description |
|-------|-------------|
| `token` | GitHub personal access token or GitHub App installation token |
| `org` | GitHub organization name |

### Required Token Scopes

For a PAT: `repo:read` (for private repos) or `public_repo` (for public repos only).

For a GitHub App: `contents: read`, `deployments: read`, `pull_requests: read`.

### API Endpoints Used

| Capability | Endpoint |
|-----------|----------|
| Validate | `GET /user` or `GET /orgs/{org}` |
| CODE_CHANGES | `GET /repos/{owner}/{repo}/commits` |
| DEPLOYMENTS | `GET /repos/{owner}/{repo}/deployments` |

### Rate Limit Behavior

GitHub enforces 5,000 requests/hour for authenticated requests. The connector reads `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers. When remaining is 0, the connector sleeps until the reset time.

### Known Limitations

- The connector queries all repos in the org unless `repos` is explicitly configured. For organizations with hundreds of repos, explicit filtering is strongly recommended.
- GitHub Enterprise Server requires setting `api_base_url` to your GHE instance.
- Git blame and code search are not yet implemented.

### Example Configuration

```yaml
connectors:
  github:
    token: "ghp_..."
    org: "mycompany"
    repos:
      - "payment-service"
      - "checkout-service"
```

---

## Kubernetes Connector

### Capabilities

`INFRASTRUCTURE_STATE` | `LOGS`

### Required Credentials

| Field | Description |
|-------|-------------|
| `api_server` | Kubernetes API server URL |
| `token` | Service account bearer token |
| `namespace` | Primary namespace to query |

### Optional Configuration

| Field | Description |
|-------|-------------|
| `ca_cert_path` | Path to the cluster CA certificate |
| `kubeconfig_path` | Path to a kubeconfig file (alternative to token auth) |
| `extra_namespaces` | Additional namespaces to include |

### Required RBAC Permissions

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: bugpilot-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "events", "services", "endpoints", "namespaces"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
    verbs: ["get", "list"]
```

### Rate Limit Behavior

The Kubernetes API server does not enforce HTTP rate limits by default. However, large clusters may have `max-requests-inflight` limits. The connector uses standard exponential backoff on 429/503 responses.

### Known Limitations

- Pod log streaming (`LOGS` capability) reads up to 500 lines per pod tail. For full log aggregation, use the Datadog or Grafana Loki connector.
- Multi-cluster support requires one connector instance per cluster.
- Kubernetes metrics (CPU/memory) require the Metrics Server to be installed; raw cAdvisor metrics are not queried directly.

### Example Configuration

```yaml
connectors:
  kubernetes:
    api_server: "https://kubernetes.example.com:6443"
    token: "eyJhbGciOiJSUzI1NiJ9..."
    namespace: "production"
    extra_namespaces:
      - "staging"
```

---

## PagerDuty Connector

### Capabilities

`INCIDENTS` | `ALERTS`

### Required Credentials

| Field | Description |
|-------|-------------|
| `api_key` | PagerDuty REST API key (v2) |
| `from_email` | Sender email address (required by PagerDuty for write operations) |

### API Endpoints Used

| Capability | Endpoint |
|-----------|----------|
| Validate | `GET /abilities` |
| INCIDENTS | `GET /incidents` |
| ALERTS | `GET /alerts` |

### Rate Limit Behavior

PagerDuty enforces 960 requests/minute per API key. The connector reads `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers. On 429, the connector sleeps until the reset time.

### Known Limitations

- Incident filtering is by time range and service IDs only; complex alert routing logic is not mirrored.
- Webhook verification for inbound PagerDuty webhooks requires the `webhook_secret` to be configured in the webhook intake section (not the connector credentials).
- PagerDuty's free tier has limited API history; older incidents may not be accessible.

### Example Configuration

```yaml
connectors:
  pagerduty:
    api_key: "u+xxxxxxxxxxxxxxxxxxxx"
    from_email: "oncall@example.com"
    service_ids:
      - "PXXXXXX"
```

---

## Adding a Custom Connector

See the [architecture guide](./architecture.md#how-to-add-a-new-connector) for the complete step-by-step process.

Quick reference:

```python
from app.connectors.base import BaseConnector, ConnectorCapability, RawEvidenceItem, ValidationResult
from app.connectors.retry import async_retry
from datetime import datetime

class MyConnector(BaseConnector):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def capabilities(self) -> list[ConnectorCapability]:
        return [ConnectorCapability.LOGS, ConnectorCapability.METRICS]

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def validate(self) -> ValidationResult:
        # Test connectivity; return ValidationResult(is_valid=True/False, ...)
        ...

    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        if capability == ConnectorCapability.LOGS:
            return await self._fetch_logs(service, since, until, limit)
        return []  # Always return [] for unsupported capabilities, never raise
```

## Connector Credential Security

Connector credentials are **never stored in plaintext**. They are encrypted using
[Fernet symmetric encryption](https://cryptography.io/en/latest/fernet/) before storage.

The encryption key is configured via the `FERNET_KEY` environment variable. If not set,
a new key is generated on each startup (use only for development — all credentials will be
unreadable after restart).
