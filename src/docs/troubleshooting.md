# Troubleshooting Guide

Common issues and how to resolve them.

---

## CLI Issues

### `bugpilot: command not found`

The CLI binary is not on your `PATH`.

**macOS (Homebrew):** Homebrew adds the binary automatically. Try opening a new terminal window, or run:
```bash
brew link bugpilot
```

**macOS (.pkg installer):** The installer places the binary at `/usr/local/bin/bugpilot`. If it's not found, check that `/usr/local/bin` is in your PATH:
```bash
echo $PATH | tr ':' '\n' | grep /usr/local/bin
```

**Windows (Scoop):** Scoop adds its shims directory to PATH automatically. Try opening a new PowerShell or Command Prompt window.

**Windows (.msi installer):** Open a new terminal window after installation. If still not found, add the install directory to your PATH manually in **System Properties → Environment Variables**.

---

### `Error: Could not connect to BugPilot API`

The CLI cannot reach `https://api.bugpilot.io`.

- Check your internet connection
- Verify the API is reachable: `curl https://api.bugpilot.io/health`
- If you're using a custom API URL (self-hosted), check `BUGPILOT_API_URL` is set correctly
- Check if a corporate firewall or proxy is blocking outbound HTTPS

---

### `401 Unauthorized`

Your session has expired or credentials are invalid.

Re-activate the CLI:
```bash
bugpilot auth activate --key bp_YOUR_LICENSE_KEY
```

Or check who you're currently logged in as:
```bash
bugpilot auth whoami
```

If credentials are corrupted, clear them and re-activate:
```bash
rm ~/.config/bugpilot/credentials.json
bugpilot auth activate --key bp_YOUR_LICENSE_KEY
```

---

### `403 Forbidden — insufficient role`

Your account role does not have permission for this action.

```
✗ Error: 403 Forbidden — insufficient role for this action
  Your role: investigator
  Required:  approver
```

Ask your admin to assign you the required role. See [Manage Users and Roles](./how-to-rbac.md).

---

### `--dry-run` shows nothing happening

`--dry-run` simulates the action without making changes. No output means the action would have no observable side effects. Add `--yes` to actually run it.

---

## Evidence Issues

### Hypotheses have low confidence or are capped at 40%

```
⚠ Evidence from a single source only. Confidence scores capped at 40%.
  Add evidence from a second source to improve hypothesis quality.
```

Add evidence from at least one additional source. Even a brief metric snapshot or deployment event significantly improves hypothesis accuracy.

---

### No hypotheses generated

Hypotheses require:
1. At least one evidence item attached to the investigation
2. At least one service name recorded (via `--service` on triage or in evidence)
3. Evidence with sufficient content in the summary field

If you have evidence but still see no hypotheses, try updating the investigation to set a service:
```bash
bugpilot investigate update inv_7f3a2b --description "Affects: payment-service"
```

---

## Webhook Issues

### `401` on webhook delivery

The webhook signature does not match.

- Verify the webhook secret registered in BugPilot matches the secret configured in your monitoring platform exactly (no extra spaces or encoding differences)
- If you recently rotated the secret, allow up to 1 hour for the grace window to expire
- Check the `bugpilot_webhook_verification_failures_total` metric for patterns

---

### Webhook received but no investigation created

- Check the BugPilot API structured logs for the webhook receipt event
- Verify the payload format matches the expected schema for your source (Datadog, Grafana, CloudWatch, or PagerDuty)
- If the dedup check matched an existing open investigation, the webhook will have updated it rather than creating a new one — check `bugpilot investigate list --status open`

---

## Action Approval Issues

### `fix run` fails with "approval required"

Actions with risk level `medium`, `high`, or `critical` require approval from an `approver` or `admin` before they can be run.

```bash
# Ask an approver to run:
bugpilot fix approve act_d2f4e1

# Then run:
bugpilot fix run act_d2f4e1 --yes
```

---

## Export Issues

### `export markdown` produces empty sections

Sections like **Root Cause** are empty if no hypothesis has been confirmed. Confirm the root cause hypothesis first:

```bash
bugpilot hypotheses confirm hyp_f3a1d2
bugpilot export markdown inv_7f3a2b
```

---

## Getting More Help

- **Verbose output:** Add `-o verbose` to any command to see full request/response details
- **GitHub Issues:** https://github.com/skonlabs/bugpilot/issues
- **Docs:** [bugpilot.io/docs](https://bugpilot.io/docs)
