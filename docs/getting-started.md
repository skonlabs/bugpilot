# Getting Started with BugPilot

BugPilot is a CLI tool you download and run from your terminal. It connects to the BugPilot cloud service to analyze logs, metrics, traces, deployments, and code changes — turning a vague production symptom into ranked, actionable root cause hypotheses in seconds.

---

## Step 1: Create an Account

Go to [bugpilot.io](https://bugpilot.io) and create a free account. After sign-up, your admin will issue you a license key from the **API Credentials** section of the dashboard.

---

## Step 2: Download and Install the CLI

### macOS (Intel & Apple Silicon)

**Homebrew (recommended):**

```bash
brew install bugpilot/tap/bugpilot
```

**Direct download:**

Go to [bugpilot.io/download](https://bugpilot.io/download) and download the `.pkg` installer.

### Windows (64-bit, Windows 10+)

**Scoop:**

```powershell
scoop install bugpilot
```

**Direct download:**

Go to [bugpilot.io/download](https://bugpilot.io/download) and download the `.msi` installer.

### Verify the installation

```bash
bugpilot --version
```

---

## Step 3: Activate the CLI

Activate BugPilot with the license key from your dashboard:

```bash
bugpilot auth activate --key bp_YOUR_LICENSE_KEY
```

You'll be prompted for your email address if not provided via `--email`. After activation:

```
✓ Activated successfully!
  Org:   acme-corp
  Role:  investigator
```

Credentials are stored at `~/.config/bugpilot/credentials.json` (permissions `600`). You only need to activate once per machine.

---

## Step 4: Connect Your Observability Tools

Log into [bugpilot.io](https://bugpilot.io), go to **Settings → Connectors**, and add credentials for your tools (Datadog, Grafana, CloudWatch, GitHub, Kubernetes, PagerDuty). BugPilot works with one connector but produces the best hypotheses when evidence comes from multiple sources.

See [Connector Setup](./connectors.md) for step-by-step instructions.

---

## Step 5: Run Your First Investigation

```bash
# Open a new investigation
bugpilot investigate create \
  --title "High error rate on payment-service" \
  --service payment-service

# BugPilot prints:
# ✓ Investigation created: inv_7f3a2b...
#   Title:    High error rate on payment-service
#   Service:  payment-service
#   Status:   open

# Collect evidence from all configured connectors
bugpilot evidence collect inv_7f3a2b --since 2h

# View generated hypotheses, ranked by confidence
bugpilot hypotheses list inv_7f3a2b

# Get fix suggestions for the top hypothesis
bugpilot fix suggest inv_7f3a2b

# Dry-run a suggested action before applying
bugpilot fix run act_d2f4... --dry-run
```

---

## Verify Your Connection

```bash
bugpilot auth whoami
```

```
  User:  alice@acme.com
  Role:  investigator
  Org:   acme-corp
```

---

## Next Steps

- [CLI Reference](./cli-reference.md) — complete command documentation
- [Connector Setup](./connectors.md) — configure Datadog, Grafana, CloudWatch, etc.
- [How to Investigate an Incident](./how-to-investigate.md) — end-to-end walkthrough
- [Architecture Overview](./architecture.md) — how evidence, graphs, and hypotheses work
- [Self-Hosting](./deployment.md) — run BugPilot on your own infrastructure (advanced)
