# BugPilot Documentation

BugPilot is a CLI tool you download and run from your terminal (macOS or Windows). It connects to the BugPilot cloud service and your existing monitoring tools, collects evidence automatically, and uses a multi-pass engine (rule-based + graph correlation + AI synthesis) to generate ranked, actionable root cause hypotheses.

---

## Getting Started

| Guide | Description |
|-------|-------------|
| [Getting Started](./getting-started.md) | Download, install, and run your first investigation in 5 minutes |
| [Download the CLI](https://bugpilot.io/download) | Direct download for macOS and Windows |

---

## How-To Guides

| Guide | Description |
|-------|-------------|
| [Investigate an Incident](./how-to-investigate.md) | End-to-end walkthrough: alert → evidence → hypotheses → fix → close |
| [Configure Connectors](./connectors.md) | Datadog, Grafana, CloudWatch, GitHub, Kubernetes, PagerDuty |
| [Configure Webhooks](./how-to-webhooks.md) | Auto-triage from Datadog, Grafana, CloudWatch, PagerDuty alerts |
| [Configure LLM Providers](./how-to-configure-llm.md) | OpenAI, Anthropic, Azure OpenAI, Ollama |
| [Manage Users and Roles](./how-to-rbac.md) | RBAC roles, approval workflow, audit log |
| [Configure Data Retention](./how-to-retention.md) | Retention phases, compliance configurations |

---

## Reference

| Reference | Description |
|-----------|-------------|
| [CLI Reference](./cli-reference.md) | Complete documentation for every CLI command |
| [API Reference](./api-reference.md) | REST API endpoints, request/response schemas |
| [Architecture](./architecture.md) | System design, data flow, and key decisions |

---

## Self-Hosting (Advanced)

Run BugPilot on your own infrastructure instead of the cloud service.

| Guide | Description |
|-------|-------------|
| [Deployment Guide](./deployment.md) | Docker Compose, Kubernetes, and AWS ECS |
| [Developer Setup](./developer_setup.md) | Local dev environment for contributors |

---

## Support

| Resource | Link |
|----------|------|
| Issues | https://github.com/skonlabs/bugpilot/issues |
| API Docs (self-hosted) | http://localhost:8000/docs |
| Troubleshooting | [Troubleshooting Guide](./troubleshooting.md) |

---

## Platform at a Glance

```
Symptom → [Evidence Collection] → [Investigation Graph] → [Hypothesis Engine] → [Safe Actions]
               │                                                    │
               ▼                                                    ▼
    6 connectors, concurrent            Rule-based + Graph correlation + LLM synthesis
    45s timeout, graceful degradation   Dedup, rank, single-lane detection
```

**Tech stack:** Python 3.11, FastAPI, PostgreSQL 14, asyncpg, SQLAlchemy 2, Alembic, Pydantic v2, structlog, Prometheus, typer, Rich.
