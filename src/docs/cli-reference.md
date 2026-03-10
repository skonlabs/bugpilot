# CLI Reference

Complete reference for every `bugpilot` command. All commands support three output formats.

---

## Global Options

```
bugpilot [OPTIONS] COMMAND [ARGS]...
```

| Option | Short | Env var | Default | Description |
|--------|-------|---------|---------|-------------|
| `--api-url TEXT` | — | `BUGPILOT_API_URL` | `https://api.bugpilot.io` | BugPilot service URL |
| `--output TEXT` | `-o` | `BUGPILOT_OUTPUT` | `human` | Output format: `human` \| `json` \| `verbose` |
| `--no-color` | — | `NO_COLOR` | false | Disable colour |
| `--version` | `-v` | — | — | Print version and exit |

**Output formats:**

- **`human`** — colour-coded tables. Best for interactive use.
- **`json`** — machine-readable JSON on stdout. Use in scripts and CI.
- **`verbose`** — all fields with syntax highlighting. Use for debugging.

---

## `bugpilot auth`

### `auth activate`

Link the CLI to your BugPilot account. Displays Terms of Service on first run. Run once per machine.

```
bugpilot auth activate [--key KEY] [--secret SECRET] [--email EMAIL] [--name NAME]
```

| Option | Short | Env var | Description |
|--------|-------|---------|-------------|
| `--key` | `-k` | `BUGPILOT_LICENSE_KEY` | License key. Prompted if omitted. |
| `--secret` | `-s` | `BUGPILOT_API_SECRET` | API secret. Prompted if omitted. |
| `--email` | `-e` | — | Your email address. Prompted if omitted. |
| `--name` | — | — | Optional display name. |

```
$ bugpilot auth activate --key YOUR_LICENSE_KEY --secret YOUR_API_SECRET

[Terms of Service displayed — accept/decline]

Enter your email address: alice@acme.com

✓ BugPilot activated!
```

Session is stored at `~/.config/bugpilot/credentials.json` (permissions `600`).

---

### `auth logout`

End the session and clear stored credentials.

```
bugpilot auth logout
```

---

### `auth whoami`

Show the currently authenticated user.

```
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

## `bugpilot connector`

Manage data source connectors. Credentials are stored in `~/.config/bugpilot/config.yaml`.

### `connector list`

Show all configured connectors (secrets masked).

```
bugpilot connector list
```

---

### `connector add`

Add or update a connector interactively.

```
bugpilot connector add TYPE [--overwrite]
```

| Argument/Option | Description |
|-----------------|-------------|
| `TYPE` | Connector type: `datadog` \| `grafana` \| `cloudwatch` \| `github` \| `kubernetes` \| `pagerduty` |
| `--overwrite` | Overwrite existing connector without prompting |

```
$ bugpilot connector add datadog

Configure datadog connector

  API Key: ••••••••••••••••••••
  Application Key: ••••••••••••••••••••
  Site (e.g. datadoghq.com) [datadoghq.com]:

✓ Connector 'datadog' saved to ~/.config/bugpilot/config.yaml
```

---

### `connector remove`

Remove a connector from config.

```
bugpilot connector remove TYPE [--yes]
```

`--yes` / `-y` — skip confirmation.

---

### `connector test`

Test connector connectivity. Omit `TYPE` to test all.

```
bugpilot connector test [TYPE]
```

```
$ bugpilot connector test

  Testing datadog...  ✓ OK
  Testing grafana...  ✓ OK
```

---

## `bugpilot config`

Manage `~/.config/bugpilot/config.yaml`.

### `config init`

Create a starter config file with all connector and webhook templates.

```
bugpilot config init [--overwrite]
```

`--overwrite` — replace an existing config file.

---

### `config show`

Display the current config (secrets masked).

```
bugpilot config show
```

---

### `config validate`

Check the config for missing required fields.

```
bugpilot config validate
```

Exits with code `1` if there are validation errors.

---

## `bugpilot investigate`

### `investigate list`

List investigations for your organisation.

```
bugpilot investigate list [--status STATUS] [--severity SEVERITY] [--page N] [--page-size N]
```

| Option | Description |
|--------|-------------|
| `--status, -s` | Filter: `open` \| `in_progress` \| `resolved` \| `closed` |
| `--severity` | Filter: `critical` \| `high` \| `medium` \| `low` |
| `--page, -p` | Page number (default: 1) |
| `--page-size` | Results per page (default: 20) |

```
$ bugpilot investigate list --status open

  ID          TITLE                                SEVERITY  STATUS   CREATED
  inv_7f3a2b  High error rate on payment-service   high      open     2h ago
  inv_c1d9e0  Database connection pool exhausted   critical  open     45m ago
