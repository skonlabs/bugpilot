# How to Manage Users and Roles

BugPilot uses role-based access control (RBAC) with four roles. This guide covers role assignments, permissions, and administration tasks.

---

## Roles

| Role | Description |
|------|-------------|
| `viewer` | Read-only access — can view investigations, evidence, hypotheses, and actions |
| `investigator` | Standard user — can create investigations, add evidence, create hypotheses and actions |
| `approver` | All investigator permissions plus the ability to approve medium/high/critical-risk actions |
| `admin` | Full access — manages users, connectors, webhooks, org settings, and all data |

---

## Permission Matrix

| Permission | viewer | investigator | approver | admin |
|------------|--------|-------------|----------|-------|
| View investigations | ✓ | ✓ | ✓ | ✓ |
| Create/update investigations | | ✓ | ✓ | ✓ |
| View evidence | ✓ | ✓ | ✓ | ✓ |
| Add/delete evidence | | ✓ | ✓ | ✓ |
| View hypotheses | ✓ | ✓ | ✓ | ✓ |
| Create/update hypotheses | | ✓ | ✓ | ✓ |
| View actions | ✓ | ✓ | ✓ | ✓ |
| Create actions | | ✓ | ✓ | ✓ |
| **Approve medium/high/critical actions** | | | **✓** | **✓** |
| Manage users and roles | | | | ✓ |
| Manage connectors and webhooks | | | | ✓ |
| View audit log | | | | ✓ |
| Configure org settings | | | | ✓ |

---

## Action Approval Workflow

When an action is created with risk level `medium`, `high`, or `critical`, it is placed in `pending` status and cannot be run until approved by a user with the `approver` or `admin` role.

```
[investigator creates action]  →  Status: pending
         │
         ▼
[approver reviews]
         │
    ┌────┴────┐
  Approve    Reject
    │
    ▼
Status: approved  →  [investigator runs action]
```

Safe and low-risk actions skip the approval step and can be run immediately by the creating user.

---

## Managing Users

### Viewing Users

```bash
curl https://api.bugpilot.io/api/v1/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Changing a User's Role

```bash
curl -X PATCH https://api.bugpilot.io/api/v1/admin/users/{user_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "approver"}'
```

Valid roles: `viewer`, `investigator`, `approver`, `admin`

### Deactivating a User

```bash
curl -X DELETE https://api.bugpilot.io/api/v1/admin/users/{user_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Deactivated users lose access immediately. Their historical data (investigations, evidence, actions) is preserved.

---

## Audit Log

Every write operation is recorded in the audit log with:

- `user_id` — who performed the action
- `action` — what was done
- `ip_address` — where the request came from
- `occurred_at` — timestamp
- `metadata` — relevant IDs and field changes

```bash
curl "https://api.bugpilot.io/api/v1/admin/audit-logs?limit=50" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

The audit log is append-only and cannot be modified or deleted.

---

## CLI Token Roles

When a user activates the CLI with `bugpilot auth activate --key bp_...`, their token inherits the role assigned to them by the admin. The role is visible in `bugpilot auth whoami`.

If a command is rejected due to insufficient permissions, the CLI returns:

```
✗ Error: 403 Forbidden — insufficient role for this action
  Your role: investigator
  Required:  approver
```
