# CLI Reference

The `bugpilot` CLI is the primary interface for the BugPilot platform. All commands support three output formats via the global `--output` / `-o` flag.

---

## Global Options

```
bugpilot [OPTIONS] COMMAND [ARGS]...
```

| Option | Short | Env var | Default | Description |
|--------|-------|---------|---------|-------------|
| `--api-url TEXT` | — | `BUGPILOT_API_URL` | `https://api.bugpilot.io` | BugPilot API URL |
| `--output TEXT` | `-o` | `BUGPILOT_OUTPUT` | `human` | Output format: `human` \| `json` \| `verbose` |
| `--no-color` | — | `NO_COLOR` | false | Disable colour output |
| `--version` | `-v` | — | — | Print version and exit |

### Output Formats

**`human`** (default) — Rich-formatted tables and panels with colour-coded status and severity. Best for interactive terminal use.

**`json`** — Machine-readable JSON on stdout. Ideal for scripting, CI pipelines, and programmatic use.

```bash
bugpilot investigate list -o json | jq '.[] | select(.status == "open")'
```

**`verbose`** — All fields including internal metadata, with syntax highlighting. Useful for debugging.

---

## `bugpilot auth` — Authentication

### `auth activate`

Activate BugPilot with your license key. Only needed once per machine.

```bash
bugpilot auth activate [--key KEY] [--email EMAIL] [--name NAME]
```

| Option | Short | Required | Env var | Description |
|--------|-------|----------|---------|-------------|
| `--key` | `-k` | Prompted if omitted | `BUGPILOT_LICENSE_KEY` | License key (`bp_...` format) |
| `--email` | `-e` | Prompted if omitted | — | Your email address |
| `--name` | — | No | — | Your display name |

**Example:**

```
$ bugpilot auth activate --key bp_T7zK9mNvXq...

✓ Activated successfully!  Org: acme-corp | Role: investigator
```

Credentials are stored at `~/.config/bugpilot/credentials.json` (permissions `600`).

---

### `auth logout`

Revoke the current session and clear stored credentials.

```bash
bugpilot auth logout
```

---

### `auth whoami`

Show the currently authenticated user.

```bash
bugpilot auth whoami
```

```
User:         alice@acme.com
Display name: Alice Smith
Role:         investigator
Org ID:       org_acme
User ID:      usr_a3f8c2
```

---

## `bugpilot investigate` — Investigations

### `investigate list`

List investigations for your org.

```bash
bugpilot investigate list [--status STATUS] [--severity SEVERITY] [--page N] [--page-size N]
```

| Option | Description |
|--------|-------------|
| `--status` | Filter: `open` \| `in_progress` \| `resolved` \| `closed` |
| `--severity` | Filter: `critical` \| `high` \| `medium` \| `low` |
| `--page` | Page number (default: 1) |
| `--page-size` | Results per page (default: 20) |

**Example:**

```
$ bugpilot investigate list --status open

  ID          TITLE                                  SEVERITY  STATUS     CREATED
  inv_7f3a2b  High error rate on payment-service     high      open       2h ago
  inv_c1d9e0  Database connection pool exhausted     critical  open       45m ago
  inv_8a2f1c  Latency spike - checkout flow          medium    open       12m ago
```

---

### `investigate create`

Open a new investigation.

```bash
bugpilot investigate create TITLE [--symptom TEXT] [--severity LEVEL] [--description TEXT]
```

| Argument/Option | Required | Description |
|-----------------|----------|-------------|
| `TITLE` | Yes | Short description of the issue (positional) |
| `--symptom, -s` | No | Observable symptom text |
| `--severity` | No | `critical` \| `high` \| `medium` \| `low` (default: `high`) |
| `--description` | No | Longer context or notes |

**Example:**

```
$ bugpilot investigate create "High error rate on payment-service" \
    --symptom "HTTP 5xx rate above 5%" \
    --severity high

✓ Created  inv_7f3a2b
  Title:    High error rate on payment-service
  Severity: high
  Status:   open
```

---

### `investigate get`

Fetch full details of one investigation.

```bash
bugpilot investigate get INVESTIGATION_ID
```

---

### `investigate update`

Update investigation fields.

```bash
bugpilot investigate update INVESTIGATION_ID \
  [--title TEXT] [--status STATUS] [--severity LEVEL] [--description TEXT]
```

| Option | Description |
|--------|-------------|
| `--title` | New title |
| `--status` | `open` \| `in_progress` \| `resolved` \| `closed` |
| `--severity` | `critical` \| `high` \| `medium` \| `low` |
| `--description` | Updated notes |

---

### `investigate close`

Mark an investigation as closed.

```bash
bugpilot investigate close INVESTIGATION_ID
```

---

### `investigate delete`

Permanently delete an investigation and all its evidence.

```bash
bugpilot investigate delete INVESTIGATION_ID [--yes]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--yes` | `-y` | Skip confirmation prompt |

---

## `bugpilot incident` — Incident Triage

### `incident triage`

Rapid triage shortcut: creates an investigation, records a timeline event, and triggers initial evidence collection in one step.

