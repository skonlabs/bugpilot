# How to Configure Data Retention

BugPilot implements a three-phase data retention policy that is configurable per organisation. This guide explains the phases, defaults, and how to tune them.

---

## Retention Phases

BugPilot retains data in three progressively smaller windows:

| Phase | Default | What happens |
|-------|---------|-------------|
| **Investigation archive** | 365 days | Resolved/closed investigations are archived after this period |
| **Evidence metadata** | 90 days | Evidence rows (normalized_summary, reliability_score, etc.) are deleted |
| **Raw payload expiry** | 30 days | `payload_ref` column is set to `NULL` — the actual raw payload in external storage is no longer referenced |

The retention service runs a **three-phase idempotent purge** daily. Each phase writes an `AuditLog` entry *before* making any deletions, ensuring full auditability.

---

## Configuring Retention

Set retention policy per organisation via the admin API:

```bash
curl -X PATCH http://localhost:8000/api/v1/admin/org/settings \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "retention": {
      "investigations_days": 180,
      "evidence_metadata_days": 60,
      "raw_payload_days": 14
    }
  }'
```

Changes take effect on the next daily purge run.

---

## Common Retention Configurations

### Compliance-heavy (HIPAA / SOC 2)

```json
{
  "investigations_days": 365,
  "evidence_metadata_days": 365,
  "raw_payload_days": 7
}
```

Keep investigation and evidence metadata for a full year for audit purposes. Expire raw payloads quickly since they may contain PII.

### Cost-optimised

```json
{
  "investigations_days": 90,
  "evidence_metadata_days": 30,
  "raw_payload_days": 7
}
```

Shorter windows reduce database size and storage costs.

### Development / testing

```json
{
  "investigations_days": 30,
  "evidence_metadata_days": 7,
  "raw_payload_days": 1
}
```

Aggressive purging for dev environments.

---

## What Each Phase Deletes

### Phase 1 — Investigation archive

```sql
-- Archive investigations resolved > N days ago
UPDATE investigations
SET status = 'archived'
WHERE status IN ('resolved', 'closed')
  AND resolved_at < NOW() - INTERVAL 'N days';
```

Before archiving, an `AuditLog` entry is written:

```json
{
  "event_type": "retention_phase1_archive",
  "entity_type": "investigation",
  "metadata": { "count": 12, "cutoff": "2023-10-12T02:00:00Z" }
}
```

### Phase 2 — Evidence metadata deletion

```sql
-- Delete evidence for archived investigations older than evidence_metadata_days
DELETE FROM evidence_items
WHERE investigation_id IN (
  SELECT id FROM investigations WHERE status = 'archived'
)
AND fetched_at < NOW() - INTERVAL 'N days';
```

### Phase 3 — Raw payload expiry

```sql
-- Null the payload_ref for evidence older than raw_payload_days
UPDATE evidence_items
SET payload_ref = NULL
WHERE fetched_at < NOW() - INTERVAL 'N days'
  AND payload_ref IS NOT NULL;
```

The evidence row is kept (normalized_summary and metadata are preserved). Only the reference to the external raw payload is cleared.

---

## Running the Purge Manually

```bash
# In a container or locally
cd backend
python3 -c "
import asyncio
from app.services.retention_service import RetentionService
from app.core.db import get_async_session

async def run():
    async with get_async_session() as db:
        service = RetentionService(db)
        await service.run_daily_purge()
        print('Purge complete')

asyncio.run(run())
"
```

---

## Idempotency

The purge is fully idempotent. Running it twice produces the same result as running it once. This makes it safe to retry on failure or run from multiple processes (with appropriate database-level concurrency controls).

---

## Monitoring Retention

The purge writes to the audit log, which you can query:

```bash
curl "http://localhost:8000/api/v1/admin/audit-logs?event_type=retention_phase1_archive" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

You can also alert on absence of purge runs:

```yaml
# Prometheus — alert if no retention log entries in 25h
- alert: BugPilotRetentionNotRunning
  expr: |
    (time() - bugpilot_last_retention_run_timestamp) > 90000
  labels:
    severity: warning
  annotations:
    summary: "BugPilot retention job has not run in > 25 hours"
```
