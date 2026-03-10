# BugPilot Documentation

BugPilot is a developer CLI tool for debugging production incidents. Install it on your machine, connect it to your existing observability tools, and use it to find the root cause of issues — on demand when something breaks, or automatically when monitoring alerts fire.

---

## Two Modes

**On-Demand** — You notice something wrong. You open a terminal, describe the symptom, and BugPilot queries your connected data sources to pull relevant evidence. It analyses what it finds and surfaces ranked hypotheses with suggested next steps.

**Automatic** — Your monitoring tool fires an alert. BugPilot receives it via webhook, creates an investigation immediately, and starts collecting evidence. When you pick it up in the terminal, the evidence trail is already there.

---

## Get Started

| Guide | Description |
|-------|-------------|
| [Getting Started](./getting-started.md) | Install, activate, connect data sources, and run your first investigation |
| [CLI Reference](./cli-reference.md) | Every command, flag, and output format |

---

## Investigating Incidents

| Guide | Description |
|-------|-------------|
| [On-Demand Investigation](./how-to-investigate.md) | Investigate a live incident step by step |
| [Automatic Mode — Webhooks](./how-to-webhooks.md) | Auto-triage from Datadog, Grafana, CloudWatch, PagerDuty alerts |
| [Connect Data Sources](./connectors.md) | Datadog, Grafana, CloudWatch, GitHub, Kubernetes, PagerDuty |

---

## Administration

| Guide | Description |
|-------|-------------|
| [Manage Users and Roles](./how-to-rbac.md) | Team access, roles, and approval workflow |
| [Data Retention](./how-to-retention.md) | How long investigation data is stored |
| [AI Analysis Settings](./how-to-configure-llm.md) | Configure the AI engine for deeper hypothesis generation |

---

## Help

| Resource | |
|----------|--|
| [Troubleshooting](./troubleshooting.md) | Common problems and how to fix them |
| GitHub Issues | https://github.com/skonlabs/bugpilot/issues |
