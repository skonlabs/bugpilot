# Getting Started with BugPilot

BugPilot is a CLI tool you download and run from your terminal. It connects to the BugPilot cloud service to analyze logs, metrics, traces, deployments, and code changes — turning a vague production symptom into ranked, actionable root cause hypotheses.

---

## Step 1: Create an Account

Go to [bugpilot.io](https://bugpilot.io) and create a free account. After sign-up, your admin will issue you a license key from the **API Credentials** section of the dashboard.

---

## Step 2: Download and Install the CLI

### macOS (Intel & Apple Silicon, macOS 12+)

**Homebrew (recommended):**

```bash
brew install bugpilot/tap/bugpilot
```

**Direct download:**

Go to [bugpilot.io/download](https://bugpilot.io/download) and download the `.pkg` installer, then open it and follow the prompts.

### Windows (64-bit, Windows 10+)

**Scoop:**

```powershell
scoop install bugpilot
```

**Direct download:**

Go to [bugpilot.io/download](https://bugpilot.io/download) and download the `.msi` installer, then run it and follow the prompts.

### Verify the installation

Open a new terminal window and run:

```bash
bugpilot --version
# bugpilot 0.1.0
```

---

## Step 3: Activate the CLI

Activate BugPilot with your license key from the dashboard. You only need to do this once per machine.

```bash
bugpilot auth activate --key bp_YOUR_LICENSE_KEY
```

You will be prompted for your email address if not supplied:

```
Enter your email address: alice@acme.com

✓ Activated successfully!  Org: acme-corp | Role: investigator
```

Credentials are stored at `~/.config/bugpilot/credentials.json` (permissions `600`).

To check who you're logged in as at any time:

```bash
bugpilot auth whoami
```

---

## Step 4: Connect Your Observability Tools

Log into [bugpilot.io](https://bugpilot.io) → **Settings → Connectors** and add credentials for the tools your team uses:

| Connector | What BugPilot collects |
|-----------|----------------------|
| Datadog | Logs, metrics, traces, alerts |
| Grafana | Metrics, alerts |
| AWS CloudWatch | Logs, metrics, alarms |
| GitHub | Code commits, deployments |
| Kubernetes | Pod state, events, logs |
| PagerDuty | Incidents, alerts |

BugPilot works with a single connector, but produces the most accurate hypotheses when evidence comes from multiple sources.

See [Connector Setup](./connectors.md) for step-by-step credential instructions for each platform.

---

## Step 5: Run Your First Investigation

```bash
# 1. Open a new investigation for the affected service
bugpilot investigate create "High error rate on payment-service" \
  --symptom "HTTP 5xx rate above 5% since 14:30 UTC" \
  --severity high

# Output:
# ✓ Created  inv_7f3a2b
#   Title:    High error rate on payment-service
#   Severity: high
#   Status:   open

# 2. Add evidence — attach a log snapshot you've already retrieved
bugpilot evidence collect \
  --investigation-id inv_7f3a2b \
  --label "payment-service errors" \
  --kind log_snapshot \
  --source datadog \
  --summary "47 NullPointerException errors at UserService.java:142 since 14:31 UTC"

# 3. List the hypotheses BugPilot generated
bugpilot hypotheses list --investigation-id inv_7f3a2b

# Output:
# RANK  HYPOTHESIS                          CONFIDENCE  STATUS
#  1    Bad deployment introduced regression  72%       active
#  2    Memory exhaustion                     41%       active

# 4. Suggest a fix action for the top hypothesis
bugpilot fix suggest \
  --investigation-id inv_7f3a2b \
  "Rollback deployment a3f8c2d" \
  --type rollback \
  --risk low \
  --description "Revert Stripe SDK v4 update that correlates with error onset" \
  --rollback-plan "git revert a3f8c2d && redeploy"

# 5. Dry-run the action before applying
bugpilot fix run act_d2f4e1 --dry-run

# 6. When resolved, close the investigation
bugpilot investigate close inv_7f3a2b
```

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Investigation** | A named workspace for a single incident. Holds evidence, hypotheses, and actions. |
| **Evidence** | A normalized snapshot from a monitoring source — log, metric, trace, config diff, etc. |
| **Hypothesis** | A ranked root cause candidate with a confidence score and supporting evidence citations. |
| **Action** | A proposed remediation step, risk-rated and approval-gated before execution. |

---

## Next Steps

- [CLI Reference](./cli-reference.md) — every command and flag
- [Connector Setup](./connectors.md) — configure Datadog, Grafana, CloudWatch, etc.
- [How to Investigate an Incident](./how-to-investigate.md) — full end-to-end walkthrough
- [Architecture Overview](./architecture.md) — how evidence, graphs, and hypotheses work
- [Self-Hosting](./deployment.md) — run BugPilot on your own infrastructure (advanced)
