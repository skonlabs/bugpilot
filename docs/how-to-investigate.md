# How to Investigate an Incident with BugPilot

This guide walks through a realistic incident scenario from alert to resolution using BugPilot.

---

## Scenario

At 14:31 UTC your monitoring fires: **payment-service HTTP 5xx rate > 5%**. The on-call engineer opens a terminal.

---

## Step 1 — Authenticate

If this is your first time on this machine:

```bash
bugpilot auth activate --license-key bp_YOUR_LICENSE_KEY
```

Check who you're logged in as:

```bash
bugpilot auth whoami
```

```
  User:  alice@acme.com
  Role:  investigator
  Org:   acme-corp
```

---

## Step 2 — Triage (recommended: let BugPilot handle it)

The `incident triage` command does the most in one step: deduplication check, investigation creation, evidence collection, and initial hypothesis generation.

```bash
bugpilot incident triage \
  --service payment-service \
  --alert-name "HTTP 5xx rate > 5%" \
  --severity critical \
  --since 2h
```

```
  ⚡ Dedup check: No similar open investigations found
  ✓ Investigation created: inv_7f3a2b
  ↓ Collecting evidence (5 connectors)...
    ✓ datadog/logs         47 items   0.34s
    ✓ datadog/metrics      12 items   0.41s
    ✓ datadog/alerts        3 items   0.28s
    ✗ grafana/metrics       —         degraded: timeout after 45s
    ✓ github/deployments    2 items   0.19s
  ✓ Hypotheses generated (3)

  TOP HYPOTHESIS
  ──────────────────────────────────────────────────────────────
  Rank 1  │  Bad Deployment Introduced Regression          ▓▓▓▓▓▓▓▒ 72%
          │  Deployment a3f8c2d at 14:23 UTC correlates with the
          │  onset of 5xx errors. Commit message: "Update Stripe
          │  SDK to v4". Affected evidence: 12 items.
  ──────────────────────────────────────────────────────────────

  Investigation ID: inv_7f3a2b
  Run: bugpilot hypotheses list inv_7f3a2b   for all hypotheses
  Run: bugpilot fix suggest inv_7f3a2b       for remediation options
```

> **Tip:** BugPilot detected that Grafana timed out but continued with the other 4 connectors. It notes the degraded source and still produced useful hypotheses from logs + metrics + deployment data.

---

## Step 3 — Review All Hypotheses

```bash
bugpilot hypotheses list inv_7f3a2b
```

```
  RANK  HYPOTHESIS                              CONFIDENCE  STATUS  SOURCE
  ────  ──────────────────────────────────────  ──────────  ──────  ──────
  1     Bad Deployment Introduced Regression    72%         active  rule
  2     Memory Exhaustion                       58%         active  rule
  3     Upstream Dependency Degradation         41%         active  graph

  3 hypotheses  │  Evidence from 3 capabilities (LOGS, METRICS, DEPLOYMENTS)
```

Each hypothesis shows:
- **Confidence score** — derived from evidence strength and correlation
- **Source** — `rule` (pattern matching), `graph` (graph analysis), or `llm` (AI synthesis)

---

## Step 4 — Investigate a Hypothesis

Check the evidence linked to the top hypothesis:

```bash
bugpilot evidence list inv_7f3a2b --capability deployments
```

```
  ID           SOURCE         CAPABILITY    SUMMARY                          RELIABILITY
  ev_d1e2f3   github         DEPLOYMENTS   Merge commit a3f8c2d: "Update     0.98
                                           Stripe SDK to v4" by alice, 14:23
  ev_a4b5c6   datadog        DEPLOYMENTS   Deployment: payment-service →      0.95
                                           v2.14.0, duration: 3m12s, 14:23
```

Timeline view to see the sequence of events:

```bash
bugpilot investigate get inv_7f3a2b
```

```
  TIMELINE
  ─────────────────────────────────────────────────────────────
  14:23:00  DEPLOYMENT    Deploy a3f8c2d — payment-service v2.14.0
  14:31:12  SYMPTOM       HTTP 5xx rate spike — 7.2% error rate
  14:31:45  ALERT         PagerDuty: P1 incident created
  14:33:00  SYMPTOM       Latency p99 increased to 8.2s
  ─────────────────────────────────────────────────────────────
```

The 8-minute gap between deployment and error onset strongly suggests the deployment is the cause.

---

## Step 5 — Reject Unlikely Hypotheses

After reviewing the evidence, hypothesis #2 (Memory Exhaustion) looks unlikely — memory metrics are stable.

```bash
bugpilot hypotheses reject hyp_mem456 \
  --reason "Memory metrics stable at 62% usage throughout the incident window"
```

