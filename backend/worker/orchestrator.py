"""
Investigation orchestrator.

Drives the end-to-end investigation pipeline for a single SQS message:

1. Mark investigation as 'running' + record start time
2. Resolve window (since / window_minutes / absolute)
3. Load connectors via registry (isolated from direct imports)
4. Fetch events from all connectors (parallel via ThreadPoolExecutor)
5. Build/update AGE graph from GitHub events
6. Rank hypotheses
7. Generate LLM narrative
8. Calculate blast radius (if database connector with blast_radius role)
9. Persist results to DB
10. Notify (Slack + SNS)
11. Mark investigation as 'completed' or 'failed'

Steps are tracked in investigation_progress table for CLI polling.
"""
from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis as redis_lib

from backend.database import get_conn, release_conn, set_org_context

log = logging.getLogger(__name__)


def _get_redis() -> redis_lib.Redis:
    return redis_lib.Redis.from_url(
        os.environ["REDIS_URL"], decode_responses=True
    )


def _record_step(conn, investigation_id: str, step: str, status: str, duration_ms: Optional[int] = None):
    try:
        with conn.cursor() as cur:
            if status == "running":
                cur.execute(
                    """INSERT INTO investigation_progress (investigation_id, step, status, started_at)
                       VALUES (%s, %s, 'running', NOW())
                       ON CONFLICT (investigation_id, step) DO UPDATE
                       SET status = 'running', started_at = NOW()""",
                    (investigation_id, step),
                )
            else:
                cur.execute(
                    """UPDATE investigation_progress
                       SET status = %s, duration_ms = %s
                       WHERE investigation_id = %s AND step = %s""",
                    (status, duration_ms, investigation_id, step),
                )
        conn.commit()
    except Exception as e:
        log.warning(f"Progress record error: {e}")


