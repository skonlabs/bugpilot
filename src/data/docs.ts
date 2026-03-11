export interface DocPage {
  slug: string;
  title: string;
  category: string;
  content: string;
}

export const docsCategories = [
  { label: "Getting Started", items: ["introduction", "getting-started"] },
  { label: "Investigating Incidents", items: ["how-to-investigate", "webhooks", "connectors"] },
  { label: "Configuration", items: ["llm-providers"] },
  { label: "Administration", items: ["rbac", "data-retention"] },
  { label: "Reference", items: ["cli-reference", "api-reference", "architecture"] },
  { label: "Self-Hosting", items: ["deployment", "developer-setup"] },
  { label: "Support", items: ["troubleshooting"] },
];

export const docsPages: Record<string, DocPage> = {
  introduction: {
    slug: "introduction",
    title: "Introduction",
    category: "Getting Started",
    content: `# BugPilot Documentation

BugPilot is a developer CLI tool for debugging production incidents. Install it on your machine, connect it to your existing observability tools, and use it to find the root cause of issues — on demand when something breaks, or automatically when monitoring alerts fire.

---

## Two Modes

**On-Demand** — You notice something wrong. You open a terminal, describe the symptom, and BugPilot queries your connected data sources to pull relevant evidence. It analyses what it finds and surfaces ranked hypotheses with suggested next steps.

**Automatic** — Your monitoring tool fires an alert. BugPilot receives it via webhook, creates an investigation immediately, and starts collecting evidence. When you pick it up in the terminal, the evidence trail is already there.

---

## Get Started

| Guide | Description |
|-------|-------------|
| [Getting Started](/docs/getting-started) | Install, activate, connect data sources, and run your first investigation |
| [CLI Reference](/docs/cli-reference) | Every command, flag, and output format |
| [API Reference](/docs/api-reference) | REST API endpoints, request/response shapes, authentication |

---

## Investigating Incidents

| Guide | Description |
|-------|-------------|
| [On-Demand Investigation](/docs/how-to-investigate) | Investigate a live incident step by step |
| [Automatic Mode — Webhooks](/docs/webhooks) | Auto-triage from Datadog, Grafana, CloudWatch, PagerDuty alerts |
| [Connect Data Sources](/docs/connectors) | Datadog, Grafana, CloudWatch, GitHub, Kubernetes, PagerDuty |

---

## Administration

| Guide | Description |
|-------|-------------|
| [Manage Users and Roles](/docs/rbac) | Team access, roles, and approval workflow |
| [Data Retention](/docs/data-retention) | How long investigation data is stored |
| [AI Analysis Settings](/docs/llm-providers) | Configure the AI engine for deeper hypothesis generation |
| [Deployment](/docs/deployment) | Self-host BugPilot on Kubernetes, ECS, or Docker Compose |
| [Architecture](/docs/architecture) | System design, data model, and security overview |

---

## Help

| Resource | |
|----------|--|
| [Troubleshooting](/docs/troubleshooting) | Common problems and how to fix them |
| GitHub Issues | https://github.com/skonlabs/bugpilot/issues |`,
  },

  "getting-started": {
    slug: "getting-started",
    title: "Getting Started",
    category: "Getting Started",
    content: `# Getting Started with BugPilot

BugPilot is a CLI tool that helps you debug production incidents. You install it on your machine, connect it to your observability tools, and use it to find root causes — either on demand when something breaks, or automatically when alerts fire.

---

## Step 1: Register

Go to [bugpilot.io](https://bugpilot.io) and create an account. After registration, copy your **license key** and **API secret** from the credentials page.

---

## Step 2: Install the CLI

Choose your operating system:

### macOS (Intel & Apple Silicon, macOS 12+)

**Homebrew (recommended):**

\`\`\`bash
brew install bugpilot/tap/bugpilot
\`\`\`

**Installer package:**

Download the \`.pkg\` file from [bugpilot.io/download](https://bugpilot.io/download), open it, and follow the on-screen steps.

### Windows (64-bit, Windows 10+)

**Scoop:**

\`\`\`powershell
scoop install bugpilot
\`\`\`

**Installer:**

Download the \`.msi\` file from [bugpilot.io/download](https://bugpilot.io/download), run it, and follow the prompts.

### Confirm the install

Open a new terminal and run:

\`\`\`bash
bugpilot --version
\`\`\`

---

## Step 3: Activate

Activation links the CLI to your account. The first time you run this command, BugPilot displays its Terms of Service — you must accept them to proceed.

\`\`\`bash
bugpilot auth activate --key YOUR_LICENSE_KEY --secret YOUR_API_SECRET
\`\`\`

You will be prompted to accept the Terms of Service and enter your email:

\`\`\`
┌─ Terms of Service ───────────────────────────────────────────┐
│ BugPilot Terms of Service                                     │
│                                                               │
│ By activating BugPilot you agree to the following:           │
│   1. BugPilot accesses your monitoring data only with the    │
│      credentials you explicitly provide.                      │
│   ...                                                         │
│                                                               │
│ Full Terms: https://bugpilot.io/terms                        │
└───────────────────────────────────────────────────────────────┘

Do you accept the Terms of Service? [y/N]: y

✓ Terms of Service accepted.

Enter your email address: alice@acme.com

✓ BugPilot activated!

Next steps:
  1. Set up a connector   bugpilot connector add datadog
  2. Test connectivity    bugpilot connector test
  3. Start investigating  bugpilot incident triage "..."
\`\`\`

BugPilot stores your session at \`~/.config/bugpilot/credentials.json\` (\`600\` permissions). You only need to activate once per machine.

Check who you're logged in as at any time:

\`\`\`bash
bugpilot auth whoami
\`\`\`

---

## Step 4: Connect Your Data Sources

BugPilot reads connector credentials from \`~/.config/bugpilot/config.yaml\`. There are two ways to configure it:

### Option A: Interactive wizard (recommended)

The \`connector add\` command walks you through each required field for the connector type you choose:

\`\`\`bash
bugpilot connector add datadog
bugpilot connector add grafana
bugpilot connector add cloudwatch
bugpilot connector add github
bugpilot connector add kubernetes
bugpilot connector add pagerduty
\`\`\`

Example:

\`\`\`
Configure datadog connector

  API Key: ••••••••••••••••••••
  Application Key: ••••••••••••••••••••
  Site (e.g. datadoghq.com) [datadoghq.com]:

✓ Connector 'datadog' saved to ~/.config/bugpilot/config.yaml
i Run 'bugpilot connector test' to verify connectivity.
\`\`\`

### Option B: Edit the config file directly

Create a starter config with all connector templates:

\`\`\`bash
bugpilot config init
\`\`\`

Then open \`~/.config/bugpilot/config.yaml\` in your editor and fill in your credentials. You can use \`\${VAR_NAME}\` syntax to read values from environment variables:

\`\`\`yaml
connectors:
  datadog:
    api_key: "\${DD_API_KEY}"
    app_key: "\${DD_APP_KEY}"
    site: "datadoghq.com"
  grafana:
    url: "https://grafana.example.com"
    api_token: "\${GRAFANA_TOKEN}"
    org_id: "1"
\`\`\`

### Verify connectivity

\`\`\`bash
bugpilot connector test
\`\`\`

\`\`\`
  Testing datadog...  ✓ OK
  Testing grafana...  ✓ OK
\`\`\`

| Connector | Data BugPilot can access |
|-----------|--------------------------|
| **Datadog** | Logs, metrics, traces, monitor alerts |
| **Grafana** | Metrics, alert notifications |
| **AWS CloudWatch** | Logs, metrics, alarms |
| **GitHub** | Commits, deployments, pull requests |
| **Kubernetes** | Pod status, events, logs |
| **PagerDuty** | Incident and alert history |

See [Connect Data Sources](/docs/connectors) for required permissions and field details for each platform.

---

## Step 5: Investigate

BugPilot has two usage modes:

### On-Demand

When you notice an issue, open a terminal and describe what you're seeing. BugPilot queries your connected sources, builds a picture of what happened, and tells you what it thinks the root cause is.

\`\`\`bash
# Start an investigation
bugpilot incident triage "Payment service errors spiking" \\
  --symptom "HTTP 5xx rate above 5% since 14:31 UTC" \\
  --severity critical \\
  --service payment-service

# Attach evidence you've collected
bugpilot evidence collect \\
  --investigation-id inv_7f3a2b \\
  --label "error logs" \\
  --kind log_snapshot \\
  --source "datadog://logs?service=payment-service&env=prod" \\
  --summary "NullPointerException at UserService.java:142, started 14:31 UTC"

# See what BugPilot thinks the root cause is
bugpilot hypotheses list --investigation-id inv_7f3a2b

# When resolved, close the investigation
bugpilot investigate close inv_7f3a2b
\`\`\`

See [On-Demand Investigation](/docs/how-to-investigate) for the full workflow.

### Automatic

Set up webhooks so that when your monitoring tool fires an alert, BugPilot automatically creates an investigation. You open the terminal to find it already has evidence collected.

\`\`\`bash
# Check what's waiting for you
bugpilot investigate list --status open

# Pick up an auto-created investigation
bugpilot incident status inv_7f3a2b
\`\`\`

See [Automatic Mode — Webhooks](/docs/webhooks) to set this up.

---

## Next Steps

- [On-Demand Investigation](/docs/how-to-investigate) — full incident walkthrough
- [Automatic Mode — Webhooks](/docs/webhooks) — auto-create investigations from alerts
- [Connect Data Sources](/docs/connectors) — connector setup for each platform
- [CLI Reference](/docs/cli-reference) — every command and flag`,
  },

  "how-to-investigate": {
    slug: "how-to-investigate",
    title: "Investigate an Incident",
    category: "Investigating Incidents",
    content: `# How to Investigate an Incident with BugPilot

This guide walks through a realistic incident from alert to resolution.

---

## Scenario

At 14:31 UTC your monitoring fires: **payment-service HTTP 5xx rate > 5%**. You open a terminal.

---

## Step 1: Open an Investigation

Create an investigation to anchor all evidence and hypotheses to this incident.

\`\`\`bash
bugpilot investigate create "HTTP 5xx spike on payment-service" \\
  --symptom "5xx rate above 5% since 14:31 UTC, ~847 affected requests" \\
  --severity critical
\`\`\`

\`\`\`
✓ Created  inv_7f3a2b
  Title:    HTTP 5xx spike on payment-service
  Severity: critical
  Status:   open
\`\`\`

**Shortcut:** Use \`bugpilot incident triage\` when you want to create the investigation and immediately record the initial alert in one step:

\`\`\`bash
bugpilot incident triage "HTTP 5xx spike on payment-service" \\
  --symptom "5xx rate above 5% since 14:31 UTC" \\
  --severity critical \\
  --service payment-service
\`\`\`

---

## Step 2: Add Evidence

Evidence items are normalized snapshots — log excerpts, metric summaries, config diffs, deployment events — that you attach to the investigation. The more evidence from different sources, the higher the confidence in hypotheses.

The \`--source\` option takes a **URI** that identifies the origin of the evidence. The scheme names the system (e.g. \`datadog://\`, \`github://\`) and query parameters narrow the scope.

\`\`\`bash
# Log snapshot from Datadog
bugpilot evidence collect \\
  --investigation-id inv_7f3a2b \\
  --label "payment-service error logs" \\
  --kind log_snapshot \\
  --source "datadog://logs?service=payment-service&env=prod" \\
  --summary "47 NullPointerException at UserService.java:142 starting 14:31 UTC. user.preferences was null."

# Deployment event from GitHub
bugpilot evidence collect \\
  --investigation-id inv_7f3a2b \\
  --label "deployment at 14:23 UTC" \\
  --kind config_diff \\
  --source "github://deployments?repo=acme/payment-service&ref=a3f8c2d" \\
  --summary "Commit a3f8c2d by alice: 'Update Stripe SDK v4'. Merged and deployed at 14:23 UTC — 8 minutes before errors began."

# Memory metric snapshot
bugpilot evidence collect \\
  --investigation-id inv_7f3a2b \\
  --label "heap memory spike" \\
  --kind metric_snapshot \\
  --source "datadog://metrics?metric=system.mem.pct_usable&service=payment-service" \\
  --summary "Heap memory rose from 60% to 92% on payment-service pod-3 between 14:23 and 14:31 UTC."
\`\`\`

List what you've added:

\`\`\`bash
bugpilot evidence list --investigation-id inv_7f3a2b
\`\`\`

\`\`\`
  ID          LABEL                         KIND             SOURCE    ADDED
  ev_9c1d3e   payment-service error logs    log_snapshot     datadog   1m ago
  ev_a2b4f1   deployment at 14:23 UTC       config_diff      github    45s ago
  ev_f7d2c3   heap memory spike             metric_snapshot  datadog   20s ago
\`\`\`

**Evidence kinds:** \`log_snapshot\` · \`metric_snapshot\` · \`trace\` · \`event\` · \`config_diff\` · \`topology\` · \`custom\`

---

## Step 3: Review Hypotheses

BugPilot generates hypotheses automatically as evidence is added. The hypothesis engine runs a multi-pass pipeline: rule-based pattern matching → graph correlation → historical reranking → LLM synthesis (when an LLM provider is configured).

\`\`\`bash
bugpilot hypotheses list --investigation-id inv_7f3a2b
\`\`\`

\`\`\`
  RANK  HYPOTHESIS                              CONFIDENCE  STATUS   SOURCE
   1    Bad deployment introduced regression    72%         active   rule
   2    Memory exhaustion (OOMKill risk)        58%         active   rule
   3    Upstream dependency degradation         31%         active   graph
\`\`\`

To add a hypothesis manually — for a theory from the team:

\`\`\`bash
bugpilot hypotheses create \\
  --investigation-id inv_7f3a2b \\
  "Stripe SDK v4 changed preferences API contract" \\
  --confidence 0.65 \\
  --reasoning "SDK upgrade changed how user.preferences is hydrated, causing NPE on first call" \\
  --evidence ev_9c1d3e \\
  --evidence ev_a2b4f1
\`\`\`

---

## Step 4: Propose a Fix

Create a remediation action. Risk level determines whether approval is required before the action can be run.

\`\`\`bash
bugpilot fix suggest \\
  --investigation-id inv_7f3a2b \\
  "Rollback deployment a3f8c2d" \\
  --type rollback \\
  --risk low \\
  --description "Revert Stripe SDK v4 update — correlates with onset of 5xx errors" \\
  --hypothesis-id hyp_f3a1d2 \\
  --rollback-plan "git revert a3f8c2d && trigger CI redeploy pipeline"
\`\`\`

\`\`\`
✓ Action created: act_d2f4e1
  Title:  Rollback deployment a3f8c2d
  Risk:   low
  Status: pending  (no approval required for low-risk actions)
\`\`\`

**Risk levels and approval:**

| Risk | Approval required |
|------|------------------|
| \`safe\` / \`low\` | No |
| \`medium\` / \`high\` / \`critical\` | Yes — \`approver\` role required |

---

## Step 5: Execute the Fix

Run the action. BugPilot will show the action details and ask for confirmation before executing:

\`\`\`bash
bugpilot fix run act_d2f4e1
\`\`\`

\`\`\`
  Action:     Rollback deployment a3f8c2d
  Risk level: LOW
Execute this action? [y/N]: y

✓ Action executed: act_d2f4e1
\`\`\`

Use \`--yes\` / \`-y\` to skip the confirmation prompt in scripts.

Watch your monitoring. If the 5xx rate drops, the fix worked.

---

## Step 6: Confirm Root Cause and Close

Confirm the hypothesis that turned out to be correct:

\`\`\`bash
bugpilot hypotheses confirm hyp_f3a1d2
\`\`\`

Reject the ones that didn't apply:

\`\`\`bash
bugpilot hypotheses reject hyp_8b3c1a
\`\`\`

Close the investigation:

\`\`\`bash
bugpilot investigate close inv_7f3a2b
# or the top-level alias:
bugpilot resolve inv_7f3a2b
\`\`\`

---

## Step 7: Export a Post-Mortem

\`\`\`bash
# Markdown report for Confluence / Notion / GitHub wiki
bugpilot export markdown inv_7f3a2b --output postmortem-2026-03-10.md

# Full JSON bundle for archiving or integrations
bugpilot export json inv_7f3a2b --output inv_7f3a2b.json
\`\`\`

---

## Tips

**Add evidence from multiple sources.** Confidence is capped at 40% with a single source. A second source from a different platform significantly improves hypothesis quality.

**Use \`--output json\` in scripts.** Every command supports \`-o json\` for pipeline-friendly output:

\`\`\`bash
bugpilot hypotheses list --investigation-id inv_7f3a2b -o json \\
  | jq '.[] | select(.confidence_score > 0.6)'
\`\`\`

**Reject bad hypotheses early.** This helps BugPilot improve scoring accuracy for your org over time.`,
  },

  webhooks: {
    slug: "webhooks",
    title: "Configure Webhooks",
    category: "Investigating Incidents",
    content: `# How to Configure Webhooks (Automatic Mode)

BugPilot can receive webhooks from your monitoring platforms to automatically create and triage investigations when alerts fire — eliminating the manual step of opening an investigation.

---

## How It Works

\`\`\`
Monitoring platform fires alert
          │
          ▼
BugPilot receives webhook POST
          │
          ▼
Signature verified (HMAC-SHA256)
          │
          ▼
Dedup check — does a similar open investigation already exist?
          │
    ┌─────┴──────┐
  New alert    Duplicate
    │              │
    ▼              ▼
Create new     Update existing
investigation  investigation
          │
          ▼
Evidence collection begins
          │
          ▼
Open terminal → bugpilot investigate list --status open
\`\`\`

---

## Supported Sources

| Source | Webhook path | Signature header |
|--------|-------------|-----------------|
| Datadog | \`/api/v1/webhooks/datadog\` | \`X-Hub-Signature\` (hex HMAC) |
| Grafana | \`/api/v1/webhooks/grafana\` | \`X-Grafana-Signature\` (\`sha256=\` prefix) |
| AWS CloudWatch (SNS) | \`/api/v1/webhooks/cloudwatch\` | SNS certificate verification |
| PagerDuty | \`/api/v1/webhooks/pagerduty\` | \`X-PagerDuty-Signature\` (\`v1=\` prefix) |

---

## Step 1: Add a Webhook Secret to Your Config

Each webhook source requires a secret (minimum 32 characters) used to verify incoming request signatures. Add the secret to the \`webhooks\` section of \`~/.config/bugpilot/config.yaml\`:

\`\`\`bash
# Generate a starter config if you haven't already
bugpilot config init
\`\`\`

Then edit \`~/.config/bugpilot/config.yaml\` and fill in the \`webhooks\` section:

\`\`\`yaml
webhooks:
  datadog:
    secret: "\${DD_WEBHOOK_SECRET}"
  grafana:
    secret: "\${GRAFANA_WEBHOOK_SECRET}"
  cloudwatch:
    secret: "\${CW_WEBHOOK_SECRET}"
  pagerduty:
    secret: "\${PD_WEBHOOK_SECRET}"
\`\`\`

Use a different secret for each source. Secrets must be at least 32 characters.

---

## Step 2: Configure Your Monitoring Platform

Point your monitoring platform's webhook/notification settings at the BugPilot endpoint and set the shared secret.

### Datadog

1. Go to **Integrations → Webhooks**
2. Add a new webhook:
   - **URL:** \`https://api.bugpilot.io/api/v1/webhooks/datadog\`
   - **Payload:** Leave as default (standard Datadog format)
   - **Secret:** The value you set for \`webhooks.datadog.secret\` in config.yaml
3. Add the webhook to any monitor under **Notify your team**

### Grafana

1. Go to **Alerting → Contact points → New contact point**
2. Select type **Webhook**
3. Set URL to \`https://api.bugpilot.io/api/v1/webhooks/grafana\`
4. Under **Optional Webhook settings**, set the Authorization header using your secret
5. Save and assign to an alert rule via a notification policy

### AWS CloudWatch (via SNS)

1. Create an SNS topic
2. Add an HTTPS subscription pointing to \`https://api.bugpilot.io/api/v1/webhooks/cloudwatch\`
3. BugPilot will automatically confirm the subscription on first delivery
4. Configure your CloudWatch alarms to send to the SNS topic

### PagerDuty

1. Go to **Integrations → Generic Webhooks (v3)**
2. Add endpoint: \`https://api.bugpilot.io/api/v1/webhooks/pagerduty\`
3. Select events: **incident.triggered**, **incident.acknowledged**, **incident.resolved**
4. Set the webhook secret to match what you set in config.yaml

---

## Step 3: Verify the Config

\`\`\`bash
bugpilot config validate
\`\`\`

\`\`\`
✓ Config is valid.
  2 connector(s) configured
\`\`\`

---

## Using Automatic Mode

After webhooks are configured, alerts create investigations automatically. In the terminal:

\`\`\`bash
# See what investigations have been auto-created
bugpilot investigate list --status open

# Check the status of an auto-created investigation
bugpilot incident status inv_7f3a2b

# Continue from where BugPilot left off — add more evidence, review hypotheses
bugpilot evidence collect --investigation-id inv_7f3a2b ...
bugpilot hypotheses list --investigation-id inv_7f3a2b
\`\`\`

---

## Deduplication

When a webhook arrives, BugPilot checks for existing open investigations using a weighted similarity score:

| Signal | Weight |
|--------|--------|
| Service name match | 40% |
| Time proximity (within 30 min) | 30% |
| Alert signature match | 20% |
| Symptom text similarity | 10% |

If similarity exceeds the threshold, the webhook updates the existing investigation rather than creating a new one.

---

## Secret Rotation

To rotate a webhook secret without downtime:

1. Update the secret in \`~/.config/bugpilot/config.yaml\`
2. Update the secret in your monitoring platform
3. BugPilot supports a 1-hour grace window where both the old and new secret are accepted

---

## Rate Limiting

Webhook endpoints are rate-limited to **100 requests per minute** per IP + org combination. Requests exceeding this return \`429 Too Many Requests\`.

---

## Troubleshooting

**401 Unauthorized on delivery**
- The signature header is missing or the secret doesn't match
- Verify the secret in your monitoring platform matches \`webhooks.<source>.secret\` in config.yaml exactly (no extra spaces or encoding differences)
- Check for encoding differences (URL-encoding, extra whitespace)

**Webhook received but no investigation created**
- Verify the webhook payload format matches the expected schema for your source
- If a dedup check matched an existing open investigation, the webhook updated it — check \`bugpilot investigate list --status open\``,
  },

  connectors: {
    slug: "connectors",
    title: "Connector Setup",
    category: "Investigating Incidents",
    content: `# Connector Setup Guide

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

All connector credentials are stored in \`~/.config/bugpilot/config.yaml\` (permissions \`600\`). Credentials are never sent anywhere except the BugPilot service for evidence collection.

### Option A: Interactive wizard (recommended)

\`\`\`bash
bugpilot connector add datadog
bugpilot connector add grafana
bugpilot connector add cloudwatch
bugpilot connector add github
bugpilot connector add kubernetes
bugpilot connector add pagerduty
\`\`\`

Each command prompts for the required fields. Secret values are masked during input.

### Option B: Edit config.yaml directly

Generate a starter file:

\`\`\`bash
bugpilot config init
\`\`\`

Then edit \`~/.config/bugpilot/config.yaml\`. Use \`\${VAR_NAME}\` to pull values from environment variables.

### Listing and removing connectors

\`\`\`bash
bugpilot connector list          # show all configured connectors (secrets masked)
bugpilot connector remove datadog  # remove a connector
bugpilot connector test          # test all connectors
bugpilot connector test grafana  # test a specific connector
\`\`\`

### Checking your config for errors

\`\`\`bash
bugpilot config validate
bugpilot config show
\`\`\`

---

## Datadog

**Capabilities:** Logs, Metrics, Traces, Alerts

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| \`api_key\` | Yes | Datadog API key |
| \`app_key\` | Yes | Datadog Application key |
| \`site\` | No | Your Datadog site — default: \`datadoghq.com\` |

### Required permissions

Your API key must have:
- \`logs_read_data\`
- \`metrics_read\`
- \`apm_read\`
- \`monitors_read\`

### Config file example

\`\`\`yaml
connectors:
  datadog:
    api_key: "\${DD_API_KEY}"
    app_key: "\${DD_APP_KEY}"
    site: "datadoghq.com"
\`\`\`

---

## Grafana

**Capabilities:** Metrics, Alerts

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| \`url\` | Yes | Your Grafana instance URL (e.g. \`https://grafana.example.com\`) |
| \`api_token\` | Yes | Service account token (Viewer role minimum) |
| \`org_id\` | No | Grafana org ID — default: \`1\` |
| \`prometheus_datasource_uid\` | No | UID of your Prometheus datasource (auto-discovered if omitted) |

### Creating a service account token

1. Go to **Administration → Service Accounts → Add service account**
2. Set role to **Viewer**
3. Click **Add token** — copy the token immediately

### Config file example

\`\`\`yaml
connectors:
  grafana:
    url: "https://grafana.example.com"
    api_token: "\${GRAFANA_TOKEN}"
    org_id: "1"
\`\`\`

---

## AWS CloudWatch

**Capabilities:** Logs, Metrics, Alarms

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| \`aws_access_key_id\` | Yes | IAM access key ID |
| \`aws_secret_access_key\` | Yes | IAM secret access key |
| \`region\` | Yes | AWS region (e.g. \`us-east-1\`) |
| \`log_group_names\` | No | List of CloudWatch log group names to query |

### Required IAM permissions

\`\`\`json
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
\`\`\`

### Config file example

\`\`\`yaml
connectors:
  cloudwatch:
    aws_access_key_id: "\${AWS_ACCESS_KEY_ID}"
    aws_secret_access_key: "\${AWS_SECRET_ACCESS_KEY}"
    region: "us-east-1"
    log_group_names:
      - "/aws/lambda/payment-service"
      - "/ecs/checkout-service"
\`\`\`

---

## GitHub

**Capabilities:** Code changes, Deployments

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| \`token\` | Yes | Personal access token or GitHub App installation token |
| \`org\` | Yes | GitHub organization name |
| \`repos\` | No | List of repository names to watch |

### Token scopes required

- \`repo:status\`
- \`read:repo_hook\`

### Creating a personal access token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Generate new token with \`repo:status\` and \`read:repo_hook\` scopes

### Config file example

\`\`\`yaml
connectors:
  github:
    token: "\${GITHUB_TOKEN}"
    org: "mycompany"
    repos:
      - "payment-service"
      - "checkout-service"
\`\`\`

---

## Kubernetes

**Capabilities:** Pod state, Events, Logs

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| \`api_server\` | Yes | Kubernetes API server URL |
| \`token\` | Yes | Service account bearer token |
| \`namespace\` | No | Primary namespace — default: \`production\` |
| \`extra_namespaces\` | No | Additional namespaces to watch |
| \`ca_cert_path\` | No | Path to CA certificate for TLS verification |

### Creating a service account

\`\`\`yaml
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
\`\`\`

Get the token:

\`\`\`bash
kubectl create token bugpilot -n production
\`\`\`

### Config file example

\`\`\`yaml
connectors:
  kubernetes:
    api_server: "https://kubernetes.example.com:6443"
    token: "\${K8S_TOKEN}"
    namespace: "production"
    extra_namespaces:
      - "staging"
\`\`\`

---

## PagerDuty

**Capabilities:** Incidents, Alerts

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| \`api_key\` | Yes | PagerDuty REST API key (read-only) |
| \`from_email\` | Yes | Email address for API requests |
| \`service_ids\` | No | Limit to specific PagerDuty service IDs |

### Creating a read-only API key

1. Go to **PagerDuty → Integrations → API Access Keys**
2. Create a key with **Read-only** access

### Config file example

\`\`\`yaml
connectors:
  pagerduty:
    api_key: "\${PD_API_KEY}"
    from_email: "oncall@example.com"
    service_ids:
      - "PXXXXXX"
\`\`\`

---

## Connection Behaviour

| Setting | Value |
|---------|-------|
| Request timeout per connector | 30 seconds |
| Max collection time per connector | 45 seconds |
| Retry on HTTP status | 429, 500, 502, 503, 504 |
| Max retry attempts | 3 |
| Retry backoff | Exponential with jitter |

If a connector times out or errors, BugPilot marks it **degraded** for that run and continues with the remaining connectors. Results are partial rather than blocked.`,
  },

  "llm-providers": {
    slug: "llm-providers",
    title: "LLM Providers",
    category: "Configuration",
    content: `# How to Configure LLM Providers

BugPilot uses LLMs to synthesize additional hypotheses when evidence is complex or when rule-based patterns don't fully explain an incident. LLM usage is **optional** — BugPilot works without one using its rule-based and graph correlation engines.

---

## Overview

When an LLM is configured, it runs as the 4th pass of the hypothesis pipeline:

\`\`\`
Pass 1: Rule-based pattern matching     (always runs)
Pass 2: Graph correlation               (always runs)
Pass 3: Historical reranking            (always runs)
Pass 4: LLM synthesis                  (runs only when LLM_PROVIDER is set)
Pass 5: Deduplication
Pass 6: Final ranking
\`\`\`

The LLM receives a **redacted** evidence summary — all PII, credentials, tokens, and keys are stripped before anything is sent. This is enforced in code; a safety check raises an error if non-redacted data reaches the LLM boundary.

---

## Supported Providers

| Provider key | Models | Notes |
|---|---|---|
| \`openai\` | \`gpt-4o\` (default) | Requires \`LLM_API_KEY\` |
| \`anthropic\` | \`claude-sonnet-4-6\` (default) | Requires \`LLM_API_KEY\`. Supports prompt caching. |
| \`azure_openai\` | Any deployed model | Requires \`LLM_BASE_URL\`, \`LLM_API_KEY\`, and \`LLM_AZURE_DEPLOYMENT\` |
| \`gemini\` | \`gemini-1.5-pro\` (default) | Requires \`LLM_API_KEY\` |
| \`ollama\` | Any locally hosted model | Requires \`LLM_BASE_URL\`. No external API calls — fully on-premise. |
| \`openai_compatible\` | Any model | For OpenAI-compatible APIs (e.g. vLLM, LM Studio). Requires \`LLM_BASE_URL\` and \`LLM_API_KEY\`. |

---

## Configuration

LLM providers are configured via environment variables on the BugPilot analysis engine server. All providers share the same variable names — only the values differ.

### Common Variables

| Variable | Description |
|---|---|
| \`LLM_PROVIDER\` | Provider key (see table above) |
| \`LLM_API_KEY\` | API key for the selected provider |
| \`LLM_MODEL\` | Model name override (uses provider default if unset) |
| \`LLM_BASE_URL\` | Base URL for Azure OpenAI, Ollama, or OpenAI-compatible providers |
| \`LLM_AZURE_DEPLOYMENT\` | Azure OpenAI deployment name (Azure only) |
| \`LLM_AZURE_API_VERSION\` | Azure OpenAI API version (Azure only) |

### OpenAI

\`\`\`bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
# Optional: override the default model
LLM_MODEL=gpt-4o
\`\`\`

### Anthropic

\`\`\`bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
# Optional: override the default model
LLM_MODEL=claude-sonnet-4-6
\`\`\`

### Azure OpenAI

\`\`\`bash
LLM_PROVIDER=azure_openai
LLM_BASE_URL=https://your-resource.openai.azure.com
LLM_API_KEY=your-azure-key
LLM_AZURE_DEPLOYMENT=your-deployment-name
LLM_AZURE_API_VERSION=2024-02-01
\`\`\`

### Google Gemini

\`\`\`bash
LLM_PROVIDER=gemini
LLM_API_KEY=AIzaSy...
# Optional: override the default model
LLM_MODEL=gemini-1.5-pro
\`\`\`

### Ollama (on-premise, no external calls)

\`\`\`bash
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3                        # or any model you have pulled
\`\`\`

### OpenAI-Compatible (vLLM, LM Studio, etc.)

\`\`\`bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:8080/v1
LLM_API_KEY=your-api-key               # use "none" if auth is not required
LLM_MODEL=your-model-name
\`\`\`

### No LLM (rule-based only)

Simply leave \`LLM_PROVIDER\` unset. BugPilot will use rule-based and graph correlation only. This is the default.

---

## Privacy Guarantee

Before any evidence is sent to an LLM, BugPilot's privacy redactor strips:

- Email addresses
- Phone numbers
- JWT and Bearer tokens
- Payment card numbers
- AWS access keys and secrets
- PEM private keys
- IP addresses (configurable)
- Custom regex patterns (configurable per org)

This redaction happens in code before the LLM boundary. A safety check in the hypothesis engine raises a \`ValueError\` if it detects non-redacted content about to be sent — this is a hard stop, not a warning.

---

## Token Budget

| Limit | Value |
|-------|-------|
| Max prompt tokens | 8,000 |
| Max completion tokens | 2,000 |
| Max tokens per investigation | 40,000 |

When the investigation token budget is exhausted, LLM synthesis is skipped for subsequent hypothesis passes. Rule-based and graph results are still produced.

---

## Caching

LLM responses are cached in-memory keyed by SHA-256 hash of the graph content. The cache is invalidated when new evidence is added to the investigation.

---

## Usage Tracking

LLM usage is logged and exposed via Prometheus metrics:

| Metric | Description |
|--------|-------------|
| \`bugpilot_llm_requests_total\` | Total LLM requests, labelled by provider |
| \`bugpilot_llm_tokens_total\` | Prompt and completion token counts |`,
  },

  rbac: {
    slug: "rbac",
    title: "Users & Roles",
    category: "Administration",
    content: `# How to Manage Users and Roles

BugPilot uses role-based access control (RBAC) with four roles. This guide covers role assignments, permissions, and administration tasks.

---

## Roles

| Role | Description |
|------|-------------|
| \`viewer\` | Read-only access — can view investigations, evidence, hypotheses, and actions |
| \`investigator\` | Standard user — can create investigations, add evidence, create hypotheses and actions |
| \`approver\` | All investigator permissions plus the ability to approve medium/high/critical-risk actions |
| \`admin\` | Full access — manages users, connectors, webhooks, org settings, and all data |

---

## Permission Matrix

| Permission | viewer | investigator | approver | admin |
|------------|--------|-------------|----------|-------|
| View investigations | ✓ | ✓ | ✓ | ✓ |
| Create/update investigations | | ✓ | ✓ | ✓ |
| View evidence | ✓ | ✓ | ✓ | ✓ |
| Add/delete evidence | | ✓ | ✓ | ✓ |
| View hypotheses | ✓ | ✓ | ✓ | ✓ |
| Create/update hypotheses | | ✓ | ✓ | ✓ |
| View actions | ✓ | ✓ | ✓ | ✓ |
| Create actions | | ✓ | ✓ | ✓ |
| **Approve medium/high/critical actions** | | | **✓** | **✓** |
| Manage users and roles | | | | ✓ |
| Manage connectors and webhooks | | | | ✓ |
| View audit log | | | | ✓ |
| Configure org settings | | | | ✓ |

---

## Action Approval Workflow

When an action is created with risk level \`medium\`, \`high\`, or \`critical\`, it is placed in \`pending\` status and cannot be run until approved by a user with the \`approver\` or \`admin\` role.

\`\`\`
[investigator creates action]  →  Status: pending
         │
         ▼
[approver reviews]
         │
    ┌────┴────┐
  Approve    Reject
    │
    ▼
Status: approved  →  [investigator runs action]
\`\`\`

Safe and low-risk actions skip the approval step and can be run immediately by the creating user.

---

## Managing Users

### Viewing Users

\`\`\`bash
curl https://api.bugpilot.io/api/v1/admin/users \\
  -H "Authorization: Bearer \$ADMIN_TOKEN"
\`\`\`

### Changing a User's Role

\`\`\`bash
curl -X PATCH https://api.bugpilot.io/api/v1/admin/users/{user_id} \\
  -H "Authorization: Bearer \$ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"role": "approver"}'
\`\`\`

Valid roles: \`viewer\`, \`investigator\`, \`approver\`, \`admin\`

### Deactivating a User

\`\`\`bash
curl -X DELETE https://api.bugpilot.io/api/v1/admin/users/{user_id} \\
  -H "Authorization: Bearer \$ADMIN_TOKEN"
\`\`\`

Deactivated users lose access immediately. Their historical data (investigations, evidence, actions) is preserved.

---

## Audit Log

Every write operation is recorded in the audit log with:

- \`user_id\` — who performed the action
- \`action\` — what was done
- \`ip_address\` — where the request came from
- \`occurred_at\` — timestamp
- \`metadata\` — relevant IDs and field changes

\`\`\`bash
curl "https://api.bugpilot.io/api/v1/admin/audit-logs?limit=50" \\
  -H "Authorization: Bearer \$ADMIN_TOKEN"
\`\`\`

The audit log is append-only and cannot be modified or deleted.

---

## CLI Token Roles

When a user activates the CLI with \`bugpilot auth activate --key bp_...\`, their token inherits the role assigned to them by the admin. The role is visible in \`bugpilot auth whoami\`.

If a command is rejected due to insufficient permissions, the CLI returns:

\`\`\`
✗ Error: 403 Forbidden — insufficient role for this action
  Your role: investigator
  Required:  approver
\`\`\``,
  },

  "data-retention": {
    slug: "data-retention",
    title: "Data Retention",
    category: "Administration",
    content: `# How to Configure Data Retention

BugPilot implements a three-phase data retention policy, configurable per organisation. A daily purge job runs automatically at 02:00 UTC.

---

## Retention Phases

Data moves through three progressively smaller retention windows:

\`\`\`
Investigation created
        │
        ▼
Phase 1: Investigation archive
  Resolved/closed investigations retained for N days
  Default: 90 days
        │
        ▼
Phase 2: Evidence metadata
  Evidence rows (metadata only) retained for N days
  Default: 30 days
        │
        ▼
Phase 3: Raw payload
  Raw evidence payloads purged after N days
  Default: 7 days
  (evidence row remains, payload_ref set to null)
\`\`\`

---

## Defaults

| Phase | Default retention |
|-------|-----------------|
| Investigation archive | 90 days |
| Evidence metadata | 30 days |
| Raw payload | 7 days |

---

## Preset Configurations

### Compliance (longer retention)

\`\`\`json
{
  "investigation_archive_days": 365,
  "evidence_metadata_days": 365,
  "raw_payload_days": 7
}
\`\`\`

### Cost-optimised

\`\`\`json
{
  "investigation_archive_days": 90,
  "evidence_metadata_days": 30,
  "raw_payload_days": 7
}
\`\`\`

### Development / low-cost

\`\`\`json
{
  "investigation_archive_days": 30,
  "evidence_metadata_days": 7,
  "raw_payload_days": 1
}
\`\`\`

---

## Updating Retention Settings

Admins can update the retention policy via the API:

\`\`\`bash
curl -X PATCH https://api.bugpilot.io/api/v1/admin/org/settings \\
  -H "Authorization: Bearer \$ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "retention": {
      "investigation_archive_days": 180,
      "evidence_metadata_days": 60,
      "raw_payload_days": 14
    }
  }'
\`\`\`

---

## How the Purge Works

Each purge phase is fully idempotent — safe to run multiple times. Every deletion writes an entry to the audit log before data is removed, so you have a record of what was purged and when.

The purge runs automatically on a daily schedule. You can view recent purge activity in the audit log:

\`\`\`bash
curl "https://api.bugpilot.io/api/v1/admin/audit-logs?action=retention_purge" \\
  -H "Authorization: Bearer \$ADMIN_TOKEN"
\`\`\`

---

## Notes

- Retention settings apply org-wide; per-investigation overrides are not currently supported
- Reducing retention takes effect on the next daily purge run
- Increasing retention is effective immediately (existing data is not retroactively deleted)
- The audit log itself is not subject to retention purges — it is permanent`,
  },

  "cli-reference": {
    slug: "cli-reference",
    title: "CLI Reference",
    category: "Reference",
    content: `# CLI Reference

Complete reference for every \`bugpilot\` command. All commands support three output formats.

---

## Global Options

\`\`\`
bugpilot [OPTIONS] COMMAND [ARGS]...
\`\`\`

| Option | Short | Env var | Default | Description |
|--------|-------|---------|---------|-------------|
| \`--api-url TEXT\` | — | \`BUGPILOT_API_URL\` | \`https://api.bugpilot.io\` | BugPilot service URL |
| \`--analysis-url TEXT\` | — | \`BUGPILOT_ANALYSIS_URL\` | — | Analysis engine URL (for AI features) |
| \`--investigation TEXT\` | — | \`BUGPILOT_INVESTIGATION\` | — | Default investigation ID for all commands |
| \`--output TEXT\` | \`-o\` | \`BUGPILOT_OUTPUT\` | \`human\` | Output format: \`human\` \\| \`json\` \\| \`verbose\` |
| \`--no-color\` | — | \`NO_COLOR\` | false | Disable colour |
| \`--version\` | \`-v\` | — | — | Print version and exit |

**Output formats:**

- **\`human\`** — colour-coded tables. Best for interactive use.
- **\`json\`** — machine-readable JSON on stdout. Use in scripts and CI.
- **\`verbose\`** — all fields with syntax highlighting. Use for debugging.

Setting \`BUGPILOT_INVESTIGATION\` (or passing \`--investigation\`) lets you omit \`-i\`/\`--investigation-id\` from every subsequent command for the duration of a shell session.

---

## \`bugpilot auth\`

### \`auth activate\`

Link the CLI to your BugPilot account. Displays Terms of Service on first run. Run once per machine.

\`\`\`
bugpilot auth activate [--key KEY] [--secret SECRET] [--email EMAIL] [--name NAME]
\`\`\`

| Option | Short | Env var | Description |
|--------|-------|---------|-------------|
| \`--key\` | \`-k\` | \`BUGPILOT_LICENSE_KEY\` | License key. Prompted if omitted. |
| \`--secret\` | \`-s\` | \`BUGPILOT_API_SECRET\` | API secret. Prompted if omitted. |
| \`--email\` | \`-e\` | — | Your email address. Prompted if omitted. |
| \`--name\` | — | — | Optional display name. |

\`\`\`
$ bugpilot auth activate --key YOUR_LICENSE_KEY --secret YOUR_API_SECRET

[Terms of Service displayed — accept/decline]

Enter your email address: alice@acme.com

✓ BugPilot activated!
\`\`\`

Session is stored at \`~/.config/bugpilot/credentials.json\` (permissions \`600\`).

---

### \`auth logout\`

End the session and clear stored credentials.

\`\`\`
bugpilot auth logout
\`\`\`

---

### \`auth whoami\`

Show the currently authenticated user.

\`\`\`
bugpilot auth whoami
\`\`\`

\`\`\`
User:         alice@acme.com
Display name: Alice Smith
Role:         investigator
Org ID:       org_acme
User ID:      usr_a3f8c2
\`\`\`

---

## \`bugpilot license\`

Show license information and seat usage.

\`\`\`
bugpilot license
\`\`\`

---

## \`bugpilot connector\`

Manage data source connectors. Credentials are stored in \`~/.config/bugpilot/config.yaml\`.

### \`connector list\`

Show all configured connectors (secrets masked).

\`\`\`
bugpilot connector list
\`\`\`

---

### \`connector add\`

Add or update a connector interactively.

\`\`\`
bugpilot connector add TYPE [--overwrite]
\`\`\`

| Argument/Option | Description |
|-----------------|-------------|
| \`TYPE\` | Connector type: \`datadog\` \\| \`grafana\` \\| \`cloudwatch\` \\| \`github\` \\| \`kubernetes\` \\| \`pagerduty\` |
| \`--overwrite\` | Overwrite existing connector without prompting |

\`\`\`
$ bugpilot connector add datadog

Configure datadog connector

  API Key: ••••••••••••••••••••
  Application Key: ••••••••••••••••••••
  Site (e.g. datadoghq.com) [datadoghq.com]:

✓ Connector 'datadog' saved to ~/.config/bugpilot/config.yaml
\`\`\`

---

### \`connector remove\`

Remove a connector from config.

\`\`\`
bugpilot connector remove TYPE [--yes]
\`\`\`

\`--yes\` / \`-y\` — skip confirmation.

---

### \`connector test\`

Test connector connectivity. Omit \`TYPE\` to test all.

\`\`\`
bugpilot connector test [TYPE]
\`\`\`

\`\`\`
$ bugpilot connector test

  Testing datadog...  ✓ OK
  Testing grafana...  ✓ OK
\`\`\`

---

## \`bugpilot config\`

Manage \`~/.config/bugpilot/config.yaml\`.

### \`config init\`

Create a starter config file with all connector and webhook templates.

\`\`\`
bugpilot config init [--overwrite]
\`\`\`

\`--overwrite\` — replace an existing config file.

---

### \`config show\`

Display the current config (secrets masked).

\`\`\`
bugpilot config show
\`\`\`

---

### \`config validate\`

Check the config for missing required fields.

\`\`\`
bugpilot config validate
\`\`\`

Exits with code \`1\` if there are validation errors.

---

## \`bugpilot investigate\`

### \`investigate list\`

List investigations for your organisation.

\`\`\`
bugpilot investigate list [--status STATUS] [--severity SEVERITY] [--page N] [--page-size N]
\`\`\`

| Option | Description |
|--------|-------------|
| \`--status, -s\` | Filter: \`open\` \\| \`in_progress\` \\| \`resolved\` \\| \`closed\` |
| \`--severity\` | Filter: \`critical\` \\| \`high\` \\| \`medium\` \\| \`low\` |
| \`--page, -p\` | Page number (default: 1) |
| \`--page-size\` | Results per page (default: 20) |

\`\`\`
$ bugpilot investigate list --status open

  ID          TITLE                                SEVERITY  STATUS   CREATED
  inv_7f3a2b  High error rate on payment-service   high      open     2h ago
  inv_c1d9e0  Database connection pool exhausted   critical  open     45m ago
\`\`\`

---

### \`investigate create\`

Open a new investigation.

\`\`\`
bugpilot investigate create TITLE [--symptom TEXT] [--severity LEVEL] [--description TEXT]
\`\`\`

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| \`TITLE\` | Yes | — | Short description (positional argument) |
| \`--symptom\` | No | — | Observable symptom text |
| \`--severity\` | No | \`medium\` | \`critical\` \\| \`high\` \\| \`medium\` \\| \`low\` |
| \`--description, -d\` | No | — | Additional context or notes |

---

### \`investigate get\`

Fetch full details of one investigation.

\`\`\`
bugpilot investigate get INVESTIGATION_ID
\`\`\`

---

### \`investigate update\`

Update investigation fields.

\`\`\`
bugpilot investigate update INVESTIGATION_ID
  [--title TEXT] [--status STATUS] [--severity LEVEL] [--description TEXT]
\`\`\`

---

### \`investigate close\`

Mark an investigation as closed.

\`\`\`
bugpilot investigate close INVESTIGATION_ID
\`\`\`

Also available as the top-level alias \`bugpilot resolve\`.

---

### \`investigate delete\`

Permanently delete an investigation and all its evidence. Requires confirmation.

\`\`\`
bugpilot investigate delete INVESTIGATION_ID [--yes]
\`\`\`

\`--yes\` / \`-y\` — skip the confirmation prompt.

---

## \`bugpilot incident\`

### \`incident list\`

List recent incidents.

\`\`\`
bugpilot incident list [--status STATUS] [--page N] [--page-size N]
\`\`\`

---

### \`incident open\`

Set the active investigation context for the current shell session. Subsequent commands that accept \`-i\`/\`--investigation-id\` will use this investigation by default.

\`\`\`
bugpilot incident open INVESTIGATION_ID
\`\`\`

\`\`\`
$ bugpilot incident open inv_7f3a2b
✓ Active investigation set to inv_7f3a2b
  (stored in BUGPILOT_INVESTIGATION for this session)
\`\`\`

---

### \`incident triage\`

Quickly create an investigation from an active alert. Creates the investigation and records a timeline event in one step.

\`\`\`
bugpilot incident triage TITLE [--symptom TEXT] [--severity LEVEL] [--service TEXT]
\`\`\`

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| \`TITLE\` | Yes | — | Incident title or alert name (positional) |
| \`--symptom, -s\` | No | — | Observed symptom or alert description |
| \`--severity\` | No | \`high\` | \`critical\` \\| \`high\` \\| \`medium\` \\| \`low\` |
| \`--service\` | No | — | Affected service name |

---

### \`incident status\`

Show a full summary of an active investigation — evidence count, hypotheses, and actions.

\`\`\`
bugpilot incident status INVESTIGATION_ID
\`\`\`

---

## \`bugpilot investigation\`

### \`investigation export\`

Export an investigation using the stored investigation context (set via \`incident open\` or \`BUGPILOT_INVESTIGATION\`).

\`\`\`
bugpilot investigation export [-i INVESTIGATION_ID] [-f FORMAT] [-o FILE]
\`\`\`

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| \`--investigation-id\` | \`-i\` | \`\$BUGPILOT_INVESTIGATION\` | Investigation ID |
| \`--format\` | \`-f\` | \`json\` | \`json\` \\| \`markdown\` |
| \`--output\` | \`-o\` | stdout | Write to file instead of stdout |

---

## \`bugpilot evidence\`

Evidence is what BugPilot analyses. You add evidence items to an investigation — log excerpts, metric summaries, deployment events, config changes — and BugPilot uses them to generate hypotheses.

### \`evidence list\`

\`\`\`
bugpilot evidence list --investigation-id ID [--kind KIND]
\`\`\`

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| \`--investigation-id\` | \`-i\` | Yes (or \`BUGPILOT_INVESTIGATION\`) | Investigation ID |
| \`--kind\` | — | No | Filter by kind |

**Evidence kinds:** \`log_snapshot\` · \`metric_snapshot\` · \`trace\` · \`event\` · \`config_diff\` · \`topology\` · \`custom\`

---

### \`evidence collect\`

Add a piece of evidence to an investigation.

\`\`\`
bugpilot evidence collect
  --investigation-id ID
  --label LABEL
  [--kind KIND]
  [--source URI]
  [--summary TEXT]
  [--connector-id CONNECTOR_ID]
\`\`\`

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| \`--investigation-id\` | \`-i\` | Yes (or \`BUGPILOT_INVESTIGATION\`) | Investigation to attach this evidence to |
| \`--label\` | \`-l\` | Yes | Short descriptive label |
| \`--kind\` | \`-k\` | No | Evidence kind (default: \`custom\`) |
| \`--source\` | — | No | Source URI identifying where this evidence came from, e.g. \`datadog://logs?service=checkout&env=prod\` |
| \`--summary\` | \`-s\` | No | Text summary of what this evidence shows |
| \`--connector-id\` | — | No | ID of the connector that produced this |

The \`--source\` option takes a **URI**, not a source system name. The URI scheme identifies the system (e.g. \`datadog://\`, \`github://\`, \`cloudwatch://\`) and query parameters narrow the scope.

\`\`\`bash
# Log snapshot from Datadog
bugpilot evidence collect \\
  -i inv_7f3a2b \\
  --label "payment-service error logs" \\
  --kind log_snapshot \\
  --source "datadog://logs?service=payment-service&env=prod" \\
  --summary "47 NullPointerException at UserService.java:142 starting 14:31 UTC"

# Deployment event from GitHub
bugpilot evidence collect \\
  -i inv_7f3a2b \\
  --label "deployment at 14:23 UTC" \\
  --kind config_diff \\
  --source "github://deployments?repo=acme/payment-service&ref=a3f8c2d" \\
  --summary "Commit a3f8c2d: Update Stripe SDK v4, deployed at 14:23 UTC"
\`\`\`

---

### \`evidence get\`

\`\`\`
bugpilot evidence get EVIDENCE_ID
\`\`\`

Also available as \`evidence show EVIDENCE_ID\`.

---

### \`evidence show\`

Alias for \`evidence get\`.

\`\`\`
bugpilot evidence show EVIDENCE_ID
\`\`\`

---

### \`evidence refresh\`

Re-fetch an evidence item from its source connector.

\`\`\`
bugpilot evidence refresh EVIDENCE_ID
\`\`\`

---

### \`evidence delete\`

\`\`\`
bugpilot evidence delete EVIDENCE_ID [--yes]
\`\`\`

---

## \`bugpilot hypotheses\`

### \`hypotheses list\`

List hypotheses ranked by confidence.

\`\`\`
bugpilot hypotheses list --investigation-id ID [--status STATUS] [--refresh]
\`\`\`

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| \`--investigation-id\` | \`-i\` | Yes (or \`BUGPILOT_INVESTIGATION\`) | Investigation ID |
| \`--status\` | \`-s\` | No | \`active\` \\| \`confirmed\` \\| \`rejected\` |
| \`--refresh\` | — | No | Trigger a new hypothesis generation pass before listing |

\`\`\`
$ bugpilot hypotheses list --investigation-id inv_7f3a2b

  RANK  HYPOTHESIS                             CONFIDENCE  STATUS
   1    Bad deployment introduced regression   72%         active
   2    Memory exhaustion                      41%         active
   3    Upstream dependency degradation        28%         active
\`\`\`

---

### \`hypotheses create\`

Add a hypothesis manually.

\`\`\`
bugpilot hypotheses create
  --investigation-id ID
  TITLE
  [--description TEXT]
  [--confidence FLOAT]
  [--reasoning TEXT]
  [--evidence EVIDENCE_ID]...
\`\`\`

| Argument/Option | Short | Required | Description |
|-----------------|-------|----------|-------------|
| \`TITLE\` | — | Yes | Hypothesis title (positional) |
| \`--investigation-id\` | \`-i\` | Yes (or \`BUGPILOT_INVESTIGATION\`) | Investigation ID |
| \`--description\` | \`-d\` | No | Detailed description |
| \`--confidence\` | \`-c\` | No | Confidence score 0.0–1.0 |
| \`--reasoning\` | — | No | Explanation of why this is a candidate |
| \`--evidence\` | — | No | Supporting evidence ID (repeatable) |

---

### \`hypotheses confirm\`

Mark a hypothesis as the confirmed root cause.

\`\`\`
bugpilot hypotheses confirm HYPOTHESIS_ID
\`\`\`

---

### \`hypotheses reject\`

Mark a hypothesis as ruled out.

\`\`\`
bugpilot hypotheses reject HYPOTHESIS_ID
\`\`\`

---

### \`hypotheses update\`

Update a hypothesis.

\`\`\`
bugpilot hypotheses update HYPOTHESIS_ID
  [--title TEXT] [--confidence FLOAT] [--reasoning TEXT]
\`\`\`

---

## \`bugpilot fix\`

### \`fix list\`

List actions for an investigation.

\`\`\`
bugpilot fix list --investigation-id ID [--status STATUS]
\`\`\`

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| \`--investigation-id\` | \`-i\` | Yes (or \`BUGPILOT_INVESTIGATION\`) | Investigation ID |
| \`--status\` | — | No | \`pending\` \\| \`approved\` \\| \`running\` \\| \`completed\` \\| \`cancelled\` |

---

### \`fix suggest\`

Propose a remediation action.

\`\`\`
bugpilot fix suggest
  --investigation-id ID
  TITLE
  --type TYPE
  [--risk LEVEL]
  [--description TEXT]
  [--hypothesis-id ID]
  [--rollback-plan TEXT]
\`\`\`

| Argument/Option | Short | Required | Default | Description |
|-----------------|-------|----------|---------|-------------|
| \`TITLE\` | — | Yes | — | Action title (positional) |
| \`--investigation-id\` | \`-i\` | Yes (or \`BUGPILOT_INVESTIGATION\`) | — | Investigation ID |
| \`--type\` | \`-t\` | Yes | — | Action type, e.g. \`rollback\`, \`config_change\`, \`restart\`, \`scale\` |
| \`--risk\` | — | No | \`medium\` | \`safe\` \\| \`low\` \\| \`medium\` \\| \`high\` \\| \`critical\` |
| \`--description\` | \`-d\` | No | — | What the action does |
| \`--hypothesis-id\` | — | No | — | Hypothesis this action targets |
| \`--rollback-plan\` | — | No | — | How to undo this action |

**Approval rules:**

| Risk level | Approval required before running? |
|------------|----------------------------------|
| \`safe\` or \`low\` | No |
| \`medium\`, \`high\`, or \`critical\` | Yes — \`approver\` role required |

---

### \`fix approve\`

Approve a medium/high/critical-risk action. Requires \`approver\` or \`admin\` role.

\`\`\`
bugpilot fix approve ACTION_ID
\`\`\`

---

### \`fix run\`

Execute an action. Displays the action title and risk level, then prompts for confirmation before proceeding.

\`\`\`
bugpilot fix run ACTION_ID [--yes]
\`\`\`

\`--yes\` / \`-y\` — skip the confirmation prompt.

\`\`\`
$ bugpilot fix run act_d2f4e1

  Action:     Rollback deployment a3f8c2d
  Risk level: LOW
Execute this action? [y/N]: y

✓ Action executed: act_d2f4e1
\`\`\`

---

### \`fix cancel\`

Cancel a pending or approved action.

\`\`\`
bugpilot fix cancel ACTION_ID
\`\`\`

---

## \`bugpilot export\`

### \`export json\`

Export the full investigation bundle as JSON (investigation, evidence, hypotheses, actions, timeline).

\`\`\`
bugpilot export json INVESTIGATION_ID [--output FILE]
\`\`\`

\`--output\` / \`-o\` — write to a file instead of stdout.

---

### \`export markdown\`

Export a Markdown incident report suitable for Confluence, Notion, or GitHub wikis.

\`\`\`
bugpilot export markdown INVESTIGATION_ID [--output FILE]
\`\`\`

\`--output\` / \`-o\` — write to a file instead of stdout.

---

## \`bugpilot summary\`

Generate an AI-powered summary of an investigation. Requires \`BUGPILOT_ANALYSIS_URL\` to be configured.

\`\`\`
bugpilot summary [-i INVESTIGATION_ID]
\`\`\`

| Option | Short | Description |
|--------|-------|-------------|
| \`--investigation-id\` | \`-i\` | Investigation ID (or \`BUGPILOT_INVESTIGATION\`) |

---

## \`bugpilot ask\`

Ask a free-form question about an investigation. The analysis engine answers using the investigation's evidence and hypotheses. Requires \`BUGPILOT_ANALYSIS_URL\`.

\`\`\`
bugpilot ask QUESTION [-i INVESTIGATION_ID]
\`\`\`

| Argument/Option | Description |
|-----------------|-------------|
| \`QUESTION\` | Your question (positional) |
| \`--investigation-id\` / \`-i\` | Investigation ID (or \`BUGPILOT_INVESTIGATION\`) |

\`\`\`
$ bugpilot ask "What changed in the 10 minutes before the errors started?" -i inv_7f3a2b

  Based on the evidence collected:
  - Deployment a3f8c2d (Stripe SDK v4) deployed at 14:23 UTC — 8 minutes before errors
  - Heap memory began rising from 60% → 92% between 14:23 and 14:31 UTC
\`\`\`

---

## \`bugpilot compare\`

Compare the current investigation state against a healthy baseline. Requires \`BUGPILOT_ANALYSIS_URL\`.

\`\`\`
bugpilot compare [--last-healthy | --last-stable-post-deploy | --user-pinned] [-i INVESTIGATION_ID]
\`\`\`

| Option | Description |
|--------|-------------|
| \`--last-healthy\` | Compare against the last healthy state (default) |
| \`--last-stable-post-deploy\` | Compare against the last stable state after a deploy |
| \`--user-pinned\` | Compare against a user-pinned baseline |
| \`--investigation-id\` / \`-i\` | Investigation ID (or \`BUGPILOT_INVESTIGATION\`) |

---

## \`bugpilot timeline\`

Display the investigation timeline — all events ordered chronologically. Shows clock skew warnings when events from different sources have inconsistent timestamps.

\`\`\`
bugpilot timeline [-i INVESTIGATION_ID]
\`\`\`

| Option | Short | Description |
|--------|-------|-------------|
| \`--investigation-id\` | \`-i\` | Investigation ID (or \`BUGPILOT_INVESTIGATION\`) |

\`\`\`
$ bugpilot timeline -i inv_7f3a2b

  TIME (UTC)  SOURCE    EVENT
  14:23:04    github    Deployment a3f8c2d pushed to production
  14:23:41    datadog   Heap memory began rising (60% → 92%)
  14:31:07    datadog   HTTP 5xx rate crossed 5% threshold
  14:31:09    pagerduty Alert fired: payment-service degraded

  ⚠ Clock skew detected: pagerduty events are ~2s ahead of datadog
\`\`\`

---

## \`bugpilot resolve\`

Top-level alias for \`bugpilot investigate close\`. Marks an investigation as resolved.

\`\`\`
bugpilot resolve INVESTIGATION_ID
\`\`\`

---

## \`bugpilot history\`

Show the history of investigations for the current org, including resolved and closed ones.

\`\`\`
bugpilot history [-i INVESTIGATION_ID] [--page N] [--page-size N]
\`\`\`

| Option | Description |
|--------|-------------|
| \`--investigation-id\` / \`-i\` | Show history for a specific investigation |
| \`--page\` | Page number (default: 1) |
| \`--page-size\` | Results per page (default: 20) |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| \`BUGPILOT_API_URL\` | Override the API endpoint (default: \`https://api.bugpilot.io\`) |
| \`BUGPILOT_ANALYSIS_URL\` | Analysis engine URL (required for \`summary\`, \`ask\`, \`compare\`) |
| \`BUGPILOT_INVESTIGATION\` | Default investigation ID — set via \`incident open\` or manually |
| \`BUGPILOT_LICENSE_KEY\` | License key, read by \`auth activate --key\` |
| \`BUGPILOT_API_SECRET\` | API secret, read by \`auth activate --secret\` |
| \`BUGPILOT_OUTPUT\` | Default output format: \`human\` \\| \`json\` \\| \`verbose\` |
| \`NO_COLOR\` | Set to any non-empty value to disable colour |

---

## Using in CI / Scripts

\`\`\`bash
# Activate non-interactively
bugpilot auth activate \\
  --key "\$BUGPILOT_LICENSE_KEY" \\
  --secret "\$BUGPILOT_API_SECRET" \\
  --email "\$BUGPILOT_EMAIL"

# Machine-readable output
bugpilot investigate list --status open -o json \\
  | jq '.items[] | {id, title, severity}'

# Create and capture investigation ID
INV_ID=\$(bugpilot incident triage "Deploy check failed" \\
  --service payment-service --severity high -o json \\
  | jq -r '.id')

# Use stored context for subsequent commands
export BUGPILOT_INVESTIGATION=\$INV_ID
bugpilot evidence collect --label "CI logs" --kind log_snapshot \\
  --source "github://actions?run_id=\$GITHUB_RUN_ID" \\
  --summary "Build failed at step: unit-tests"
bugpilot hypotheses list
\`\`\``,
  },

  "api-reference": {
    slug: "api-reference",
    title: "API Reference",
    category: "Reference",
    content: `# API Reference

The BugPilot REST API follows standard HTTP conventions. All endpoints are versioned under \`/api/v1/\`. Request and response bodies use JSON (\`Content-Type: application/json\`).

---

## Authentication

All endpoints except \`/auth/activate\` require a valid JWT in the Authorization header:

\`\`\`
Authorization: Bearer <access_token>
\`\`\`

Tokens expire after **1 hour**. Use the refresh endpoint to get a new token without re-activating.

---

## Auth Endpoints

### \`POST /api/v1/auth/activate\`

Exchange a license key for access and refresh tokens.

**Request:**
\`\`\`json
{
  "license_key": "bp_T7zK9mNvXq...",
  "email": "alice@acme.com",
  "display_name": "Alice Smith",
  "device_fingerprint": "sha256_of_hardware_uuid_and_system"
}
\`\`\`

**Response \`200\`:**
\`\`\`json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "org_id": "org_acme",
  "user_id": "usr_a3f8c2"
}
\`\`\`

---

### \`POST /api/v1/auth/refresh\`

Exchange a refresh token for a new access token.

**Request:**
\`\`\`json
{
  "refresh_token": "eyJ..."
}
\`\`\`

**Response \`200\`:** Same structure as \`/auth/activate\`.

---

### \`POST /api/v1/auth/logout\`

Revoke the current session. Returns \`204 No Content\`.

---

### \`GET /api/v1/auth/whoami\`

Return the current user's identity.

**Response \`200\`:**
\`\`\`json
{
  "user_id": "usr_a3f8c2",
  "email": "alice@acme.com",
  "display_name": "Alice Smith",
  "role": "investigator",
  "org_id": "org_acme",
  "org_slug": "acme-corp"
}
\`\`\`

---

## Investigation Endpoints

### \`GET /api/v1/investigations\`

List investigations.

**Query params:** \`status\`, \`severity\`, \`page\` (default: 1), \`page_size\` (default: 20)

**Response \`200\`:** Array of investigation objects.

---

### \`POST /api/v1/investigations\`

Create a new investigation.

**Request:**
\`\`\`json
{
  "title": "High error rate on payment-service",
  "symptom": "HTTP 5xx rate above 5%",
  "severity": "critical",
  "linked_services": ["payment-service"],
  "description": "Optional longer context"
}
\`\`\`

**Response \`201\`:** Investigation object with \`id\`.

---

### \`GET /api/v1/investigations/{investigation_id}\`

Fetch a single investigation with full details.

---

### \`PATCH /api/v1/investigations/{investigation_id}\`

Update investigation fields.

**Request (all fields optional):**
\`\`\`json
{
  "title": "Updated title",
  "status": "in_progress",
  "severity": "high",
  "description": "Updated notes"
}
\`\`\`

---

### \`DELETE /api/v1/investigations/{investigation_id}\`

Permanently delete an investigation and all its evidence. Returns \`204\`.

---

## Evidence Endpoints

### \`GET /api/v1/evidence\`

List evidence items for an investigation.

**Query params:** \`investigation_id\` (required), \`kind\`, \`limit\`, \`offset\`

---

### \`POST /api/v1/evidence\`

Add an evidence item.

**Request:**
\`\`\`json
{
  "investigation_id": "inv_7f3a2b",
  "label": "payment-service error logs",
  "kind": "log_snapshot",
  "source": "datadog",
  "summary": "47 NullPointerException at UserService.java:142",
  "connector_id": "conn_dd_prod"
}
\`\`\`

**Response \`201\`:** Evidence object with \`id\`.

---

### \`GET /api/v1/evidence/{evidence_id}\`

Fetch a single evidence item.

---

### \`DELETE /api/v1/evidence/{evidence_id}\`

Delete an evidence item. Returns \`204\`.

---

## Hypothesis Endpoints

### \`GET /api/v1/hypotheses\`

List hypotheses for an investigation.

**Query params:** \`investigation_id\` (required), \`status\` (\`active\` / \`confirmed\` / \`rejected\`)

**Response \`200\`:** Array of hypothesis objects, sorted by \`rank\`.

---

### \`POST /api/v1/hypotheses\`

Create a hypothesis manually.

**Request:**
\`\`\`json
{
  "investigation_id": "inv_7f3a2b",
  "title": "Bad deployment introduced regression",
  "description": "Stripe SDK v4 changed preferences API contract",
  "confidence_score": 0.72,
  "reasoning": "Deployment at 14:23 correlates with error onset at 14:31",
  "evidence_ids": ["ev_9c1d3e", "ev_a2b4f1"]
}
\`\`\`

---

### \`POST /api/v1/hypotheses/{hypothesis_id}/confirm\`

Mark a hypothesis as the confirmed root cause. Returns \`200\`.

---

### \`POST /api/v1/hypotheses/{hypothesis_id}/reject\`

Mark a hypothesis as rejected.

**Request (optional):**
\`\`\`json
{ "reason": "Ruled out — memory was stable during the incident" }
\`\`\`

---

### \`PATCH /api/v1/hypotheses/{hypothesis_id}\`

Update hypothesis fields.

---

## Action Endpoints

### \`GET /api/v1/actions\`

List actions for an investigation.

**Query params:** \`investigation_id\` (required), \`status\`

---

### \`POST /api/v1/actions\`

Create an action.

**Request:**
\`\`\`json
{
  "investigation_id": "inv_7f3a2b",
  "title": "Rollback deployment a3f8c2d",
  "action_type": "rollback",
  "risk_level": "low",
  "description": "Revert Stripe SDK v4 update",
  "hypothesis_id": "hyp_f3a1d2",
  "rollback_plan": "git revert a3f8c2d && redeploy"
}
\`\`\`

**Response \`201\`:** Action object with \`id\` and \`status: pending\`.

---

### \`POST /api/v1/actions/{action_id}/approve\`

Approve an action (requires \`approver\` or \`admin\` role). Returns \`200\`.

---

### \`POST /api/v1/actions/{action_id}/run\`

Execute an action. Returns \`200\` with the updated action object.

---

### \`POST /api/v1/actions/{action_id}/dry-run\`

Simulate an action without making any changes. Returns the same response shape as \`/run\` but no side effects are applied.

---

### \`POST /api/v1/actions/{action_id}/cancel\`

Cancel a pending or approved action. Returns \`200\`.

---

## Graph Endpoints

### \`GET /api/v1/graph/timeline\`

Return the investigation timeline as an ordered list of events.

**Query params:** \`investigation_id\` (required)

### \`GET /api/v1/graph/causal/{investigation_id}\`

Return the causal graph as nodes and weighted edges.

---

## Export Endpoints

### \`GET /api/v1/export/json/{investigation_id}\`

Export the full investigation bundle as JSON.

### \`GET /api/v1/export/markdown/{investigation_id}\`

Export a Markdown incident report.

---

## Webhook Endpoints

These endpoints receive alerts from monitoring platforms. Requests must include a valid HMAC signature.

| Method | Path | Source |
|--------|------|--------|
| POST | \`/api/v1/webhooks/datadog\` | Datadog |
| POST | \`/api/v1/webhooks/grafana\` | Grafana |
| POST | \`/api/v1/webhooks/cloudwatch\` | AWS CloudWatch (SNS) |
| POST | \`/api/v1/webhooks/pagerduty\` | PagerDuty |

All webhook endpoints return \`200\` on success or \`401\` on signature failure. Rate limit: 100 requests/min per IP + org.

---

## Admin Endpoints

All admin endpoints require the \`admin\` role.

### Connectors

| Method | Path | Description |
|--------|------|-------------|
| GET | \`/api/v1/admin/connectors\` | List configured connectors |
| POST | \`/api/v1/admin/connectors\` | Add a connector |
| DELETE | \`/api/v1/admin/connectors/{id}\` | Remove a connector |
| GET | \`/api/v1/admin/connectors/validate\` | Validate all connectors |

### Users

| Method | Path | Description |
|--------|------|-------------|
| GET | \`/api/v1/admin/users\` | List users |
| PATCH | \`/api/v1/admin/users/{id}\` | Update role |
| DELETE | \`/api/v1/admin/users/{id}\` | Deactivate user |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| GET | \`/api/v1/admin/webhooks\` | List webhook configs |
| POST | \`/api/v1/admin/webhooks\` | Register webhook |
| DELETE | \`/api/v1/admin/webhooks/{id}\` | Remove webhook |

### Org Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | \`/api/v1/admin/org/settings\` | Get org settings |
| PATCH | \`/api/v1/admin/org/settings\` | Update settings (retention, etc.) |

### Audit Log

| Method | Path | Description |
|--------|------|-------------|
| GET | \`/api/v1/admin/audit-logs\` | Query audit log |

---

## Health Endpoints

| Path | Description |
|------|-------------|
| \`GET /health\` | Liveness — returns \`{"status": "ok"}\` |
| \`GET /health/ready\` | Readiness — checks database connectivity |
| \`GET /metrics\` | Prometheus metrics |
| \`GET /openapi.json\` | OpenAPI specification |
| \`GET /docs\` | Swagger UI |

---

## Error Responses

All errors use standard HTTP status codes with a JSON body:

\`\`\`json
{
  "detail": "Human-readable error message"
}
\`\`\`

| Status | Meaning |
|--------|---------|
| \`400\` | Bad request — invalid input |
| \`401\` | Unauthorized — missing or invalid token |
| \`403\` | Forbidden — insufficient role |
| \`404\` | Not found |
| \`422\` | Validation error — request body failed schema validation |
| \`429\` | Rate limit exceeded |
| \`500\` | Internal server error |`,
  },

  architecture: {
    slug: "architecture",
    title: "Architecture",
    category: "Reference",
    content: `# Architecture Overview

BugPilot turns a vague symptom — "payment service is returning errors" — into ranked, evidence-backed root cause hypotheses with suggested safe actions. This document explains the system design and data flow.

---

## System Diagram

\`\`\`
┌──────────────────────────────────────────────────────────────────┐
│  User's Machine                                                  │
│                                                                  │
│   bugpilot CLI (macOS / Windows binary)                          │
│       │                                                          │
└───────┼──────────────────────────────────────────────────────────┘
        │  HTTPS  (api.bugpilot.io)
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  BugPilot Cloud Service                                          │
│                                                                  │
│   FastAPI REST API  (/api/v1/...)                                 │
│       │                    │                                     │
│       ▼                    ▼                                     │
│   PostgreSQL DB        Evidence Collectors                       │
│                             │                                    │
│                    ┌────────┼────────┐                           │
│                    ▼        ▼        ▼                           │
│               Datadog   Grafana   CloudWatch                     │
│               GitHub    K8s       PagerDuty                      │
│                                                                  │
│   Hypothesis Engine                                              │
│       ├── Pass 1: Rule-based patterns                            │
│       ├── Pass 2: Graph correlation                              │
│       ├── Pass 3: Historical reranking                           │
│       ├── Pass 4: LLM synthesis (optional)                       │
│       ├── Pass 5: Deduplication                                  │
│       └── Pass 6: Final ranking                                  │
└──────────────────────────────────────────────────────────────────┘
\`\`\`

---

## Core Concepts

### Investigation

The central unit of work. An investigation holds a title, symptom, severity, linked services, timeline of events, and references to all evidence, hypotheses, and actions.

Status lifecycle: \`open\` → \`in_progress\` → \`resolved\` → \`closed\`

### Evidence

A normalized snapshot of a data point from a monitoring source. Evidence is typed by kind:

| Kind | Description |
|------|-------------|
| \`log_snapshot\` | Log lines or error summaries |
| \`metric_snapshot\` | Metric values at a point in time |
| \`trace\` | Distributed trace data |
| \`event\` | Deployment, config change, or system event |
| \`config_diff\` | Before/after config comparison |
| \`topology\` | Service dependency or infrastructure topology |
| \`custom\` | Free-form evidence from any source |

Each evidence item has a \`reliability_score\` (0–1), an \`is_redacted\` flag, and an optional \`connector_id\` attributing it to a configured source.

### Investigation Graph

BugPilot builds a directed graph of causal relationships between evidence items. Graph edges are weighted by temporal proximity, service overlap, and signal type correlation. The graph drives the second pass of hypothesis generation.

### Hypothesis Engine — 6-Pass Pipeline

1. **Rule-based:** Matches evidence patterns against a library of known failure signatures (bad deployment, OOMKill, dependency degradation, config error, etc.)
2. **Graph correlation:** Traverses the investigation graph to find causal chains
3. **Historical reranking:** Compares current evidence patterns to resolved past investigations for the same org
4. **LLM synthesis:** (Optional) Sends a redacted evidence summary to the configured LLM provider (\`openai\`, \`anthropic\`, \`azure_openai\`, \`gemini\`, \`ollama\`, or \`openai_compatible\`) for open-ended hypothesis generation
5. **Deduplication:** Merges near-duplicate hypotheses using title similarity and evidence overlap
6. **Final ranking:** Sorts by confidence score, assigns ranks

### Actions

Proposed remediation steps. Each action has:
- A **risk level** (\`safe\` / \`low\` / \`medium\` / \`high\` / \`critical\`)
- An **approval gate** — medium and above require an \`approver\` or \`admin\` before execution
- A **rollback plan** — documented steps to undo the action
- A **dry-run mode** — simulates the action without making changes

---

## Privacy and Security

### PII Redaction

Before evidence summaries are sent to an LLM, BugPilot's privacy redactor strips:

- Email addresses
- Phone numbers
- JWT and Bearer tokens
- Payment card numbers (PAN)
- AWS access keys and secrets
- PEM private keys
- IP addresses (configurable)
- Custom regex patterns (per org)

A hard safety check in the hypothesis engine raises an error if non-redacted content is detected at the LLM boundary — this is enforced in code, not policy.

### Authentication

- License keys activate a device and exchange for a short-lived JWT (1-hour expiry) plus a refresh token
- Device fingerprint (SHA-256 of hardware UUID + system info) is recorded at activation
- Tokens are stored at \`~/.config/bugpilot/credentials.json\` with \`600\` permissions
- All API requests use \`Authorization: Bearer <token>\`

### Org Isolation

Every database query is scoped to \`org_id\`. Cross-tenant queries are architecturally impossible — the \`org_id\` is derived from the verified JWT, not from a user-supplied parameter.

### Credential Encryption

Connector credentials are encrypted with Fernet (symmetric AES-128-CBC + HMAC-SHA256) before storage. The Fernet key is a required environment variable and must be managed in a secrets manager in production.

---

## Connectors

Evidence collection is concurrent across all configured connectors. Each connector runs with:
- Request timeout: 30 seconds
- Collection timeout: 45 seconds (connector is marked degraded if exceeded)
- Retry policy: exponential backoff with jitter, max 3 attempts, on 429 / 5xx

Connector failures are graceful — other connectors continue unaffected.

---

## Data Model

Key tables (21 total):

| Table | Description |
|-------|-------------|
| \`organisations\` | Tenant root, holds settings and retention config |
| \`users\` | User accounts with role and org membership |
| \`license_activations\` | Device activations and token refresh history |
| \`investigations\` | Investigation workspace |
| \`investigation_timeline\` | Timestamped events within an investigation |
| \`evidence_items\` | Normalized evidence with metadata and payload reference |
| \`hypotheses\` | Generated hypotheses with confidence scores and evidence citations |
| \`actions\` | Proposed remediation actions with risk and approval state |
| \`connectors\` | Configured monitoring integrations (credentials encrypted) |
| \`webhooks\` | Registered webhook sources and secrets |
| \`audit_logs\` | Append-only record of all write operations |
| \`llm_usage_logs\` | LLM token usage per investigation |

---

## Observability

### Metrics (Prometheus)

Available at \`/metrics\` on the backend:

| Metric | Description |
|--------|-------------|
| \`bugpilot_activations_total\` | CLI activations |
| \`bugpilot_active_investigations\` | Current open investigations |
| \`bugpilot_investigation_duration_seconds\` | Time from open to resolved |
| \`bugpilot_time_to_first_hypothesis_seconds\` | Hypothesis generation latency |
| \`bugpilot_connector_errors_total\` | Connector fetch errors by connector |
| \`bugpilot_connector_rate_limits_total\` | Rate limit hits by connector |
| \`bugpilot_webhook_verification_failures_total\` | Failed webhook signature verifications |
| \`bugpilot_llm_requests_total\` | LLM requests by provider |
| \`bugpilot_llm_tokens_total\` | LLM token usage (prompt + completion) |
| \`bugpilot_http_requests_total\` | API request counts |
| \`bugpilot_http_request_duration_seconds\` | API response latency |

### Structured Logging

All log output is structured JSON via structlog. Log entries include: \`timestamp\`, \`level\`, \`event\`, \`investigation_id\`, \`org_id\`, \`connector\`, \`duration_ms\`, and other context fields as applicable.`,
  },

  deployment: {
    slug: "deployment",
    title: "Deployment",
    category: "Self-Hosting",
    content: `# Self-Hosting BugPilot

:::info
This guide is for teams that want to run BugPilot on their own infrastructure. If you are using the hosted service at bugpilot.io, you do not need this guide — just [download the CLI](/docs/getting-started) and activate it.
:::

BugPilot's backend is a stateless FastAPI service backed by PostgreSQL, making it straightforward to deploy on any container platform.

---

## Prerequisites

- PostgreSQL 14+
- Docker and Docker Compose (for the quick start)
- A Fernet key and JWT secret (generated below)
- Optional: an LLM API key (OpenAI, Anthropic, Azure OpenAI, Gemini, Ollama, or OpenAI-compatible)

---

## Generating Required Secrets

Before deploying, generate the two required secrets:

\`\`\`bash
# JWT_SECRET — 64-character hex string
python3 -c 'import secrets; print(secrets.token_hex(32))'

# FERNET_KEY — symmetric encryption key for connector credentials
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
\`\`\`

Store these in a secrets manager (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault, etc.). Do not commit them to source control.

---

## Docker Compose (Single Host / Staging)

\`\`\`bash
# 1. Set environment variables
export DATABASE_URL="postgresql+asyncpg://bugpilot:yourpassword@postgres:5432/bugpilot"
export JWT_SECRET="your-64-char-hex-string"
export FERNET_KEY="your-fernet-key"

# 2. Start the services
docker compose up -d

# 3. Apply database migrations
docker compose exec backend alembic upgrade head

# 4. Verify the service is healthy
curl http://localhost:8000/health
# {"status": "ok"}
\`\`\`

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| \`DATABASE_URL\` | Yes | — | \`postgresql+asyncpg://user:pass@host/db\` |
| \`JWT_SECRET\` | Yes | — | 64-char hex string for JWT signing |
| \`FERNET_KEY\` | Yes | — | Fernet key for encrypting connector credentials |
| \`LOG_LEVEL\` | No | \`info\` | \`debug\` / \`info\` / \`warning\` / \`error\` |
| \`EVIDENCE_TTL_MINUTES\` | No | \`10080\` | Raw payload TTL (default: 7 days) |
| \`LLM_PROVIDER\` | No | — | \`openai\` / \`anthropic\` / \`azure_openai\` / \`gemini\` / \`ollama\` / \`openai_compatible\` |
| \`LLM_API_KEY\` | If using a cloud LLM | — | API key for the configured LLM provider |
| \`LLM_MODEL\` | No | provider default | Model name override |
| \`LLM_BASE_URL\` | If using Azure / Ollama / openai_compatible | — | Base URL for the LLM endpoint |
| \`LLM_AZURE_DEPLOYMENT\` | If using Azure OpenAI | — | Azure deployment name |
| \`LLM_AZURE_API_VERSION\` | If using Azure OpenAI | — | Azure API version |

---

## Kubernetes

### Namespace and Secrets

\`\`\`bash
kubectl create namespace bugpilot

kubectl create secret generic bugpilot-secrets \\
  --namespace bugpilot \\
  --from-literal=DATABASE_URL="postgresql+asyncpg://bugpilot:\$DB_PASS@postgres:5432/bugpilot" \\
  --from-literal=JWT_SECRET="\$JWT_SECRET" \\
  --from-literal=FERNET_KEY="\$FERNET_KEY"
\`\`\`

### API Deployment

\`\`\`yaml
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
\`\`\`

### Migration Job

\`\`\`yaml
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
\`\`\`

### Daily Retention Purge CronJob

\`\`\`yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bugpilot-retention
  namespace: bugpilot
spec:
  schedule: "0 2 * * *"
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
\`\`\`

---

## AWS ECS (Fargate)

\`\`\`json
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
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/DATABASE_URL"},
        {"name": "JWT_SECRET",   "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/JWT_SECRET"},
        {"name": "FERNET_KEY",   "valueFrom": "arn:aws:ssm:us-east-1:ACCOUNT:parameter/bugpilot/FERNET_KEY"}
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
\`\`\`

---

## PostgreSQL

### Recommended Settings

\`\`\`sql
-- Increase max connections for asyncpg connection pool
ALTER SYSTEM SET max_connections = 200;

-- Enable query monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
\`\`\`

### Managed Database Options

| Platform | Recommended service |
|----------|-------------------|
| AWS | RDS PostgreSQL 14+ or Aurora PostgreSQL |
| GCP | Cloud SQL for PostgreSQL |
| Azure | Azure Database for PostgreSQL |
| Self-hosted | PostgreSQL 14+ |

Ensure the connection string uses asyncpg SSL mode for managed databases:

\`\`\`
postgresql+asyncpg://user:pass@host/db?ssl=require
\`\`\`

---

## Prometheus Scraping

\`\`\`yaml
scrape_configs:
  - job_name: bugpilot
    static_configs:
      - targets: ['bugpilot-api:8000']
    metrics_path: /metrics
    scrape_interval: 15s
\`\`\`

---

## Pointing the CLI at Your Self-Hosted Instance

When using a self-hosted backend, set the API URL before activating:

\`\`\`bash
export BUGPILOT_API_URL=https://your-bugpilot-instance.example.com
bugpilot auth activate --key bp_YOUR_LICENSE_KEY
\`\`\`

Or pass it per-command:

\`\`\`bash
bugpilot --api-url https://your-bugpilot-instance.example.com auth whoami
\`\`\`

---

## Security Checklist

Before going to production:

- \`JWT_SECRET\` is at least 32 bytes and stored in a secrets manager (not in \`.env\` files)
- \`FERNET_KEY\` is stored in a secrets manager and rotated on a schedule
- PostgreSQL is not publicly accessible — use a private subnet or VPC
- TLS is terminated at the load balancer (ALB / nginx / ingress controller)
- Webhook secrets are rotated periodically using the dual-secret grace window
- \`/metrics\` and \`/health\` endpoints are not publicly accessible
- Database credentials use a least-privilege role (SELECT, INSERT, UPDATE, DELETE only — no DDL)
- \`LOG_LEVEL=info\` in production (not \`debug\`, which may log request bodies)
- Org isolation verified — no cross-tenant queries are possible through the API`,
  },

  "developer-setup": {
    slug: "developer-setup",
    title: "Developer Setup",
    category: "Self-Hosting",
    content: `# Developer Setup Guide

:::info
This guide is for contributors building BugPilot from source. If you are a BugPilot user, [download the CLI binary](/docs/getting-started) — you do not need this guide.
:::

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or Docker)
- Node.js 20+ (for the frontend website)
- Git

---

## Repository Structure

\`\`\`
bugpilot/
├── src/
│   ├── backend/                  # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/           # Route handlers
│   │   │   ├── connectors/       # Evidence source integrations
│   │   │   │   ├── datadog/
│   │   │   │   ├── grafana/
│   │   │   │   ├── cloudwatch/
│   │   │   │   ├── github/
│   │   │   │   ├── kubernetes/
│   │   │   │   └── pagerduty/
│   │   │   ├── core/             # Config, DB, security, RBAC, logging
│   │   │   ├── graph/            # Investigation graph engine
│   │   │   ├── hypothesis/       # 6-pass hypothesis pipeline
│   │   │   ├── llm/              # LLM providers and service layer
│   │   │   ├── models/           # SQLAlchemy ORM models
│   │   │   ├── privacy/          # PII redaction pipeline
│   │   │   ├── schemas/          # Pydantic request/response schemas
│   │   │   ├── services/         # Domain services
│   │   │   ├── webhooks/         # Webhook handlers
│   │   │   └── workers/          # Evidence collector
│   │   ├── migrations/           # Alembic migrations
│   │   ├── tests/                # pytest test suite
│   │   └── pyproject.toml
│   ├── cli/                      # typer CLI (source for the binary)
│   │   ├── bugpilot/
│   │   │   ├── auth/             # License activation
│   │   │   ├── commands/         # CLI command groups
│   │   │   └── output/           # human / json / verbose formatters
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── docs/                     # Documentation
├── fixtures/                     # Sample configs and webhook payloads
└── docker-compose.yml
\`\`\`

---

## Backend Setup

\`\`\`bash
cd src/backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Set required environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost/bugpilot_dev?ssl=disable"
export JWT_SECRET="dev-only-secret-do-not-use-in-production-1234567890abcdef"
export FERNET_KEY="\$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export LOG_LEVEL="debug"

# Create the database
createdb bugpilot_dev

# Run migrations
alembic upgrade head

# Start the API with live reload
uvicorn app.main:app --reload --port 8000
\`\`\`

The API is now running at \`http://localhost:8000\`. Swagger UI is at \`http://localhost:8000/docs\`.

---

## CLI Setup (for development)

\`\`\`bash
cd src/cli

# Install in editable mode
pip install -e .

# Point at your local backend
export BUGPILOT_API_URL=http://localhost:8000

# Verify
bugpilot --version
\`\`\`

:::info
The distributed CLI binary is compiled from this source. Users never install from source — they download the pre-built binary from bugpilot.io.
:::

---

## Running Tests

The test suite uses an in-memory SQLite database — no running PostgreSQL needed.

\`\`\`bash
cd src/backend

# Run all tests
pytest

# Run a specific file
pytest tests/test_hypothesis.py -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run tests matching a keyword
pytest -k "test_dedup" -v
\`\`\`

The test suite uses \`sqlite+aiosqlite:///:memory:\` via a cross-dialect \`JSONB\` TypeDecorator in \`app/models/all_models.py\` that routes to \`JSON\` on SQLite automatically.

---

## Code Style

- **Type hints** on all function signatures
- **Async/await** throughout — no sync blocking calls in API handlers or connectors
- **structlog** for all logging — never \`print()\`
- **Pydantic v2** with \`ConfigDict\` (not the deprecated \`class Config\`)
- **SQLAlchemy 2.0** declarative style with \`Mapped\` / \`mapped_column\`

---

## Adding a New API Endpoint

1. Add a route handler to the appropriate file in \`app/api/v1/\`
2. Add request/response Pydantic schemas to \`app/schemas/base.py\`
3. Mount the router in \`app/main.py\` if it's a new file
4. Write tests in \`backend/tests/\`

\`\`\`python
# app/api/v1/my_feature.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.rbac import TokenPayload, require_role, Role

router = APIRouter(prefix="/my-feature", tags=["my-feature"])

class MyFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str

@router.get("/{item_id}", response_model=MyFeatureResponse)
async def get_item(
    item_id: str,
    current_user: TokenPayload = Depends(require_role(Role.viewer)),
    db: AsyncSession = Depends(get_db),
):
    ...
\`\`\`

---

## Adding a New Connector

1. Create \`app/connectors/myplatform/__init__.py\` and \`connector.py\`
2. Subclass \`BaseConnector\` from \`app.connectors.base\`
3. Implement \`capabilities()\`, \`validate()\`, and \`fetch_evidence()\`
4. Add a value to the \`ConnectorType\` enum in \`app/models/all_models.py\`
5. Register the connector in the connector factory
6. Add a sample config to \`fixtures/sample_configs/sample_connector_config.yaml\`
7. Write tests in \`backend/tests/test_connectors.py\`

---

## Database Migrations

When you modify \`app/models/all_models.py\`, generate a new Alembic migration:

\`\`\`bash
cd src/backend

# Auto-generate from model diff
alembic revision --autogenerate -m "add_my_new_column"

# Review the generated file in migrations/versions/
# Always review before applying — autogenerate is not perfect

# Apply
alembic upgrade head

# Rollback one step
alembic downgrade -1
\`\`\`

---

## Common Issues

### \`FERNET_KEY\` is not valid

Generate a proper key:

\`\`\`bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
\`\`\`

### \`asyncpg\` SSL error on local dev

Add \`?ssl=disable\` to the local database URL:

\`\`\`
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/bugpilot_dev?ssl=disable
\`\`\`

### \`aiosqlite\` not found (test suite)

\`\`\`bash
pip install aiosqlite
\`\`\`

---

## Pull Request Guidelines

1. Run the full test suite before submitting: \`pytest\`
2. Add tests for any new feature or bug fix
3. Keep changes focused — one feature or fix per PR
4. Update the relevant doc file if your change affects user-facing behaviour
5. Ensure no Pydantic deprecation warnings (\`class Config\` → \`model_config = ConfigDict(...)\`)`,
  },

  troubleshooting: {
    slug: "troubleshooting",
    title: "Troubleshooting",
    category: "Support",
    content: `# Troubleshooting Guide

Common issues and how to resolve them.

---

## CLI Issues

### \`bugpilot: command not found\`

The CLI binary is not on your \`PATH\`.

**macOS (Homebrew):** Homebrew adds the binary automatically. Try opening a new terminal window, or run:
\`\`\`bash
brew link bugpilot
\`\`\`

**macOS (.pkg installer):** The installer places the binary at \`/usr/local/bin/bugpilot\`. If it's not found, check that \`/usr/local/bin\` is in your PATH:
\`\`\`bash
echo \$PATH | tr ':' '\\n' | grep /usr/local/bin
\`\`\`

**Windows (Scoop):** Scoop adds its shims directory to PATH automatically. Try opening a new PowerShell or Command Prompt window.

**Windows (.msi installer):** Open a new terminal window after installation. If still not found, add the install directory to your PATH manually in **System Properties → Environment Variables**.

---

### \`Error: Could not connect to BugPilot API\`

The CLI cannot reach \`https://api.bugpilot.io\`.

- Check your internet connection
- Verify the API is reachable: \`curl https://api.bugpilot.io/health\`
- If you're using a custom API URL (self-hosted), check \`BUGPILOT_API_URL\` is set correctly
- Check if a corporate firewall or proxy is blocking outbound HTTPS

---

### \`401 Unauthorized\`

Your session has expired or credentials are invalid.

Re-activate the CLI:
\`\`\`bash
bugpilot auth activate --key bp_YOUR_LICENSE_KEY --secret YOUR_API_SECRET
\`\`\`

Or check who you're currently logged in as:
\`\`\`bash
bugpilot auth whoami
\`\`\`

If credentials are corrupted, clear them and re-activate:
\`\`\`bash
rm ~/.config/bugpilot/credentials.json
bugpilot auth activate --key bp_YOUR_LICENSE_KEY --secret YOUR_API_SECRET
\`\`\`

---

### \`403 Forbidden — insufficient role\`

Your account role does not have permission for this action.

\`\`\`
✗ Error: 403 Forbidden — insufficient role for this action
  Your role: investigator
  Required:  approver
\`\`\`

Ask your admin to assign you the required role. See [Manage Users and Roles](/docs/rbac).

---

### \`fix run\` asks for confirmation before executing

\`bugpilot fix run\` always shows the action details and prompts before executing. Use \`--yes\` / \`-y\` to skip the prompt:

\`\`\`bash
bugpilot fix run act_d2f4e1 --yes
\`\`\`

---

## Evidence Issues

### Hypotheses have low confidence or are capped at 40%

\`\`\`
⚠ Evidence from a single source only. Confidence scores capped at 40%.
  Add evidence from a second source to improve hypothesis quality.
\`\`\`

Add evidence from at least one additional source. Even a brief metric snapshot or deployment event significantly improves hypothesis accuracy.

---

### No hypotheses generated

Hypotheses require:
1. At least one evidence item attached to the investigation
2. At least one service name recorded (via \`--service\` on triage or in evidence)
3. Evidence with sufficient content in the summary field

If you have evidence but still see no hypotheses, try updating the investigation to set a service:
\`\`\`bash
bugpilot investigate update inv_7f3a2b --description "Affects: payment-service"
\`\`\`

---

## Webhook Issues

### \`401\` on webhook delivery

The webhook signature does not match.

- Verify the webhook secret registered in BugPilot matches the secret configured in your monitoring platform exactly (no extra spaces or encoding differences)
- If you recently rotated the secret, allow up to 1 hour for the grace window to expire
- Check the \`bugpilot_webhook_verification_failures_total\` metric for patterns

---

### Webhook received but no investigation created

- Check the BugPilot API structured logs for the webhook receipt event
- Verify the payload format matches the expected schema for your source (Datadog, Grafana, CloudWatch, or PagerDuty)
- If the dedup check matched an existing open investigation, the webhook will have updated it rather than creating a new one — check \`bugpilot investigate list --status open\`

---

## Action Approval Issues

### \`fix run\` fails with "approval required"

Actions with risk level \`medium\`, \`high\`, or \`critical\` require approval from an \`approver\` or \`admin\` before they can be run.

\`\`\`bash
# Ask an approver to run:
bugpilot fix approve act_d2f4e1

# Then run:
bugpilot fix run act_d2f4e1 --yes
\`\`\`

---

## Export Issues

### \`export markdown\` produces empty sections

Sections like **Root Cause** are empty if no hypothesis has been confirmed. Confirm the root cause hypothesis first:

\`\`\`bash
bugpilot hypotheses confirm hyp_f3a1d2
bugpilot export markdown inv_7f3a2b
\`\`\`

---

## Getting More Help

- **Verbose output:** Add \`-o verbose\` to any command to see full request/response details
- **GitHub Issues:** https://github.com/skonlabs/bugpilot/issues
- **Docs:** [bugpilot.io/docs](https://bugpilot.io/docs)`,
  },
};

export function getDocPage(slug: string): DocPage | undefined {
  return docsPages[slug];
}

export function getAdjacentPages(slug: string): { prev?: DocPage; next?: DocPage } {
  const allSlugs = docsCategories.flatMap((cat) => cat.items);
  const idx = allSlugs.indexOf(slug);
  return {
    prev: idx > 0 ? docsPages[allSlugs[idx - 1]] : undefined,
    next: idx < allSlugs.length - 1 ? docsPages[allSlugs[idx + 1]] : undefined,
  };
}
