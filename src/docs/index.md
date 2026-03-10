# BugPilot Documentation

BugPilot is a CLI tool you download and run from your terminal (macOS or Windows). It connects to the BugPilot cloud service and your existing monitoring tools, collects evidence from logs, metrics, traces, and deployments, and uses a multi-pass AI engine to generate ranked, actionable root cause hypotheses.

---

## Getting Started

| Guide | Description |
|-------|-------------|
| [Getting Started](./getting-started.md) | Download, install, activate, and run your first investigation |
| [CLI Reference](./cli-reference.md) | Every command, flag, and output format |

---

## How-To Guides

| Guide | Description |
|-------|-------------|
| [Investigate an Incident](./how-to-investigate.md) | End-to-end walkthrough: alert → evidence → hypotheses → fix → close |
| [Configure Connectors](./connectors.md) | Connect Datadog, Grafana, CloudWatch, GitHub, Kubernetes, PagerDuty |
| [Configure Webhooks](./how-to-webhooks.md) | Auto-triage from incoming monitoring alerts |
| [Configure LLM Providers](./how-to-configure-llm.md) | OpenAI, Anthropic, Azure OpenAI, Ollama |
| [Manage Users and Roles](./how-to-rbac.md) | RBAC roles, approval workflow, audit log |
| [Configure Data Retention](./how-to-retention.md) | Retention phases and compliance configurations |

---

## Reference

| Reference | Description |
|-----------|-------------|
| [API Reference](./api-reference.md) | REST API endpoints, request/response schemas |
| [Architecture](./architecture.md) | System design, data flow, and key decisions |
| [Troubleshooting](./troubleshooting.md) | Common problems and how to fix them |

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
| Troubleshooting | [Troubleshooting Guide](./troubleshooting.md) |

---

## How It Works

```
Alert / Symptom
      │
      ▼
[Investigation Created]
      │
      ▼
[Evidence Collection] ──── Datadog · Grafana · CloudWatch
      │                     GitHub · Kubernetes · PagerDuty
      ▼
[Investigation Graph] ──── Causal links, timeline, service map
      │
      ▼
[Hypothesis Engine]  ──── Rule-based → Graph correlation
      │                   → Historical reranking → LLM synthesis
      ▼
[Ranked Hypotheses]  ──── Confidence scores, evidence citations
      │
      ▼
[Safe Actions]       ──── Risk-rated, approval-gated, dry-run capable
```