def _resolve_window(
    window_minutes: int,
    since: Optional[str],
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if since:
        # Parse relative: "2h", "30m"
        if since.endswith("h"):
            delta = timedelta(hours=float(since[:-1]))
        elif since.endswith("m"):
            delta = timedelta(minutes=float(since[:-1]))
        else:
            # Try ISO8601
            try:
                start = datetime.fromisoformat(since.replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                return start, now
            except Exception:
                delta = timedelta(minutes=window_minutes)
        return now - delta, now
    return now - timedelta(minutes=window_minutes), now


def _fetch_connector_safe(connector, window_start, window_end, trigger_ref, service_name):
    """Fetch with timeout via ConnectorBase.fetch_with_timeout()."""
    try:
        data = connector.fetch_with_timeout(
            service_name=service_name,
            window_start=window_start,
            window_end=window_end,
            trigger_ref=trigger_ref,
        )
        return data
    except Exception as e:
        log.error(f"Connector {connector.connector_type}/{connector._connector_name} failed: {e}")
        return None


def run_investigation(message: dict) -> None:
    """
    Entry point called by the worker for each SQS message.
    """
    investigation_id = message["investigation_id"]
    org_id = message["org_id"]
    trigger_ref = message.get("trigger_ref")
    trigger_source = message.get("trigger_source", "cli")
    service_name = message.get("service_name")
    window_minutes = int(message.get("window_minutes", 30))
    since = message.get("since")
    suppress_slack = message.get("suppress_slack", False)
    text = message.get("text", "")

    start_time = time.time()
    conn = get_conn()
    redis_client = _get_redis()

    try:
        set_org_context(conn, org_id)

        # Step 0: Mark running
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE investigations SET status='running', started_at=NOW() WHERE id=%s",
                (investigation_id,),
            )
        conn.commit()

        # Step 1: Resolve window
        _record_step(conn, investigation_id, "resolve_window", "running")
        t0 = time.time()
        window_start, window_end = _resolve_window(window_minutes, since)
        _record_step(conn, investigation_id, "resolve_window", "done",
                     int((time.time() - t0) * 1000))

        # Step 2: Load connectors
        _record_step(conn, investigation_id, "load_connectors", "running")
        t0 = time.time()
        from backend.connectors.registry import get_connectors_for_service
        connectors = get_connectors_for_service(org_id, service_name, conn)
        _record_step(conn, investigation_id, "load_connectors", "done",
                     int((time.time() - t0) * 1000))

        connectors_used = [c.connector_type for c in connectors]
        connectors_missing = []

        # Check for required connectors
        conn_types = {c.connector_type for c in connectors}
        if "github" not in conn_types:
            connectors_missing.append("github")
        if not conn_types & {"sentry", "jira", "freshdesk", "email_imap"}:
            connectors_missing.append("ticket_source")

        # Step 3: Fetch events
        _record_step(conn, investigation_id, "fetch_events", "running")
        t0 = time.time()

        all_events: dict[str, list] = {
            "github": [], "sentry": [], "jira": [], "freshdesk": [],
            "email_imap": [], "database": [], "log_files": [],
        }

        with ThreadPoolExecutor(max_workers=min(len(connectors), 8)) as executor:
            futures = {
                executor.submit(
                    _fetch_connector_safe, c,
                    window_start, window_end, trigger_ref, service_name
                ): c
                for c in connectors
            }
            for future in as_completed(futures):
                connector = futures[future]
                data = future.result()
                if data and data.normalised_events:
                    key = connector.connector_type
                    all_events.setdefault(key, []).extend(data.normalised_events)

        _record_step(conn, investigation_id, "fetch_events", "done",
                     int((time.time() - t0) * 1000))

        # Step 4: Build AGE graph
        _record_step(conn, investigation_id, "build_graph", "running")
        t0 = time.time()
        if all_events.get("github"):
            try:
                from backend.worker.graph_builder import upsert_pr_nodes
                count = upsert_pr_nodes(conn, org_id, all_events["github"])
                log.info(f"AGE: upserted {count} PR nodes")
            except Exception as e:
                log.warning(f"AGE graph build error: {e}")
        _record_step(conn, investigation_id, "build_graph", "done",
                     int((time.time() - t0) * 1000))

        # Step 5: Rank hypotheses
        _record_step(conn, investigation_id, "rank_hypotheses", "running")
        t0 = time.time()

        ticket_events = (
            all_events.get("jira", []) +
            all_events.get("freshdesk", []) +
            all_events.get("email_imap", [])
        )
        sentry_events = all_events.get("sentry", [])
        blast_user_ids: list[str] = []

        from backend.worker.hypothesis_ranker import rank_hypotheses
        hypotheses = rank_hypotheses(
            org_id=org_id,
            pr_events=all_events.get("github", []),
            ticket_events=ticket_events,
            sentry_events=sentry_events,
            blast_user_ids=blast_user_ids,
            window_start=window_start,
            window_end=window_end,
            db_conn=conn,
            redis_client=redis_client,
        )
        _record_step(conn, investigation_id, "rank_hypotheses", "done",
                     int((time.time() - t0) * 1000))

        # Step 6: Generate narrative
        _record_step(conn, investigation_id, "generate_narrative", "running")
        t0 = time.time()

        ticket_summary = (
            text or
            (ticket_events[0].get("title", "") if ticket_events else "") or
            (trigger_ref or "")
        )

        from backend.worker.llm_client import generate_narrative
        narrative = generate_narrative(
            investigation_id=investigation_id,
            ticket_summary=ticket_summary,
            hypotheses=hypotheses,
            sentry_events=sentry_events,
            redis_client=redis_client,
        )
        _record_step(conn, investigation_id, "generate_narrative", "done",
                     int((time.time() - t0) * 1000))

        # Step 7: Blast radius from database connector
        blast_count = None
        blast_value_usd = None
        blast_cohort = None
        blast_status = None

        db_events = all_events.get("database", [])
        blast_records = [e for e in db_events if e.get("event_type") == "blast_radius_record"]
        if blast_records:
            blast_count = len(blast_records)
            blast_status = "estimated"
            blast_cohort = service_name or "all_users"

        # Step 8: Persist results
        _record_step(conn, investigation_id, "persist_results", "running")
        t0 = time.time()

        top = hypotheses[0] if hypotheses else {}
        duration_ms = int((time.time() - start_time) * 1000)

        # Detect failure class from events
        failure_class = _detect_failure_class(ticket_events + sentry_events)

        with conn.cursor() as cur:
            cur.execute(
                """UPDATE investigations SET
                   status = 'completed',
                   failure_class = %s,
                   duration_ms = %s,
                   llm_narrative = %s,
                   top_pr_id = %s,
                   top_pr_url = %s,
                   top_file = %s,
                   top_line = %s,
                   top_confidence = %s,
                   top_diff_type = %s,
                   blast_count = %s,
                   blast_value_usd = %s,
                   blast_cohort = %s,
                   blast_status = %s,
                   window_start = %s,
                   window_end = %s,
                   connectors_used = %s::jsonb,
                   connectors_missing = %s::jsonb
                   WHERE id = %s""",
                (
                    failure_class,
                    duration_ms,
                    narrative,
                    str(top.get("pr_id")) if top.get("pr_id") else None,
                    top.get("pr_url"),
                    top.get("file_path"),
                    top.get("line_number"),
                    top.get("confidence"),
                    top.get("diff_type"),
                    blast_count,
                    blast_value_usd,
                    blast_cohort,
                    blast_status,
                    window_start,
                    window_end,
                    json.dumps(connectors_used),
                    json.dumps(connectors_missing),
                    investigation_id,
                ),
            )

        # Persist hypotheses
        for h in hypotheses:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO investigation_hypotheses
                       (investigation_id, rank, pr_id, pr_url, pr_title, pr_author,
                        pr_merged_at, file_path, line_number, diff_type, confidence,
                        feature_scores, evidence, conflict_note)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                       ON CONFLICT DO NOTHING""",
                    (
                        investigation_id, h["rank"],
                        str(h.get("pr_id")) if h.get("pr_id") else None,
                        h.get("pr_url"), h.get("pr_title"), h.get("pr_author"),
                        h.get("pr_merged_at"), h.get("file_path"), h.get("line_number"),
                        h.get("diff_type"), h.get("confidence"),
                        json.dumps(h.get("feature_scores", {})),
                        json.dumps(h.get("evidence", {})),
                        h.get("conflict_note"),
                    ),
                )

        conn.commit()
        _record_step(conn, investigation_id, "persist_results", "done",
                     int((time.time() - t0) * 1000))

        # Step 9: Notify
        _notify(
            investigation_id, org_id, conn,
            hypotheses, narrative, blast_count, blast_value_usd,
            suppress_slack, redis_client,
        )

        log.info(
            f"Investigation {investigation_id} completed in {duration_ms}ms, "
            f"{len(hypotheses)} hypotheses"
        )

    except Exception as e:
        log.error(f"Investigation {investigation_id} failed: {e}", exc_info=True)
        try:
            set_org_context(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE investigations SET status='failed', error_message=%s WHERE id=%s",
                    (str(e)[:500], investigation_id),
                )
            conn.commit()
        except Exception:
            pass

        from backend.worker.notifier import publish_sns
        try:
            publish_sns(investigation_id, org_id, "failed", [], str(e))
        except Exception:
            pass

    finally:
        release_conn(conn)


def _detect_failure_class(events: list[dict]) -> Optional[str]:
    """Simple keyword-based failure class detection."""
    text = " ".join(
        (ev.get("title", "") + " " + ev.get("description", "")).lower()
        for ev in events
    )
    if any(k in text for k in ("payment", "charge", "invoice", "billing", "refund")):
        return "payment"
    if any(k in text for k in ("login", "auth", "token", "session", "password")):
        return "authentication"
    if any(k in text for k in ("timeout", "latency", "slow", "performance")):
        return "performance"
    if any(k in text for k in ("500", "error", "exception", "crash")):
        return "server_error"
    return "functional"


def _notify(
    investigation_id: str,
    org_id: str,
    conn,
    hypotheses: list[dict],
    narrative: str,
    blast_count: Optional[int],
    blast_value_usd,
    suppress_slack: bool,
    redis_client,
) -> None:
    from backend.worker.notifier import publish_sns, send_slack

    # Build investigation dict for notifier
    inv = {
        "id": investigation_id,
        "service_name": None,
        "trigger_ref": None,
        "llm_narrative": narrative,
        "blast_count": blast_count,
        "blast_value_usd": blast_value_usd,
    }

    try:
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT service_name, trigger_ref, duration_ms FROM investigations WHERE id=%s",
                (investigation_id,),
            )
            row = cur.fetchone()
        if row:
            inv["service_name"] = row[0]
            inv["trigger_ref"] = row[1]
            inv["duration_ms"] = row[2]
    except Exception:
        pass

    # SNS (always)
    publish_sns(investigation_id, org_id, "completed", hypotheses)

    # Slack (unless suppressed)
    if not suppress_slack:
        try:
            slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
            if slack_webhook:
                send_slack(slack_webhook, inv, hypotheses)
        except Exception as e:
            log.warning(f"Slack notify error: {e}")
