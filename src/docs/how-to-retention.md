# How to Configure Data Retention

BugPilot implements a three-phase data retention policy, configurable per organisation. A daily purge job runs automatically at 02:00 UTC.

---

## Retention Phases

Data moves through three progressively smaller retention windows:

```
Investigation created
        │
        ▼
Phase 1: Investigation archive
  Resolved/closed investigations retained for N days
  Default: 90 days
        │
        ▼
Phase 2: Evidence metadata
  Evidence rows (metadata only) retained for N days
  Default: 30 days
        │
        ▼
Phase 3: Raw payload
  Raw evidence payloads purged after N days
  Default: 7 days
  (evidence row remains, payload_ref set to null)
```

---

## Defaults

| Phase | Default retention |
|-------|-----------------|
| Investigation archive | 90 days |
| Evidence metadata | 30 days |
| Raw payload | 7 days |

---

## Preset Configurations

### Compliance (longer retention)

```json
{
  "investigation_archive_days": 365,
  "evidence_metadata_days": 365,
  "raw_payload_days": 7
}
```

### Cost-optimised

```json
{
  "investigation_archive_days": 90,
  "evidence_metadata_days": 30,
  "raw_payload_days": 7
}
```

### Development / low-cost

```json
{
  "investigation_archive_days": 30,
  "evidence_metadata_days": 7,
  "raw_payload_days": 1
}
```

---

## Updating Retention Settings

Admins can update the retention policy via the API:

```bash
curl -X PATCH https://api.bugpilot.io/api/v1/admin/org/settings \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "retention": {
      "investigation_archive_days": 180,
      "evidence_metadata_days": 60,
      "raw_payload_days": 14
    }
  }'
```

---

## How the Purge Works

Each purge phase is fully idempotent — safe to run multiple times. Every deletion writes an entry to the audit log before data is removed, so you have a record of what was purged and when.

The purge runs automatically on a daily schedule. You can view recent purge activity in the audit log:

```bash
curl "https://api.bugpilot.io/api/v1/admin/audit-logs?action=retention_purge" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Notes

- Retention settings apply org-wide; per-investigation overrides are not currently supported
- Reducing retention takes effect on the next daily purge run
- Increasing retention is effective immediately (existing data is not retroactively deleted)
- The audit log itself is not subject to retention purges — it is permanent
