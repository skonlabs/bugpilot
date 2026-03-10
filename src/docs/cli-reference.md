# CLI Reference

The `bugpilot` CLI is the primary interface for interacting with the BugPilot platform. Every command supports three output formats via the global `--output` / `-o` flag.

---

## Global Options

```
bugpilot [OPTIONS] COMMAND [ARGS]...
```

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `--api-url TEXT` | `BUGPILOT_API_URL` | `http://localhost:8000` | BugPilot backend URL |
| `-o, --output TEXT` | `BUGPILOT_OUTPUT` | `human` | Output format: `human` \| `json` \| `verbose` |
| `--no-color` | `NO_COLOR` | false | Disable Rich colour output |
| `-v, --version` | — | — | Print version and exit |

### Output Formats

**`human`** (default) — Rich-formatted tables and panels with colour-coded status and severity. Best for terminal use.

**`json`** — Machine-readable JSON on stdout. Every command writes a single JSON object or array. Ideal for scripting and CI pipelines.

```bash
bugpilot investigate list -o json | jq '.[] | select(.status == "open")'
```

**`verbose`** — Includes all fields including internal metadata, formatted with syntax highlighting. Useful for debugging.

---

## `bugpilot auth` — Authentication

### `auth activate`

Activate a BugPilot license on this device.

```bash
bugpilot auth activate --license-key bp_<KEY>
```

| Option | Required | Description |
|--------|----------|-------------|
| `--license-key` | Yes | License key (format: `bp_...`) |

**Example:**

```
$ bugpilot auth activate --license-key bp_T7zK9mNvXq...

✓ License activated
  Org:        acme-corp
  Tier:       pro
  Seats:      8 / 10 available
  Expires:    2027-03-01
  Device ID:  dev_a3f8c2d1e9
```

Credentials are stored at `~/.config/bugpilot/credentials.json` with permissions `600`.

---

### `auth logout`

Revoke the current session and clear local credentials.

```bash
bugpilot auth logout
```

---

### `auth whoami`

Display the currently authenticated user and org.

```bash
bugpilot auth whoami
```

```
  User:  alice@acme.com
  Role:  investigator
  Org:   acme-corp
  Tier:  pro
```

---

## `bugpilot investigate` — Investigations

### `investigate list`

List all investigations for your org.

```bash
bugpilot investigate list [--status STATUS] [--service SERVICE] [--limit N]
```

| Option | Description |
|--------|-------------|
| `--status` | Filter: `open` \| `in_progress` \| `resolved` \| `closed` |
| `--service` | Filter by service name |
| `--limit` | Max results (default: 20) |

**Example:**

```
$ bugpilot investigate list --status open

  ID             TITLE                                 SERVICE           STATUS     STARTED
  inv_7f3a2b...  High error rate on payment-service    payment-service   open       2 hours ago
  inv_c1d9e0...  Database connection pool exhausted    orders-db         open       45 min ago
  inv_8a2f1c...  Latency spike - checkout flow         checkout-svc      open       12 min ago
```

---

### `investigate create`

Open a new investigation.

```bash
bugpilot investigate create \
  --title "TITLE" \
  --service SERVICE \
  [--severity critical|high|medium|low]
```

| Option | Required | Description |
|--------|----------|-------------|
| `--title` | Yes | Short description of the symptom |
| `--service` | Yes | Affected service name (must match connector service labels) |
| `--severity` | No | `critical` \| `high` \| `medium` \| `low` (default: `high`) |

---

### `investigate get`

Fetch full details of one investigation.

```bash
bugpilot investigate get <INVESTIGATION_ID>
```

---

### `investigate update`

Update investigation fields.

```bash
bugpilot investigate update <INVESTIGATION_ID> \
  [--title "NEW TITLE"] \
  [--status in_progress|resolved]
```

---

### `investigate close`

Mark an investigation as resolved and record the root cause.

```bash
bugpilot investigate close <INVESTIGATION_ID> \
  --root-cause "Description of what caused the issue"
```

---

## `bugpilot incident` — Incident Triage

### `incident triage`

Run automated triage on a new incoming alert or incident. BugPilot checks for existing open investigations (deduplication), creates or updates an investigation, collects initial evidence, and prints the top hypothesis.

```bash
bugpilot incident triage \
  --service SERVICE \
  --alert-name "ALERT_NAME" \
  [--severity critical|high|medium|low] \
  [--since DURATION]
```

