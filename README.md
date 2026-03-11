# BugPilot

BugPilot is a CLI-first developer tool for debugging and investigating production incidents. It connects to your observability stack, correlates signals across logs, metrics, and traces, and uses LLM-powered analysis to surface root-cause hypotheses and suggest remediation actions.

## Features

- **Incident triage** — open and track production incidents from the command line
- **Evidence collection** — pull logs, metrics, traces, and config diffs from connected sources
- **Hypothesis generation** — 6-pass pipeline (rule-based → graph correlation → historical reranking → LLM synthesis → deduplication → final ranking)
- **AI analysis** — ask questions, generate summaries, and compare against baselines
- **Action playbooks** — suggest and run remediation actions with approval gates
- **Export** — produce JSON or Markdown investigation reports
- **Webhook ingest** — receive alerts from Datadog, Grafana, CloudWatch, and PagerDuty

## Architecture

| Layer | Technology |
|---|---|
| CLI | Python / Typer |
| API | FastAPI + PostgreSQL |
| Analysis engine | Separate service (`BUGPILOT_ANALYSIS_URL`) |
| LLM providers | OpenAI, Anthropic, Azure OpenAI, Gemini, Ollama, OpenAI-compatible |

## Quick Start

```bash
pip install bugpilot

# Authenticate
bugpilot auth login

# Open an incident
bugpilot incident triage --title "High error rate on checkout service"

# Collect evidence
bugpilot evidence collect --source "datadog://logs?service=checkout&env=prod" -i <investigation-id>

# Generate hypotheses
bugpilot hypotheses list -i <investigation-id>

# Ask a question
bugpilot ask "What changed in the last 30 minutes?" -i <investigation-id>
```

## Documentation

Full documentation is in [`src/docs/`](src/docs/):

- [Getting Started](src/docs/getting-started.md)
- [CLI Reference](src/docs/cli-reference.md)
- [API Reference](src/docs/api-reference.md)
- [Architecture](src/docs/architecture.md)
- [How to Investigate](src/docs/how-to-investigate.md)
- [How to Configure LLM](src/docs/how-to-configure-llm.md)
- [Deployment](src/docs/deployment.md)
- [Data Retention](src/docs/how-to-retention.md)
- [Webhooks](src/docs/how-to-webhooks.md)
- [Connectors](src/docs/how-to-connectors.md)
- [RBAC](src/docs/how-to-rbac.md)

## Configuration

| Environment variable | Description |
|---|---|
| `BUGPILOT_API_URL` | BugPilot API base URL (default: `https://api.bugpilot.io`) |
| `BUGPILOT_ANALYSIS_URL` | Analysis engine URL |
| `BUGPILOT_TOKEN` | API authentication token |
| `BUGPILOT_INVESTIGATION` | Default investigation ID for all commands |
| `LLM_PROVIDER` | LLM provider (`openai`, `anthropic`, `azure_openai`, `gemini`, `ollama`, `openai_compatible`) |
| `LLM_API_KEY` | API key for the configured LLM provider |
| `LLM_MODEL` | Model name |
| `LLM_BASE_URL` | Base URL (for Ollama or OpenAI-compatible providers) |

## RBAC Roles

| Role | Permissions |
|---|---|
| `viewer` | Read-only access to investigations and evidence |
| `investigator` | Create and update investigations, collect evidence |
| `approver` | Approve and run medium/high-risk actions |
| `admin` | Full access including critical actions and user management |

## License

See [LICENSE](LICENSE).