```bash
bugpilot incident triage TITLE [--symptom TEXT] [--severity LEVEL] [--service TEXT]
```

| Argument/Option | Required | Description |
|-----------------|----------|-------------|
| `TITLE` | Yes | Short incident description (positional) |
| `--symptom, -s` | No | Observable symptom |
| `--severity` | No | `critical` \| `high` \| `medium` \| `low` |
| `--service` | No | Affected service name |

**Example:**

```
$ bugpilot incident triage "HTTP 5xx rate > 5% on payment-service" \
    --symptom "Started at 14:31 UTC, 847 affected requests" \
    --severity critical \
    --service payment-service

✓ Investigation created: inv_7f3a2b
  Service: payment-service | Severity: critical
```

---

### `incident status`

Show a summary of evidence, hypotheses, and actions for an investigation.

```bash
bugpilot incident status INVESTIGATION_ID
```

```
  Investigation: inv_7f3a2b — High error rate on payment-service
  Status:        in_progress | Severity: critical

  Evidence:    12 items   Hypotheses: 3   Actions: 2
```

---

## `bugpilot evidence` — Evidence

Evidence items are normalized snapshots attached to an investigation. They can be sourced from your connected monitoring tools or added manually.

### `evidence list`

List evidence items for an investigation.

```bash
bugpilot evidence list --investigation-id ID [--kind KIND]
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--investigation-id` | `-i` | Yes | Investigation ID |
| `--kind` | `-k` | No | Filter by kind (see kinds below) |

**Evidence kinds:** `log_snapshot` \| `metric_snapshot` \| `trace` \| `event` \| `config_diff` \| `topology` \| `custom`

---

### `evidence collect`

Add an evidence item to an investigation.

```bash
bugpilot evidence collect \
  --investigation-id ID \
  --label LABEL \
  [--kind KIND] \
  [--source SOURCE] \
  [--summary TEXT] \
  [--connector-id CONNECTOR_ID]
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--investigation-id` | `-i` | Yes | Investigation to attach evidence to |
| `--label` | `-l` | Yes | Human-readable label for this evidence item |
| `--kind` | `-k` | No | Evidence kind (default: `custom`) |
| `--source` | — | No | Source system name (e.g. `datadog`, `grafana`) |
| `--summary` | `-s` | No | Text summary of what this evidence shows |
| `--connector-id` | — | No | ID of the configured connector that produced this |

**Example:**

```
$ bugpilot evidence collect \
    --investigation-id inv_7f3a2b \
    --label "payment-service error logs" \
    --kind log_snapshot \
    --source datadog \
    --summary "47 NullPointerException at UserService.java:142 since 14:31 UTC"

✓ Evidence added: ev_9c1d3e
```

---

### `evidence get`

Show the full details of one evidence item.

```bash
bugpilot evidence get EVIDENCE_ID
```

---

### `evidence delete`

Remove an evidence item.

```bash
bugpilot evidence delete EVIDENCE_ID
```

---

## `bugpilot hypotheses` — Hypotheses

### `hypotheses list`

List hypotheses for an investigation, ranked by confidence.

```bash
bugpilot hypotheses list --investigation-id ID [--status STATUS]
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--investigation-id` | `-i` | Yes | Investigation ID |
| `--status` | `-s` | No | Filter: `active` \| `confirmed` \| `rejected` |

**Example:**

```
$ bugpilot hypotheses list --investigation-id inv_7f3a2b

  RANK  HYPOTHESIS                              CONFIDENCE  STATUS   SOURCE
   1    Bad deployment introduced regression    72%         active   rule
   2    Memory exhaustion                       41%         active   rule
   3    Upstream dependency degradation         28%         active   graph
```

---

### `hypotheses create`

Manually add a hypothesis.

```bash
bugpilot hypotheses create \
  --investigation-id ID \
  TITLE \
  [--description TEXT] \
  [--confidence FLOAT] \
  [--reasoning TEXT] \
  [--evidence EVIDENCE_ID]...
```

| Argument/Option | Short | Required | Description |
|-----------------|-------|----------|-------------|
| `TITLE` | — | Yes | Hypothesis title (positional) |
| `--investigation-id` | `-i` | Yes | Investigation ID |
| `--description` | `-d` | No | Detailed description |
| `--confidence` | `-c` | No | Confidence score 0.0–1.0 |
| `--reasoning` | — | No | Explanation of the reasoning |
| `--evidence` | — | No | Evidence ID to cite (repeatable) |

**Example:**

```
$ bugpilot hypotheses create \
    --investigation-id inv_7f3a2b \
    "Config change disabled null check" \
    --confidence 0.65 \
    --evidence ev_9c1d3e \
    --evidence ev_a2b4f1

✓ Hypothesis created: hyp_f3a1d2
```

---

### `hypotheses confirm`

Mark a hypothesis as the confirmed root cause.

```bash
bugpilot hypotheses confirm HYPOTHESIS_ID
```

---

### `hypotheses reject`

Mark a hypothesis as ruled out.

```bash
bugpilot hypotheses reject HYPOTHESIS_ID
```

---

### `hypotheses update`