| Option | Required | Description |
|--------|----------|-------------|
| `--service` | Yes | Affected service |
| `--alert-name` | Yes | Alert or incident name |
| `--severity` | No | Incident severity |
| `--since` | No | How far back to look for evidence (e.g. `2h`, `30m`, `1d`). Default: `1h` |

**Example:**

```
$ bugpilot incident triage \
    --service payment-service \
    --alert-name "HTTP 5xx rate > 5%" \
    --severity critical \
    --since 2h

  ⚡ Dedup check: No similar open investigations found
  ✓ Investigation created: inv_7f3a2b...
  ↓ Collecting evidence (4 connectors)...
    ✓ datadog/logs      (47 items, 0.3s)
    ✓ datadog/metrics   (12 items, 0.4s)
    ✓ github/deploys    (3 items, 0.2s)
    ✗ grafana/metrics   degraded: connection timeout
  ✓ Hypotheses generated (3)

  TOP HYPOTHESIS
  ───────────────────────────────────────────────────────
  Rank 1  │  Bad Deployment Introduced Regression      ▓▓▓▓▓▓▓▒ 72%
          │  A deployment at 14:23 UTC correlates with the onset
          │  of 5xx errors. Commit a3f8c2d: "Update Stripe SDK v4"
          │  may have introduced a breaking change.
  ───────────────────────────────────────────────────────
  Run: bugpilot fix suggest inv_7f3a2b
```

---

### `incident status`

Show the current status and summary of an ongoing incident.

```bash
bugpilot incident status <INVESTIGATION_ID>
```

---

## `bugpilot evidence` — Evidence

### `evidence collect`

Trigger evidence collection from all configured connectors for a given investigation.

```bash
bugpilot evidence collect <INVESTIGATION_ID> \
  [--since DURATION] \
  [--until DATETIME] \
  [--connector CONNECTOR_ID] \
  [--capability logs|metrics|traces|alerts|incidents|deployments]
```

| Option | Description |
|--------|-------------|
| `--since` | Duration string: `30m`, `2h`, `1d` (default: `1h`) |
| `--until` | ISO-8601 datetime. Default: now |
| `--connector` | Restrict to one connector ID |
| `--capability` | Restrict to one capability type |

**Example output:**

```
$ bugpilot evidence collect inv_7f3a2b --since 2h

  Collecting evidence (since 2h ago)...

  CONNECTOR            CAPABILITY    ITEMS    LATENCY    STATUS
  datadog              logs          47       0.34s      ok
  datadog              metrics       12       0.41s      ok
  datadog              alerts        3        0.28s      ok
  grafana              metrics       —        —          degraded: timeout
  github               deployments   2        0.19s      ok
  pagerduty            incidents     1        0.22s      ok

  Total: 65 items collected (1 connector degraded)
```

---

### `evidence list`

List evidence items for an investigation.

```bash
bugpilot evidence list <INVESTIGATION_ID> \
  [--capability logs|metrics|traces|alerts|incidents|deployments] \
  [--limit N]
```

---

### `evidence get`

Show the full normalized evidence item.

```bash
bugpilot evidence get <EVIDENCE_ID>
```

---

## `bugpilot hypotheses` — Hypotheses

### `hypotheses list`

List all hypotheses for an investigation, ranked by confidence.

```bash
bugpilot hypotheses list <INVESTIGATION_ID> [--status active|confirmed|rejected]
```

**Example:**

```
$ bugpilot hypotheses list inv_7f3a2b

  RANK  HYPOTHESIS                              CONFIDENCE  STATUS    SOURCE
  1     Bad Deployment Introduced Regression    72%         active    rule
  2     Memory Exhaustion                       58%         active    rule
  3     Upstream Dependency Degradation         41%         active    graph

  ⚠ Evidence from single source only (logs). Confidence scores are capped at 40%.
    Collect metrics or traces to improve hypothesis quality.
```

---

### `hypotheses confirm`

Mark a hypothesis as confirmed (the root cause).

```bash
bugpilot hypotheses confirm <HYPOTHESIS_ID>
```

---

### `hypotheses reject`

Mark a hypothesis as ruled out.

```bash
bugpilot hypotheses reject <HYPOTHESIS_ID> [--reason "REASON"]
```

---

## `bugpilot fix` — Remediation Actions

### `fix suggest`

