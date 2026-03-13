"""
BugPilot Mock API Server — for local CLI testing.

Usage:
    pip install 'fastapi[standard]' uvicorn
    python mock_server.py
    # or:
    uvicorn mock_server:app --reload --port 8000

Then in another terminal:
    export BUGPILOT_API_URL=http://localhost:8000
    export BUGPILOT_ANALYSIS_URL=http://localhost:8000
    bugpilot auth activate --key test-license-key-123 --email dev@example.com --accept-tos
    bugpilot auth whoami
    bugpilot investigate list
    ...
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="BugPilot Mock API", version="0.1.0")

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_VALID_LICENSE = "test-license-key-123"
_ACCESS_TOKEN = "mock-access-token"
_REFRESH_TOKEN = "mock-refresh-token"
_ORG_ID = "org-mock-001"
_USER_ID = "user-mock-001"

_store: dict[str, dict] = {
    "investigations": {},
    "evidence": {},
    "hypotheses": {},
    "actions": {},
    "timeline": {},
}

# Seed a couple of sample investigations so list/get work immediately
def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"

def _seed():
    inv_id = "inv-0001"
    _store["investigations"][inv_id] = {
        "id": inv_id,
        "org_id": _ORG_ID,
        "title": "High error rate on payment-service",
        "severity": "high",
        "status": "open",
        "symptom": "HTTP 5xx above 5%",
        "description": "Started around 14:30 UTC after the v2.3.1 deploy.",
        "outcome": None,
        "resolved_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    ev_id = "ev-0001"
    _store["evidence"][ev_id] = {
        "id": ev_id,
        "investigation_id": inv_id,
        "kind": "log",
        "label": "payment-service error logs",
        "source_uri": "https://logs.example.com/payment",
        "summary": "NullPointerException in PaymentProcessor.charge() at line 142",
        "connector_id": None,
        "expires_at": None,
        "created_at": _now(),
    }
    hyp_id = "hyp-0001"
    _store["hypotheses"][hyp_id] = {
        "id": hyp_id,
        "investigation_id": inv_id,
        "title": "DB connection pool exhausted after deploy",
        "status": "under_review",
        "confidence_score": 0.82,
        "reasoning": "Connection pool size was halved in v2.3.1 config.",
        "supporting_evidence": [ev_id],
        "generated_by_llm": True,
        "created_at": _now(),
    }
    act_id = "act-0001"
    _store["actions"][act_id] = {
        "id": act_id,
        "investigation_id": inv_id,
        "hypothesis_id": hyp_id,
        "title": "Increase DB connection pool size to 50",
        "action_type": "config_change",
        "risk_level": "low",
        "status": "pending",
        "description": "Edit payment-service Helm chart: db.poolSize=50",
        "rollback_plan": "Revert Helm chart to previous values.",
        "result": None,
        "created_at": _now(),
    }
    _store["timeline"][inv_id] = [
        {
            "id": "tl-0001",
            "investigation_id": inv_id,
            "occurred_at": _now(),
            "event_type": "deploy",
            "description": "Deployed v2.3.1 of payment-service",
            "source": "github",
        },
        {
            "id": "tl-0002",
            "investigation_id": inv_id,
            "occurred_at": _now(),
            "event_type": "alert",
            "description": "PagerDuty alert: 5xx rate > 5%",
            "source": "pagerduty",
        },
    ]

_seed()

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _require_auth(authorization: Optional[str]) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != _ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid access token")


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/auth/activate")
async def activate(request: Request):
    body = await request.json()
    key = body.get("license_key", "")
    if key != _VALID_LICENSE:
        raise HTTPException(status_code=402, detail=f"Invalid license key: '{key}'. Use '{_VALID_LICENSE}'.")
    return {
        "access_token": _ACCESS_TOKEN,
        "refresh_token": _REFRESH_TOKEN,
        "org_id": _ORG_ID,
        "user_id": _USER_ID,
        "role": "admin",
    }


@app.post("/api/v1/auth/refresh")
async def refresh_token(request: Request):
    body = await request.json()
    if body.get("refresh_token") != _REFRESH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return {"access_token": _ACCESS_TOKEN, "refresh_token": _REFRESH_TOKEN}


@app.post("/api/v1/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    return JSONResponse(status_code=204, content=None)


@app.get("/api/v1/auth/whoami")
async def whoami(authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    return {
        "user_id": _USER_ID,
        "org_id": _ORG_ID,
        "email": "dev@example.com",
        "display_name": "Dev User",
        "role": "admin",
    }


# ---------------------------------------------------------------------------
# License
# ---------------------------------------------------------------------------

@app.get("/api/v1/license/status")
async def license_status(authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    return {
        "status": "active",
        "tier": "pro",
        "org_id": _ORG_ID,
        "device_count": 1,
        "max_devices": 5,
        "expires_at": "2027-01-01T00:00:00Z",
        "entitlements": ["investigations", "evidence", "hypotheses", "actions", "analysis"],
    }


# ---------------------------------------------------------------------------
# Investigations
# ---------------------------------------------------------------------------

@app.get("/api/v1/investigations")
async def list_investigations(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    _require_auth(authorization)
    items = list(_store["investigations"].values())
    if status:
        items = [i for i in items if i["status"] == status]
    if severity:
        items = [i for i in items if i["severity"] == severity]
    start = (page - 1) * page_size
    return {"items": items[start : start + page_size], "total": len(items)}


@app.post("/api/v1/investigations")
async def create_investigation(request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    body = await request.json()
    inv_id = f"inv-{uuid.uuid4().hex[:8]}"
    inv = {
        "id": inv_id,
        "org_id": _ORG_ID,
        "title": body.get("title", "Untitled"),
        "severity": body.get("severity", "medium"),
        "status": body.get("status", "open"),
        "symptom": body.get("symptom"),
        "description": body.get("description"),
        "outcome": None,
        "resolved_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    _store["investigations"][inv_id] = inv
    _store["timeline"][inv_id] = []
    return inv


@app.get("/api/v1/investigations/{inv_id}")
async def get_investigation(inv_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    inv = _store["investigations"].get(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{inv_id}' not found")
    return inv


@app.patch("/api/v1/investigations/{inv_id}")
async def update_investigation(inv_id: str, request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    inv = _store["investigations"].get(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{inv_id}' not found")
    body = await request.json()
    for field in ("title", "status", "severity", "description", "outcome"):
        if field in body:
            inv[field] = body[field]
    inv["updated_at"] = _now()
    return inv


@app.post("/api/v1/investigations/{inv_id}/close")
async def close_investigation(inv_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    inv = _store["investigations"].get(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{inv_id}' not found")
    inv["status"] = "closed"
    inv["resolved_at"] = _now()
    inv["updated_at"] = _now()
    return inv


@app.delete("/api/v1/investigations/{inv_id}")
async def delete_investigation(inv_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    if inv_id not in _store["investigations"]:
        raise HTTPException(status_code=404, detail=f"Investigation '{inv_id}' not found")
    del _store["investigations"][inv_id]
    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@app.get("/api/v1/evidence")
async def list_evidence(
    investigation_id: Optional[str] = None,
    kind: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    _require_auth(authorization)
    items = list(_store["evidence"].values())
    if investigation_id:
        items = [e for e in items if e["investigation_id"] == investigation_id]
    if kind:
        items = [e for e in items if e["kind"] == kind]
    return {"items": items, "total": len(items)}


@app.post("/api/v1/evidence")
async def collect_evidence(request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    body = await request.json()
    ev_id = f"ev-{uuid.uuid4().hex[:8]}"
    ev = {
        "id": ev_id,
        "investigation_id": body.get("investigation_id"),
        "kind": body.get("kind", "log"),
        "label": body.get("label", ""),
        "source_uri": body.get("source_uri"),
        "summary": body.get("summary"),
        "connector_id": body.get("connector_id"),
        "expires_at": None,
        "created_at": _now(),
    }
    _store["evidence"][ev_id] = ev
    return ev


@app.get("/api/v1/evidence/{ev_id}")
async def get_evidence(ev_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    ev = _store["evidence"].get(ev_id)
    if not ev:
        raise HTTPException(status_code=404, detail=f"Evidence '{ev_id}' not found")
    return ev


@app.delete("/api/v1/evidence/{ev_id}")
async def delete_evidence(ev_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    if ev_id not in _store["evidence"]:
        raise HTTPException(status_code=404, detail=f"Evidence '{ev_id}' not found")
    del _store["evidence"][ev_id]
    return JSONResponse(status_code=204, content=None)


@app.post("/api/v1/investigations/{inv_id}/evidence/refresh")
async def refresh_evidence(inv_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    count = sum(1 for e in _store["evidence"].values() if e["investigation_id"] == inv_id)
    return {"refreshed": count}


# ---------------------------------------------------------------------------
# Hypotheses
# ---------------------------------------------------------------------------

@app.get("/api/v1/hypotheses")
async def list_hypotheses(
    investigation_id: Optional[str] = None,
    status: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    _require_auth(authorization)
    items = list(_store["hypotheses"].values())
    if investigation_id:
        items = [h for h in items if h["investigation_id"] == investigation_id]
    if status:
        items = [h for h in items if h["status"] == status]
    return {"items": items, "total": len(items)}


@app.post("/api/v1/hypotheses")
async def create_hypothesis(request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    body = await request.json()
    hyp_id = f"hyp-{uuid.uuid4().hex[:8]}"
    hyp = {
        "id": hyp_id,
        "investigation_id": body.get("investigation_id"),
        "title": body.get("title", ""),
        "status": "under_review",
        "confidence_score": body.get("confidence_score"),
        "reasoning": body.get("reasoning"),
        "supporting_evidence": body.get("supporting_evidence", []),
        "generated_by_llm": body.get("generated_by_llm", False),
        "created_at": _now(),
    }
    _store["hypotheses"][hyp_id] = hyp
    return hyp


@app.post("/api/v1/hypotheses/{hyp_id}/confirm")
async def confirm_hypothesis(hyp_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    hyp = _store["hypotheses"].get(hyp_id)
    if not hyp:
        raise HTTPException(status_code=404, detail=f"Hypothesis '{hyp_id}' not found")
    hyp["status"] = "confirmed"
    return hyp


@app.post("/api/v1/hypotheses/{hyp_id}/reject")
async def reject_hypothesis(hyp_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    hyp = _store["hypotheses"].get(hyp_id)
    if not hyp:
        raise HTTPException(status_code=404, detail=f"Hypothesis '{hyp_id}' not found")
    hyp["status"] = "rejected"
    return hyp


@app.patch("/api/v1/hypotheses/{hyp_id}")
async def update_hypothesis(hyp_id: str, request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    hyp = _store["hypotheses"].get(hyp_id)
    if not hyp:
        raise HTTPException(status_code=404, detail=f"Hypothesis '{hyp_id}' not found")
    body = await request.json()
    for field in ("title", "confidence_score", "reasoning"):
        if field in body:
            hyp[field] = body[field]
    return hyp


@app.post("/api/v1/investigations/{inv_id}/hypotheses/refresh")
async def refresh_hypotheses(inv_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    return {"status": "queued", "investigation_id": inv_id}


# ---------------------------------------------------------------------------
# Actions (fix)
# ---------------------------------------------------------------------------

@app.get("/api/v1/actions")
async def list_actions(
    investigation_id: Optional[str] = None,
    status: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    _require_auth(authorization)
    items = list(_store["actions"].values())
    if investigation_id:
        items = [a for a in items if a["investigation_id"] == investigation_id]
    if status:
        items = [a for a in items if a["status"] == status]
    return {"items": items, "total": len(items)}


@app.post("/api/v1/actions")
async def create_action(request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    body = await request.json()
    act_id = f"act-{uuid.uuid4().hex[:8]}"
    act = {
        "id": act_id,
        "investigation_id": body.get("investigation_id"),
        "hypothesis_id": body.get("hypothesis_id"),
        "title": body.get("title", ""),
        "action_type": body.get("action_type", "manual"),
        "risk_level": body.get("risk_level", "medium"),
        "status": "pending",
        "description": body.get("description"),
        "rollback_plan": body.get("rollback_plan"),
        "result": None,
        "created_at": _now(),
    }
    _store["actions"][act_id] = act
    return act


@app.get("/api/v1/actions/{act_id}")
async def get_action(act_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    act = _store["actions"].get(act_id)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action '{act_id}' not found")
    return act


@app.post("/api/v1/actions/{act_id}/approve")
async def approve_action(act_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    act = _store["actions"].get(act_id)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action '{act_id}' not found")
    act["status"] = "approved"
    return act


@app.post("/api/v1/actions/{act_id}/run")
async def run_action(act_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    act = _store["actions"].get(act_id)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action '{act_id}' not found")
    act["status"] = "completed"
    act["result"] = "Action executed successfully (mock)."
    return {"result": act["result"]}


@app.post("/api/v1/actions/{act_id}/dry-run")
async def dry_run_action(act_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    act = _store["actions"].get(act_id)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action '{act_id}' not found")
    return {
        "predicted_changes": f"[mock] Would execute: {act['title']}",
        "dry_run_output": "No side effects — mock dry run passed.",
    }


@app.post("/api/v1/actions/{act_id}/cancel")
async def cancel_action(act_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    act = _store["actions"].get(act_id)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action '{act_id}' not found")
    act["status"] = "cancelled"
    return act


# ---------------------------------------------------------------------------
# Timeline / graph
# ---------------------------------------------------------------------------

@app.get("/api/v1/graph/timeline")
async def get_timeline(investigation_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    events = _store["timeline"].get(investigation_id, [])
    return {"events": events}


@app.post("/api/v1/graph/timeline")
async def add_timeline_event(request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    body = await request.json()
    inv_id = body.get("investigation_id", "")
    event = {
        "id": f"tl-{uuid.uuid4().hex[:8]}",
        "investigation_id": inv_id,
        "occurred_at": body.get("occurred_at", _now()),
        "event_type": body.get("event_type", "manual"),
        "description": body.get("description", ""),
        "source": body.get("source", "cli"),
    }
    if inv_id not in _store["timeline"]:
        _store["timeline"][inv_id] = []
    _store["timeline"][inv_id].append(event)
    return event


# ---------------------------------------------------------------------------
# Analysis endpoints (ask, summary, compare, refresh)
# ---------------------------------------------------------------------------

@app.post("/api/v1/investigations/{inv_id}/ask")
async def ask(inv_id: str, request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    body = await request.json()
    question = body.get("question", "")
    return {
        "answer": f"[mock LLM answer] You asked: \"{question}\"\n\n"
                  f"Based on the evidence for investigation {inv_id}, "
                  "the most likely root cause is a misconfigured connection pool. "
                  "Consider reviewing the DB pool settings in the Helm chart.",
        "model": "mock-llm-v1",
    }


@app.get("/api/v1/investigations/{inv_id}/summary")
async def summary(inv_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    inv = _store["investigations"].get(inv_id, {})
    return {
        "summary": f"[mock summary] Investigation '{inv.get('title', inv_id)}' is currently "
                   f"{inv.get('status', 'open')} with {inv.get('severity', 'unknown')} severity. "
                   "Key evidence points to a DB connection pool issue introduced in the latest deploy. "
                   "Recommended action: increase pool size and roll back if symptoms persist.",
        "model": "mock-llm-v1",
    }


@app.get("/api/v1/investigations/{inv_id}/baseline-comparison")
async def baseline_comparison(
    inv_id: str,
    strategy: str = "last_healthy",
    authorization: Optional[str] = Header(None),
):
    _require_auth(authorization)
    return {
        "baseline_description": f"Last healthy snapshot before this incident (strategy: {strategy})",
        "metric_deltas": [
            {"metric": "error_rate", "baseline": 0.1, "current": 6.2, "delta": "+6.1%"},
            {"metric": "p99_latency_ms", "baseline": 120, "current": 980, "delta": "+860ms"},
            {"metric": "db_pool_wait_ms", "baseline": 2, "current": 450, "delta": "+448ms"},
        ],
        "degraded_services": ["payment-service", "checkout-api"],
    }


# ---------------------------------------------------------------------------
# Connector test
# ---------------------------------------------------------------------------

@app.post("/api/v1/admin/connectors/test")
async def test_connector(request: Request, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    body = await request.json()
    kind = body.get("kind", "unknown")
    return {"status": "ok", "latency_ms": 42.0, "kind": kind}


# ---------------------------------------------------------------------------
# Resolve (PATCH investigations alias used by resolve_cmd)
# ---------------------------------------------------------------------------

@app.get("/api/v1/investigations/{inv_id}/history")
async def get_history(inv_id: str, authorization: Optional[str] = Header(None)):
    _require_auth(authorization)
    return {
        "items": [
            {
                "id": f"hist-{uuid.uuid4().hex[:6]}",
                "investigation_id": inv_id,
                "field": "status",
                "old_value": "open",
                "new_value": "resolved",
                "changed_by": _USER_ID,
                "changed_at": _now(),
            }
        ],
        "total": 1,
    }


# ---------------------------------------------------------------------------
# Dev helpers
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "service": "bugpilot-mock-api",
        "docs": "/docs",
        "license_key": _VALID_LICENSE,
        "access_token": _ACCESS_TOKEN,
    }


@app.get("/api/v1/_reset")
async def reset_store():
    """Reset in-memory store and re-seed sample data (useful during tests)."""
    global _store
    _store = {"investigations": {}, "evidence": {}, "hypotheses": {}, "actions": {}, "timeline": {}}
    _seed()
    return {"status": "reset"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    print("\n  BugPilot Mock API")
    print("  ─────────────────")
    print(f"  License key : {_VALID_LICENSE}")
    print(f"  Access token: {_ACCESS_TOKEN}")
    print( "  Docs        : http://localhost:8000/docs")
    print( "  Reset store : http://localhost:8000/api/v1/_reset")
    print()
    print("  To test the CLI:")
    print("    export BUGPILOT_API_URL=http://localhost:8000")
    print("    export BUGPILOT_ANALYSIS_URL=http://localhost:8000")
    print(f"    bugpilot auth activate --key {_VALID_LICENSE} --email dev@example.com --accept-tos")
    print()
    uvicorn.run("mock_server:app", host="0.0.0.0", port=8000, reload=True)