---

## Step 6 — Get Remediation Options

```bash
bugpilot fix suggest inv_7f3a2b
```

```
  SUGGESTED ACTIONS

  #1  Rollback deployment a3f8c2d                                  RISK: low
      Rationale:   Deployment correlates with 5xx onset at 14:31
      Effect:      Restore payment-service to v2.13.0 (stable 3 days)
      Rollback:    git revert a3f8c2d && trigger CI/CD pipeline
      Approval:    Not required

  #2  Disable Stripe SDK v4 feature flag                          RISK: low
      Rationale:   New SDK may have breaking API changes
      Effect:      Bypass v4 code path without a full rollback
      Rollback:    Re-enable feature flag
      Approval:    Not required

  #3  Increase memory limit to 1Gi                                RISK: medium
      Rationale:   Memory headroom of 38% — guard against spikes
      Effect:      Prevent potential OOMKill under load
      Rollback:    Revert resource quota change
      Approval:    Required (approver role)
```

---

## Step 7 — Dry Run a Safe Action

Always dry-run before executing:

```bash
bugpilot fix run act_rollback123 --dry-run
```

```
  DRY RUN: Rollback deployment a3f8c2d
  ─────────────────────────────────────────────────────────────
  Would execute:
    1. Trigger rollback pipeline for payment-service
    2. Set image: payment-service → v2.13.0
    3. Wait for rollout (estimated: 2-3 minutes)

  Estimated downtime:    0s  (rolling update strategy)
  Previous version age:  3 days (stable, no incidents)
  Risk assessment:       LOW

  To execute: bugpilot fix run act_rollback123
```

---

## Step 8 — Execute the Action

```bash
bugpilot fix run act_rollback123
```

```
  ✓ Action executed: Rollback deployment a3f8c2d
    Status:   completed
    Output:   Rolling update complete. 3/3 pods ready.
    Duration: 2m41s
```

---

## Step 9 — Confirm the Root Cause and Close

Once the 5xx rate drops back to baseline, confirm the hypothesis and close the investigation.

```bash
# Confirm the root cause
bugpilot hypotheses confirm hyp_deploy789

# Close the investigation with root cause summary
bugpilot investigate close inv_7f3a2b \
  --root-cause "Stripe SDK v4 introduced a breaking change in the charge() API. Rolled back to v2.13.0. SDK upgrade to be re-attempted with proper integration tests."
```

```
  ✓ Investigation closed
    Duration:     47 minutes
    Root cause:   Stripe SDK v4 introduced a breaking change...
    Actions:      1 executed (rollback a3f8c2d)
    Evidence:     65 items from 4 sources
```

---

## Step 10 — Export the Incident Report

```bash
bugpilot export markdown inv_7f3a2b --output-file incident-report.md
```

The generated Markdown report includes: timeline, root cause, evidence summary, actions taken (with approvals), and outcome. Ready to paste into Confluence, Notion, or a GitHub issue.

---

## Tips and Patterns

### Parallel hypothesis testing

Use branches to test multiple hypotheses in parallel without polluting the main investigation:

```bash
# Create a branch to test the memory hypothesis separately
bugpilot investigate update inv_7f3a2b --create-branch memory-investigation
```

### Multi-service incidents

When multiple services are affected, add them to the investigation:

```bash
bugpilot investigate update inv_7f3a2b \
  --service checkout-service \
  --service stripe-gateway
```

BugPilot will collect evidence for all linked services and look for cross-service causal chains.

### Automating triage from CI/CD

```bash
# Trigger triage automatically after a failed deployment
if [ "$DEPLOY_STATUS" = "failed" ]; then
  bugpilot incident triage \
    --service "$SERVICE_NAME" \
    --alert-name "Deployment smoke test failed: $BUILD_ID" \
    --severity high \
    --since 15m \
    --output json > /tmp/triage.json

  # Print top hypothesis to CI logs
  cat /tmp/triage.json | python3 -c "
  import json,sys
  r = json.load(sys.stdin)
  h = r.get('top_hypothesis')
  if h:
      print(f'Top hypothesis: {h[\"title\"]} ({h[\"confidence_score\"]*100:.0f}% confidence)')
  "
fi
```

### When evidence is thin (single-lane warning)

If you see `⚠ Evidence from single source only` — this means only one connector provided data. Confidence scores are capped at 40%.

To improve hypothesis quality:
1. Check that other connectors are properly configured: `bugpilot auth whoami`
2. Validate connector health: `curl /api/v1/admin/connectors/validate`
3. Re-collect with explicit capabilities: `bugpilot evidence collect inv_7f3a2b --since 2h`