Generate safe remediation actions for an investigation.

```bash
bugpilot fix suggest <INVESTIGATION_ID> [--hypothesis-id HYPOTHESIS_ID]
```

**Example:**

```
$ bugpilot fix suggest inv_7f3a2b

  SUGGESTED ACTIONS

  #1  Rollback deployment a3f8c2d                         RISK: low
      Expected effect: Restore previous stable version
      Rollback path:   git revert a3f8c2d && redeploy
      Approval needed: No

  #2  Increase memory limit to 1Gi                        RISK: medium
      Expected effect: Prevent OOMKill recurrence
      Rollback path:   Revert resource quota change
      Approval needed: Yes (approver role)

  #3  Temporarily disable Stripe SDK v4 feature flag      RISK: low
      Expected effect: Bypass potentially broken code path
      Rollback path:   Re-enable feature flag
      Approval needed: No
```

---

### `fix approve`

Approve a medium/high-risk action (requires `approver` role).

```bash
bugpilot fix approve <ACTION_ID> [--note "APPROVAL_NOTE"]
```

---

### `fix run`

Execute an approved action.

```bash
bugpilot fix run <ACTION_ID> [--dry-run]
```

| Option | Description |
|--------|-------------|
| `--dry-run` | Simulate the action without making changes. Prints what would happen. |

**Dry-run example:**

```
$ bugpilot fix run act_d2f4e1 --dry-run

  DRY RUN: Rollback deployment a3f8c2d
  ─────────────────────────────────────
  Would execute:
    1. git revert a3f8c2d
    2. docker build -t payment-service:rollback .
    3. kubectl set image deployment/payment-service app=payment-service:rollback

  Estimated downtime: 0s (rolling update)
  Risk assessment:    LOW — previous version was stable for 3 days

  To apply: bugpilot fix run act_d2f4e1
```

---

### `fix cancel`

Cancel a pending or approved action.

```bash
bugpilot fix cancel <ACTION_ID>
```

---

### `fix list`

List all actions for an investigation.

```bash
bugpilot fix list <INVESTIGATION_ID> [--status pending|approved|running|completed|cancelled]
```

---

## `bugpilot export` — Export

### `export json`

Export a complete investigation as structured JSON.

```bash
bugpilot export json <INVESTIGATION_ID> [--output-file FILE]
```

The exported JSON includes: investigation metadata, timeline, evidence summary (redacted, no raw payloads), all hypotheses with rankings, all actions and approval decisions, and outcome.

---

### `export markdown`

Export a human-readable incident report in Markdown format suitable for wikis, Confluence, or GitHub.

```bash
bugpilot export markdown <INVESTIGATION_ID> [--output-file FILE]
```

**Sample output (truncated):**

```markdown
# Incident Report: High error rate on payment-service
**ID:** inv_7f3a2b  **Severity:** critical  **Resolved:** 2024-01-15 16:42 UTC

## Timeline
| Time (UTC) | Event |
|------------|-------|
| 14:23      | Deployment a3f8c2d merged by alice@acme.com |
| 14:31      | HTTP 5xx rate exceeded 5% threshold |
| 14:33      | PagerDuty incident created |
| 14:35      | BugPilot investigation opened |

## Root Cause
Bad Deployment Introduced Regression (confidence: 72%)

## Actions Taken
1. ✓ Rollback deployment a3f8c2d (approved by bob@acme.com)
```

---

## Shell Completion

```bash
# bash
bugpilot --install-completion bash
source ~/.bashrc

# zsh
bugpilot --install-completion zsh
source ~/.zshrc

# fish
bugpilot --install-completion fish
```

---

## Using with CI/CD

In CI pipelines, use `--output json` and `BUGPILOT_API_URL` / `BUGPILOT_LICENSE_KEY` environment variables:

```yaml
# GitHub Actions example
- name: Triage deployment incident
  env:
    BUGPILOT_API_URL: ${{ secrets.BUGPILOT_URL }}
    BUGPILOT_LICENSE_KEY: ${{ secrets.BUGPILOT_KEY }}
  run: |
    bugpilot auth activate --license-key "$BUGPILOT_LICENSE_KEY"
    bugpilot incident triage \
      --service "$SERVICE" \
      --alert-name "Deployment smoke test failed" \
      --severity high \
      --since 15m \
      --output json > triage-result.json
    cat triage-result.json | jq '.top_hypothesis'
```
