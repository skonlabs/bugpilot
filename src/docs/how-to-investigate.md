# How to Investigate an Incident with BugPilot

This guide walks through a realistic incident from alert to resolution.

---

## Scenario

At 14:31 UTC your monitoring fires: **payment-service HTTP 5xx rate > 5%**. You open a terminal.

---

## Step 1: Open an Investigation

Create an investigation to anchor all evidence and hypotheses to this incident.

```bash
bugpilot investigate create "HTTP 5xx spike on payment-service" \
  --symptom "5xx rate above 5% since 14:31 UTC, ~847 affected requests" \
  --severity critical
```

```
✓ Created  inv_7f3a2b
  Title:    HTTP 5xx spike on payment-service
  Severity: critical
  Status:   open
```

**Shortcut:** Use `bugpilot incident triage` when you want to create the investigation and immediately record the initial alert in one step:

```bash
bugpilot incident triage "HTTP 5xx spike on payment-service" \
  --symptom "5xx rate above 5% since 14:31 UTC" \
  --severity critical \
  --service payment-service
```

---

## Step 2: Add Evidence

Evidence items are normalized snapshots — log excerpts, metric summaries, config diffs, deployment events — that you attach to the investigation. The more evidence from different sources, the higher the confidence in hypotheses.

The `--source` option takes a **URI** that identifies the origin of the evidence. The scheme names the system (e.g. `datadog://`, `github://`) and query parameters narrow the scope.

```bash
# Log snapshot from Datadog
bugpilot evidence collect \
  --investigation-id inv_7f3a2b \
  --label "payment-service error logs" \
  --kind log_snapshot \
  --source "datadog://logs?service=payment-service&env=prod" \
  --summary "47 NullPointerException at UserService.java:142 starting 14:31 UTC. user.preferences was null."

# Deployment event from GitHub
bugpilot evidence collect \
  --investigation-id inv_7f3a2b \
  --label "deployment at 14:23 UTC" \
  --kind config_diff \
  --source "github://deployments?repo=acme/payment-service&ref=a3f8c2d" \
  --summary "Commit a3f8c2d by alice: 'Update Stripe SDK v4'. Merged and deployed at 14:23 UTC — 8 minutes before errors began."

# Memory metric snapshot
bugpilot evidence collect \
  --investigation-id inv_7f3a2b \
  --label "heap memory spike" \
  --kind metric_snapshot \
  --source "datadog://metrics?metric=system.mem.pct_usable&service=payment-service" \
  --summary "Heap memory rose from 60% to 92% on payment-service pod-3 between 14:23 and 14:31 UTC."
```

List what you've added:

```bash
bugpilot evidence list --investigation-id inv_7f3a2b
```

```
  ID          LABEL                         KIND             SOURCE    ADDED
  ev_9c1d3e   payment-service error logs    log_snapshot     datadog   1m ago
  ev_a2b4f1   deployment at 14:23 UTC       config_diff      github    45s ago
  ev_f7d2c3   heap memory spike             metric_snapshot  datadog   20s ago
```

**Evidence kinds:** `log_snapshot` · `metric_snapshot` · `trace` · `event` · `config_diff` · `topology` · `custom`

---

## Step 3: Review Hypotheses

BugPilot generates hypotheses automatically as evidence is added. The hypothesis engine runs a multi-pass pipeline: rule-based pattern matching → graph correlation → historical reranking → LLM synthesis (when an LLM provider is configured).

```bash
bugpilot hypotheses list --investigation-id inv_7f3a2b
```

```
  RANK  HYPOTHESIS                              CONFIDENCE  STATUS   SOURCE
   1    Bad deployment introduced regression    72%         active   rule
   2    Memory exhaustion (OOMKill risk)        58%         active   rule
   3    Upstream dependency degradation         31%         active   graph
```

To add a hypothesis manually — for a theory from the team:

```bash
bugpilot hypotheses create \
  --investigation-id inv_7f3a2b \
  "Stripe SDK v4 changed preferences API contract" \
  --confidence 0.65 \
  --reasoning "SDK upgrade changed how user.preferences is hydrated, causing NPE on first call" \
  --evidence ev_9c1d3e \
  --evidence ev_a2b4f1
```

---

## Step 4: Propose a Fix

Create a remediation action. Risk level determines whether approval is required before the action can be run.

```bash
bugpilot fix suggest \
  --investigation-id inv_7f3a2b \
  "Rollback deployment a3f8c2d" \
  --type rollback \
  --risk low \
  --description "Revert Stripe SDK v4 update — correlates with onset of 5xx errors" \
  --hypothesis-id hyp_f3a1d2 \
  --rollback-plan "git revert a3f8c2d && trigger CI redeploy pipeline"
```

```
✓ Action created: act_d2f4e1
  Title:  Rollback deployment a3f8c2d
  Risk:   low
  Status: pending  (no approval required for low-risk actions)
```

**Risk levels and approval:**

| Risk | Approval required |
|------|------------------|
| `safe` / `low` | No |
| `medium` / `high` / `critical` | Yes — `approver` role required |

---

## Step 5: Execute the Fix

Run the action. BugPilot will show the action details and ask for confirmation before executing:

```bash
bugpilot fix run act_d2f4e1
```

```
  Action:     Rollback deployment a3f8c2d
  Risk level: LOW
Execute this action? [y/N]: y

✓ Action executed: act_d2f4e1
```

Use `--yes` / `-y` to skip the confirmation prompt in scripts.

Watch your monitoring. If the 5xx rate drops, the fix worked.

---

## Step 6: Confirm Root Cause and Close

Confirm the hypothesis that turned out to be correct:

```bash
bugpilot hypotheses confirm hyp_f3a1d2
```

Reject the ones that didn't apply:

```bash
bugpilot hypotheses reject hyp_8b3c1a
```

Close the investigation:

```bash
bugpilot investigate close inv_7f3a2b
# or the top-level alias:
bugpilot resolve inv_7f3a2b
```

---

## Step 7: Export a Post-Mortem

```bash
# Markdown report for Confluence / Notion / GitHub wiki
bugpilot export markdown inv_7f3a2b --output postmortem-2026-03-10.md

# Full JSON bundle for archiving or integrations
bugpilot export json inv_7f3a2b --output inv_7f3a2b.json
```

---

## Tips

**Add evidence from multiple sources.** Confidence is capped at 40% with a single source. A second source from a different platform significantly improves hypothesis quality.

**Use `--output json` in scripts.** Every command supports `-o json` for pipeline-friendly output:

```bash
bugpilot hypotheses list --investigation-id inv_7f3a2b -o json \
  | jq '.[] | select(.confidence_score > 0.6)'
```

**Reject bad hypotheses early.** This helps BugPilot improve scoring accuracy for your org over time.