```

---

### `investigate create`

Open a new investigation.

```
bugpilot investigate create TITLE [--symptom TEXT] [--severity LEVEL] [--description TEXT]
```

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `TITLE` | Yes | — | Short description (positional argument) |
| `--symptom` | No | — | Observable symptom text |
| `--severity` | No | `medium` | `critical` \| `high` \| `medium` \| `low` |
| `--description, -d` | No | — | Additional context or notes |

---

### `investigate get`

Fetch full details of one investigation.

```
bugpilot investigate get INVESTIGATION_ID
```

---

### `investigate update`

Update investigation fields.

```
bugpilot investigate update INVESTIGATION_ID
  [--title TEXT] [--status STATUS] [--severity LEVEL] [--description TEXT]
```

---

### `investigate close`

Mark an investigation as closed.

```
bugpilot investigate close INVESTIGATION_ID
```

---

### `investigate delete`

Permanently delete an investigation and all its evidence. Requires confirmation.

```
bugpilot investigate delete INVESTIGATION_ID [--yes]
```

`--yes` / `-y` — skip the confirmation prompt.

---

## `bugpilot incident`

### `incident triage`

Quickly create an investigation from an active alert. Creates the investigation and records a timeline event in one step.

```
bugpilot incident triage TITLE [--symptom TEXT] [--severity LEVEL] [--service TEXT]
```

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `TITLE` | Yes | — | Incident title or alert name (positional) |
| `--symptom, -s` | No | — | Observed symptom or alert description |
| `--severity` | No | `high` | `critical` \| `high` \| `medium` \| `low` |
| `--service` | No | — | Affected service name |

---

### `incident status`

Show a full summary of an active investigation — evidence count, hypotheses, and actions.

```
bugpilot incident status INVESTIGATION_ID
```

---

## `bugpilot evidence`

Evidence is what BugPilot analyses. You add evidence items to an investigation — log excerpts, metric summaries, deployment events, config changes — and BugPilot uses them to generate hypotheses.

### `evidence list`

```
bugpilot evidence list --investigation-id ID [--kind KIND]
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--investigation-id` | `-i` | Yes | Investigation ID |
| `--kind` | — | No | Filter by kind |

**Evidence kinds:** `log_snapshot` · `metric_snapshot` · `trace` · `event` · `config_diff` · `topology` · `custom`

---

### `evidence collect`

Add a piece of evidence to an investigation.

```
bugpilot evidence collect
  --investigation-id ID
  --label LABEL
  [--kind KIND]
  [--source SOURCE]
  [--summary TEXT]
  [--connector-id CONNECTOR_ID]
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--investigation-id` | `-i` | Yes | Investigation to attach this evidence to |
| `--label` | `-l` | Yes | Short descriptive label |
| `--kind` | `-k` | No | Evidence kind (default: `custom`) |
| `--source` | — | No | Source system name, e.g. `datadog`, `github` |
| `--summary` | `-s` | No | Text summary of what this evidence shows |
| `--connector-id` | — | No | ID of the connector that produced this |

---

### `evidence get`

```
bugpilot evidence get EVIDENCE_ID
```

---

### `evidence delete`

```
bugpilot evidence delete EVIDENCE_ID [--yes]
```

---

## `bugpilot hypotheses`

### `hypotheses list`

List hypotheses ranked by confidence.

```
bugpilot hypotheses list --investigation-id ID [--status STATUS]
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--investigation-id` | `-i` | Yes | Investigation ID |
| `--status` | `-s` | No | `active` \| `confirmed` \| `rejected` |

```
$ bugpilot hypotheses list --investigation-id inv_7f3a2b

  RANK  HYPOTHESIS                             CONFIDENCE  STATUS
   1    Bad deployment introduced regression   72%         active
   2    Memory exhaustion                      41%         active
   3    Upstream dependency degradation        28%         active
```

---

### `hypotheses create`

Add a hypothesis manually.

```
bugpilot hypotheses create
  --investigation-id ID
  TITLE
  [--description TEXT]
  [--confidence FLOAT]
  [--reasoning TEXT]
  [--evidence EVIDENCE_ID]...
