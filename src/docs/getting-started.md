# Getting Started with BugPilot

BugPilot is a CLI tool that helps you debug production incidents. You install it on your machine, connect it to your observability tools, and use it to find root causes — either on demand when something breaks, or automatically when alerts fire.

---

## Step 1: Register

Go to [bugpilot.io](https://bugpilot.io) and create an account. After registration, copy your **license key** and **API secret** from the credentials page.

---

## Step 2: Install the CLI

Choose your operating system:

### macOS (Intel & Apple Silicon, macOS 12+)

**Homebrew (recommended):**

```bash
brew install bugpilot/tap/bugpilot
```

**Installer package:**

Download the `.pkg` file from [bugpilot.io/download](https://bugpilot.io/download), open it, and follow the on-screen steps.

### Windows (64-bit, Windows 10+)

**Scoop:**

```powershell
scoop install bugpilot
```

**Installer:**

Download the `.msi` file from [bugpilot.io/download](https://bugpilot.io/download), run it, and follow the prompts.

### Confirm the install

Open a new terminal and run:

```bash
bugpilot --version
```

---

## Step 3: Activate

Activation links the CLI to your account. The first time you run this command, BugPilot displays its Terms of Service — you must accept them to proceed.

```bash
bugpilot auth activate --key YOUR_LICENSE_KEY --secret YOUR_API_SECRET
```

You will be prompted to accept the Terms of Service and enter your email:

```
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
```

BugPilot stores your session at `~/.config/bugpilot/credentials.json` (`600` permissions). You only need to activate once per machine.

Check who you're logged in as at any time:

```bash
bugpilot auth whoami
```

---

## Step 4: Connect Your Data Sources

BugPilot reads connector credentials from `~/.config/bugpilot/config.yaml`. There are two ways to configure it:

### Option A: Interactive wizard (recommended)

The `connector add` command walks you through each required field for the connector type you choose:

```bash
bugpilot connector add datadog
bugpilot connector add grafana
bugpilot connector add cloudwatch
bugpilot connector add github
bugpilot connector add kubernetes
bugpilot connector add pagerduty
```

Example:

```
Configure datadog connector

  API Key: ••••••••••••••••••••
  Application Key: ••••••••••••••••••••
  Site (e.g. datadoghq.com) [datadoghq.com]:

✓ Connector 'datadog' saved to ~/.config/bugpilot/config.yaml
i Run 'bugpilot connector test' to verify connectivity.
```

### Option B: Edit the config file directly

Create a starter config with all connector templates:

```bash
bugpilot config init
```

Then open `~/.config/bugpilot/config.yaml` in your editor and fill in your credentials. You can use `${VAR_NAME}` syntax to read values from environment variables:

```yaml
connectors:
  datadog:
    api_key: "${DD_API_KEY}"
    app_key: "${DD_APP_KEY}"
    site: "datadoghq.com"
  grafana:
    url: "https://grafana.example.com"
    api_token: "${GRAFANA_TOKEN}"
    org_id: "1"
```

### Verify connectivity

```bash
bugpilot connector test
```

```
  Testing datadog...  ✓ OK
  Testing grafana...  ✓ OK
```

| Connector | Data BugPilot can access |
|-----------|--------------------------|
| **Datadog** | Logs, metrics, traces, monitor alerts |
| **Grafana** | Metrics, alert notifications |
| **AWS CloudWatch** | Logs, metrics, alarms |
| **GitHub** | Commits, deployments, pull requests |
| **Kubernetes** | Pod status, events, logs |
| **PagerDuty** | Incident and alert history |

See [Connect Data Sources](./connectors.md) for required permissions and field details for each platform.

---

## Step 5: Investigate

BugPilot has two usage modes:

### On-Demand

When you notice an issue, open a terminal and describe what you're seeing. BugPilot queries your connected sources, builds a picture of what happened, and tells you what it thinks the root cause is.

```bash
# Start an investigation
bugpilot incident triage "Payment service errors spiking" \
  --symptom "HTTP 5xx rate above 5% since 14:31 UTC" \
  --severity critical \
  --service payment-service

# Attach evidence you've collected
bugpilot evidence collect \
  --investigation-id inv_7f3a2b \
  --label "error logs" \
  --kind log_snapshot \
  --source datadog \
  --summary "NullPointerException at UserService.java:142, started 14:31 UTC"

# See what BugPilot thinks the root cause is
bugpilot hypotheses list --investigation-id inv_7f3a2b

# When resolved, close the investigation
bugpilot investigate close inv_7f3a2b
```

See [On-Demand Investigation](./how-to-investigate.md) for the full workflow.

### Automatic

Set up webhooks so that when your monitoring tool fires an alert, BugPilot automatically creates an investigation. You open the terminal to find it already has evidence collected.

```bash
# Check what's waiting for you
bugpilot investigate list --status open

# Pick up an auto-created investigation
bugpilot incident status inv_7f3a2b
```

See [Automatic Mode — Webhooks](./how-to-webhooks.md) to set this up.

---

## Next Steps

- [On-Demand Investigation](./how-to-investigate.md) — full incident walkthrough
- [Automatic Mode — Webhooks](./how-to-webhooks.md) — auto-create investigations from alerts
- [Connect Data Sources](./connectors.md) — connector setup for each platform
- [CLI Reference](./cli-reference.md) — every command and flag
