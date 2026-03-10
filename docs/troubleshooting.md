# Troubleshooting Guide

Common issues and how to resolve them.

---

## CLI Issues

### `bugpilot: command not found`

The CLI is not installed or not on `PATH`.

```bash
pip install -e ./cli
# or
pip install bugpilot
```

Check your Python bin directory is on PATH:

```bash
python3 -c "import sys; print(sys.prefix + '/bin')"
export PATH="$PATH:$(python3 -c 'import sys; print(sys.prefix + "/bin")')"
```

---

### `Error: Could not connect to BugPilot API at http://localhost:8000`

The backend is not running or the URL is wrong.

```bash
# Check the backend
curl http://localhost:8000/health
# Should return: {"status":"ok"}

# Check what URL the CLI is using
bugpilot auth whoami
# Look for: connecting to: http://...

# Override the URL
export BUGPILOT_API_URL=https://your-bugpilot.example.com
```

---

### `Error: 401 Unauthorized — session expired`

Your JWT has expired. The CLI automatically refreshes tokens, but if the refresh token has also expired (sessions last 30 days), you need to re-activate.

```bash
bugpilot auth activate --license-key bp_YOUR_KEY
```

---

### `Error: 403 Forbidden — insufficient role`

You don't have the required role for this action.

| Command | Required role |
|---------|--------------|
| `bugpilot fix approve` | `approver` |
| `bugpilot auth whoami` → admin routes | `admin` |

Contact your org admin to update your role.

---

## Backend / API Issues

### `sqlalchemy.exc.OperationalError: could not connect to server`

PostgreSQL is not reachable.

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check the connection string
psql "$DATABASE_URL"

# For Docker Compose
docker compose ps postgres
docker compose logs postgres
```

---

### `alembic.util.exc.CommandError: Can't locate revision`

The database has not been migrated.

```bash
cd backend
alembic upgrade head
```

---

### `cryptography.fernet.InvalidToken`

The `FERNET_KEY` in the environment doesn't match the key used to encrypt stored credentials. This happens if you rotated the key without re-encrypting stored data.

```bash
# Check the key format
python3 -c "
from cryptography.fernet import Fernet
import base64, os
key = os.environ['FERNET_KEY'].encode()
# Should not raise:
Fernet(key)
print('Key is valid')
"
```

If you have changed the key, you need to re-enter credentials for all configured connectors via the admin API.

---

### `ValueError: SECURITY: Attempted to send non-redacted GraphSlice to LLM provider`

This is a safety check — BugPilot is preventing raw (potentially sensitive) evidence from being sent to an LLM. This should not appear in normal use. If you see it:

1. Check that evidence collection is calling the redaction pipeline before passing data to the hypothesis engine
2. In tests, ensure `GraphSlice.is_redacted=True` when testing LLM-related code paths

---

### Pydantic validation error on startup

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
```

A required environment variable is missing. BugPilot will tell you which one. Common missing variables:

- `DATABASE_URL` — PostgreSQL connection string
- `JWT_SECRET` — must be at least 32 characters
- `FERNET_KEY` — must be a valid Fernet key (base64-encoded 32 bytes)

---

## Connector Issues

### `Connector degraded: timeout after 45s`

A connector didn't respond within the 45-second collection window.

**Check:**
1. Is the target system reachable from the BugPilot host?
   ```bash
   curl -I https://api.datadoghq.com/api/v1/validate -H "DD-API-KEY: $KEY"
   ```
2. Are credentials valid?
   ```bash
   curl http://localhost:8000/api/v1/admin/connectors/validate \
     -H "Authorization: Bearer $TOKEN"
   ```
3. Is the network allowing outbound HTTPS from the container?

---

### `401 Unauthorized` from Datadog/Grafana connector

Credentials have expired or permissions are insufficient.

- **Datadog:** Verify `DD-API-KEY` and `DD-APPLICATION-KEY` in the Datadog portal. Check that the App key has `logs_read_data` and `metrics_read` scopes.
- **Grafana:** Check the service account token hasn't expired (Grafana → Administration → Service accounts).

---

### `CloudWatch: SignatureDoesNotMatch`

The AWS credentials are invalid or the request is being made too long after the timestamp in the signature.

```bash
# Verify your credentials
aws sts get-caller-identity \
  --access-key-id "$AWS_ACCESS_KEY_ID" \
  --secret-access-key "$AWS_SECRET_ACCESS_KEY" \
  --region us-east-1
```

Ensure the BugPilot host's system clock is accurate (within 5 minutes of AWS time). Use NTP.

---

## Webhook Issues

### `401 Unauthorized` on webhook endpoint

The HMAC signature doesn't match. Common causes:

1. **Wrong secret** — The secret registered in BugPilot doesn't match the one configured in your monitoring platform.
2. **Encoding mismatch** — The payload is being modified in transit (e.g. by a proxy that normalises JSON whitespace). BugPilot computes the HMAC over the exact raw bytes received.
3. **Stale secret** — You rotated the secret in the monitoring platform but forgot to update BugPilot (or vice versa).

Use the dual-secret rotation feature to rotate without downtime.

---

### Webhook received but no investigation created

Check the webhook delivery logs:

```bash
curl http://localhost:8000/api/v1/admin/webhooks/deliveries \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Also check the structured logs:

```bash
docker compose logs backend | grep webhook | jq '.'
```

---

## Evidence / Hypothesis Issues

### `⚠ Evidence from single source only — confidence capped at 40%`

This is a warning, not an error. BugPilot has evidence from only one connector capability type. The hypothesis engine is working correctly but with less data.

**Fix:** Configure additional connectors (e.g. if you only have Datadog logs, add Datadog metrics, or configure GitHub for deployment data).

---

### No hypotheses generated

The hypothesis engine has minimum requirements before generating:
- At least 1 symptom node in the graph
- At least 1 service/component node
- At least 2 evidence items

Check evidence was collected:

```bash
bugpilot evidence list INVESTIGATION_ID
```

If evidence is empty, re-collect:

```bash
bugpilot evidence collect INVESTIGATION_ID --since 2h
```

---

## Performance Issues

### Slow evidence collection

Evidence collection runs concurrently across all connectors. A slow connector drags out the total time. Check which connector is slow:

```bash
bugpilot evidence collect INVESTIGATION_ID --since 1h
# Look at per-connector latency in the output table
```

If one connector is consistently slow, consider increasing its timeout or investigating the root cause on the source system.

---

### High database memory usage

BugPilot stores JSONB payloads in PostgreSQL. Run the retention purge to clean up old data:

```bash
docker compose exec backend python3 -c "
import asyncio
from app.services.retention_service import RetentionService
..."
```

---

## Getting Help

- **GitHub Issues:** https://github.com/skonlabs/bugpilot/issues
- **API Docs (local):** http://localhost:8000/docs
- **Health check:** `curl http://localhost:8000/health/ready`
- **Verbose logging:** Set `LOG_LEVEL=debug` in your environment
