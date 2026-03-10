# How to Manage Users and Roles

BugPilot uses role-based access control (RBAC) with four roles. This guide covers role assignments, permissions, and common administration tasks.

---

## Roles

| Role | Description |
|------|-------------|
| `viewer` | Read-only access to investigations, evidence, and hypotheses |
| `investigator` | Can create and work investigations, collect evidence, run low-risk actions |
| `approver` | Inherits investigator + can approve medium/high/critical risk actions |
| `admin` | Full access including connector management, user management, org settings |

---

## Permission Matrix

| Permission | viewer | investigator | approver | admin |
|-----------|:------:|:------------:|:--------:|:-----:|
| `investigations:read` | ✓ | ✓ | ✓ | ✓ |
| `investigations:write` | | ✓ | ✓ | ✓ |
| `evidence:read` | ✓ | ✓ | ✓ | ✓ |
| `evidence:write` | | ✓ | ✓ | ✓ |
| `hypotheses:read` | ✓ | ✓ | ✓ | ✓ |
| `hypotheses:write` | | ✓ | ✓ | ✓ |
| `actions:read` | ✓ | ✓ | ✓ | ✓ |
| `actions:write` | | ✓ | ✓ | ✓ |
| `actions:approve` | | | ✓ | ✓ |
| `admin:manage` | | | | ✓ |

---

## Listing Users

```bash
curl http://localhost:8000/api/v1/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# [
#   {"id": "usr_abc", "email": "alice@acme.com", "role": "investigator", "is_active": true},
#   {"id": "usr_def", "email": "bob@acme.com",   "role": "approver",     "is_active": true},
#   {"id": "usr_ghi", "email": "carol@acme.com", "role": "viewer",       "is_active": true}
# ]
```

---

## Changing a User's Role

```bash
curl -X PATCH http://localhost:8000/api/v1/admin/users/usr_abc \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "approver"}'
```

Role changes take effect on the next API request — existing sessions are not invalidated immediately.

---

## Deactivating a User

```bash
curl -X DELETE http://localhost:8000/api/v1/admin/users/usr_abc \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Deactivated users cannot create new sessions. Existing tokens will be rejected at the next request.

---

## Approval Workflow

When a user runs `bugpilot fix suggest`, each action is assigned a risk level. The approval gate:

| Risk level | Approval required | Who can approve |
|-----------|-------------------|-----------------|
| `low` | No | Anyone (investigator+) can run immediately |
| `medium` | Yes | `approver` or `admin` role |
| `high` | Yes | `approver` or `admin` role |
| `critical` | Yes | `approver` or `admin` role |

### Approving an action (CLI)

```bash
# As a user with approver role:
bugpilot fix approve act_d2f4e1 \
  --note "Verified rollback path with infra team. Safe to proceed."
```

### Approving via API

```bash
curl -X POST http://localhost:8000/api/v1/actions/act_d2f4e1/approve \
  -H "Authorization: Bearer $APPROVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"note": "Approved — rollback verified safe."}'
```

### What happens after approval

1. The action status changes from `pending` → `approved`
2. Any `investigator` in the org can now run the action
3. The approval is recorded in the `approvals` table with approver user ID, timestamp, and note
4. The action execution is also logged to `audit_logs`

---

## Audit Log

All write operations are logged to the audit trail. Query it:

```bash
curl "http://localhost:8000/api/v1/admin/audit-logs?limit=50" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# [
#   {
#     "id": "aud_abc",
#     "event_type": "action_approved",
#     "entity_type": "action",
#     "entity_id": "act_d2f4e1",
#     "user_id": "usr_def",
#     "ip_address": "10.0.1.42",
#     "occurred_at": "2024-01-15T15:12:00Z",
#     "metadata": {"note": "Approved — rollback verified safe."}
#   }
# ]
```

Audit logs are retained according to the org's retention policy (default: 365 days).

---

## Org Settings

```bash
# Get current settings
curl http://localhost:8000/api/v1/admin/org/settings \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Update retention policy
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

Retention changes apply to the next daily purge run.