Update a hypothesis.

```bash
bugpilot hypotheses update HYPOTHESIS_ID \
  [--title TEXT] [--confidence FLOAT] [--reasoning TEXT]
```

---

## `bugpilot fix` — Remediation Actions

### `fix list`

List actions for an investigation.

```bash
bugpilot fix list INVESTIGATION_ID [--status STATUS]
```

| Option | Description |
|--------|-------------|
| `--status` | Filter: `pending` \| `approved` \| `running` \| `completed` \| `cancelled` |

---

### `fix suggest`

Create a proposed remediation action for an investigation.

```bash
bugpilot fix suggest \
  --investigation-id ID \
  TITLE \
  --type TYPE \
  [--risk LEVEL] \
  [--description TEXT] \
  [--hypothesis-id ID] \
  [--rollback-plan TEXT]
```

| Argument/Option | Short | Required | Description |
|-----------------|-------|----------|-------------|
| `TITLE` | — | Yes | Action title (positional) |
| `--investigation-id` | `-i` | Yes | Investigation ID |
| `--type` | `-t` | Yes | Action type (e.g. `rollback`, `config_change`, `restart`, `scale`) |
| `--risk` | — | No | `safe` \| `low` \| `medium` \| `high` \| `critical` (default: `low`) |
| `--description` | `-d` | No | Detailed description of what the action does |
| `--hypothesis-id` | — | No | Hypothesis this action targets |
| `--rollback-plan` | — | No | How to undo this action if needed |

**Risk levels and approval:**

| Risk | Approval required |
|------|------------------|
| `safe` / `low` | No — can run immediately |
| `medium` / `high` / `critical` | Yes — requires `approver` role |

**Example:**

```
$ bugpilot fix suggest \
    --investigation-id inv_7f3a2b \
    "Rollback deployment a3f8c2d" \
    --type rollback \
    --risk low \
    --description "Revert Stripe SDK v4 update that correlates with error onset" \
    --rollback-plan "git revert a3f8c2d && redeploy"

✓ Action created: act_d2f4e1
  Title:  Rollback deployment a3f8c2d
  Risk:   low
  Status: pending
```

---

### `fix approve`

Approve a medium/high/critical-risk action (requires `approver` role).

```bash
bugpilot fix approve ACTION_ID
```

---

### `fix run`

Execute an action.

```bash
bugpilot fix run ACTION_ID [--yes] [--dry-run]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--yes` | `-y` | Skip confirmation prompt |
| `--dry-run` | — | Simulate the action without making any changes |

**Dry-run example:**

```
$ bugpilot fix run act_d2f4e1 --dry-run

  DRY RUN: Rollback deployment a3f8c2d
  ──────────────────────────────────────
  Type:         rollback
  Risk:         low
  Rollback plan: git revert a3f8c2d && redeploy

  No changes made. Remove --dry-run to execute.
```

---

### `fix cancel`

Cancel a pending or approved action.

```bash
bugpilot fix cancel ACTION_ID
```

---

## `bugpilot export` — Export

### `export json`

Export a complete investigation bundle as structured JSON.

```bash
bugpilot export json INVESTIGATION_ID [--output FILE]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Write to file instead of stdout |

The JSON bundle includes: investigation metadata, evidence summary, all hypotheses with confidence scores, all actions and approval decisions, timeline, and outcome.

---

### `export markdown`

Export a human-readable incident report in Markdown format.

```bash
bugpilot export markdown INVESTIGATION_ID [--output FILE]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Write to file instead of stdout |

Suitable for Confluence, Notion, GitHub wikis, and incident post-mortems.

**Example output (truncated):**

```markdown
# Incident Report: High error rate on payment-service
**ID:** inv_7f3a2b  **Severity:** critical

## Timeline
| Time (UTC) | Event |
|------------|-------|
| 14:23      | Deployment a3f8c2d merged |
| 14:31      | HTTP 5xx rate exceeded 5% |
| 14:35      | Investigation opened |

## Root Cause
Bad deployment introduced regression (confidence: 72%)

## Actions Taken
1. ✓ Rollback deployment a3f8c2d
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

Set `BUGPILOT_LICENSE_KEY` as a secret and use `--output json` for machine-readable output:

```yaml
# GitHub Actions example
- name: Triage deployment incident
  env:
    BUGPILOT_LICENSE_KEY: ${{ secrets.BUGPILOT_LICENSE_KEY }}
  run: |
    bugpilot auth activate --key "$BUGPILOT_LICENSE_KEY"
    bugpilot incident triage "Deployment smoke test failed" \
      --service "$SERVICE" \
      --severity high \
      --output json > triage-result.json
    cat triage-result.json | jq '.id'
```

---

## Environment Variables Summary

| Variable | Description |
|----------|-------------|
| `BUGPILOT_API_URL` | Override the API endpoint (default: `https://api.bugpilot.io`) |
| `BUGPILOT_LICENSE_KEY` | License key used by `auth activate --key` |
| `BUGPILOT_OUTPUT` | Default output format: `human` \| `json` \| `verbose` |
| `NO_COLOR` | Set to any value to disable colour output |