```

| Argument/Option | Short | Required | Description |
|-----------------|-------|----------|-------------|
| `TITLE` | — | Yes | Hypothesis title (positional) |
| `--investigation-id` | `-i` | Yes | Investigation ID |
| `--description` | `-d` | No | Detailed description |
| `--confidence` | `-c` | No | Confidence score 0.0–1.0 |
| `--reasoning` | — | No | Explanation of why this is a candidate |
| `--evidence` | — | No | Supporting evidence ID (repeatable) |

---

### `hypotheses confirm`

Mark a hypothesis as the confirmed root cause.

```
bugpilot hypotheses confirm HYPOTHESIS_ID
```

---

### `hypotheses reject`

Mark a hypothesis as ruled out.

```
bugpilot hypotheses reject HYPOTHESIS_ID
```

---

### `hypotheses update`

Update a hypothesis.

```
bugpilot hypotheses update HYPOTHESIS_ID
  [--title TEXT] [--confidence FLOAT] [--reasoning TEXT]
```

---

## `bugpilot fix`

### `fix list`

List actions for an investigation.

```
bugpilot fix list --investigation-id ID [--status STATUS]
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--investigation-id` | `-i` | Yes | Investigation ID |
| `--status` | — | No | `pending` \| `approved` \| `running` \| `completed` \| `cancelled` |

---

### `fix suggest`

Propose a remediation action.

```
bugpilot fix suggest
  --investigation-id ID
  TITLE
  --type TYPE
  [--risk LEVEL]
  [--description TEXT]
  [--hypothesis-id ID]
  [--rollback-plan TEXT]
```

| Argument/Option | Short | Required | Default | Description |
|-----------------|-------|----------|---------|-------------|
| `TITLE` | — | Yes | — | Action title (positional) |
| `--investigation-id` | `-i` | Yes | — | Investigation ID |
| `--type` | `-t` | Yes | — | Action type, e.g. `rollback`, `config_change`, `restart`, `scale` |
| `--risk` | — | No | `medium` | `safe` \| `low` \| `medium` \| `high` \| `critical` |
| `--description` | `-d` | No | — | What the action does |
| `--hypothesis-id` | — | No | — | Hypothesis this action targets |
| `--rollback-plan` | — | No | — | How to undo this action |

**Approval rules:**

| Risk level | Approval required before running? |
|------------|----------------------------------|
| `safe` or `low` | No |
| `medium`, `high`, or `critical` | Yes — `approver` role required |

---

### `fix approve`

Approve a medium/high/critical-risk action. Requires `approver` or `admin` role.

```
bugpilot fix approve ACTION_ID
```

---

### `fix run`

Execute an action. Displays the action title and risk level, then prompts for confirmation before proceeding.

```
bugpilot fix run ACTION_ID [--yes]
```

`--yes` / `-y` — skip the confirmation prompt.

```
$ bugpilot fix run act_d2f4e1

  Action:     Rollback deployment a3f8c2d
  Risk level: LOW
Execute this action? [y/N]: y

✓ Action executed: act_d2f4e1
```

---

### `fix cancel`

Cancel a pending or approved action.

```
bugpilot fix cancel ACTION_ID
```

---

## `bugpilot export`

### `export json`

Export the full investigation bundle as JSON (investigation, evidence, hypotheses, actions, timeline).

```
bugpilot export json INVESTIGATION_ID [--output FILE]
```

`--output` / `-o` — write to a file instead of stdout.

---

### `export markdown`

Export a Markdown incident report suitable for Confluence, Notion, or GitHub wikis.

```
bugpilot export markdown INVESTIGATION_ID [--output FILE]
```

`--output` / `-o` — write to a file instead of stdout.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BUGPILOT_API_URL` | Override the API endpoint (default: `https://api.bugpilot.io`) |
| `BUGPILOT_LICENSE_KEY` | License key, read by `auth activate --key` |
| `BUGPILOT_API_SECRET` | API secret, read by `auth activate --secret` |
| `BUGPILOT_OUTPUT` | Default output format: `human` \| `json` \| `verbose` |
| `NO_COLOR` | Set to any non-empty value to disable colour |

---

## Using in CI / Scripts

```bash
# Activate non-interactively
bugpilot auth activate \
  --key "$BUGPILOT_LICENSE_KEY" \
  --secret "$BUGPILOT_API_SECRET" \
  --email "$BUGPILOT_EMAIL"

# Machine-readable output
bugpilot investigate list --status open -o json \
  | jq '.items[] | {id, title, severity}'

# Create and capture investigation ID
INV_ID=$(bugpilot incident triage "Deploy check failed" \
  --service payment-service --severity high -o json \
  | jq -r '.id')
```
