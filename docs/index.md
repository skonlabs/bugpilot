# BugPilot Documentation

BugPilot is a CLI-first debugging and investigation platform. It connects to your existing monitoring tools, collects evidence automatically, and uses a multi-pass engine (rule-based + graph correlation + AI synthesis) to generate ranked, actionable root cause hypotheses.

---

## Getting Started

| Guide | Description |
|-------|-------------|
| [Getting Started](./getting-started.md) | Install, configure, and run your first investigation in 5 minutes |
| [Developer Setup](./developer_setup.md) | Full local dev environment setup for contributors |
| [Deployment](./deployment.md) | Docker Compose, Kubernetes, and AWS ECS deployment |

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

## Support

| Resource | Link |
|----------|------|
| Issues | https://github.com/skonlabs/bugpilot/issues |
| API Docs (local) | http://localhost:8000/docs |
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
