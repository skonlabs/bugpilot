"""
SQS investigation enqueue service.

Priority routing:
  p1  — ticket_source in (sentry, pagerduty) or explicitly urgent
  retro — layer == 'retro'
  p2  — everything else (default)

When SQS is not configured (local dev / inline mode), investigations are
dispatched in a background thread instead of being sent to SQS.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Optional

from backend.database import get_conn, release_conn, set_org_context

log = logging.getLogger(__name__)

_sqs = None


def _get_sqs():
    global _sqs
    if _sqs is None:
        import boto3
        _sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _sqs


def _queue_url(priority: str) -> str:
    env_map = {
        "p1":    "AWS_SQS_P1_URL",
        "retro": "AWS_SQS_RETRO_URL",
        "p2":    "AWS_SQS_P2_URL",
    }
    key = env_map.get(priority, "AWS_SQS_P2_URL")
    return os.environ.get(key, "")


def _sqs_configured(priority: str) -> bool:
    return bool(_queue_url(priority))


def _determine_priority(trigger_source: str, layer: str) -> str:
    if layer == "retro":
        return "retro"
    if trigger_source in ("sentry", "pagerduty"):
        return "p1"
    return "p2"


def enqueue_investigation(
    *,
    org_id: str,
    trigger_type: str,
    trigger_ref: Optional[str],
    trigger_source: str,
    service_name: Optional[str],
    window_minutes: int,
    since: Optional[str],
    suppress_slack: bool,
    text: Optional[str],
    layer: str = "l2",
) -> str:
    """
    1. Insert investigation row (status=queued) → get INV-XXX id.
    2. Enqueue SQS message.
    Returns investigation_id.
    """
    conn = get_conn()
    try:
        set_org_context(conn, org_id)

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO investigations
                   (org_id, trigger_type, trigger_ref, trigger_source,
                    service_name, window_minutes, layer, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'queued')
                   RETURNING id""",
                (
                    org_id,
                    trigger_type,
                    trigger_ref,
                    trigger_source,
                    service_name,
                    window_minutes,
                    layer,
                ),
            )
            inv_id = cur.fetchone()[0]

        conn.commit()

        # Build message payload
        priority = _determine_priority(trigger_source, layer)
        message = {
            "investigation_id": inv_id,
            "org_id": org_id,
            "trigger_type": trigger_type,
            "trigger_ref": trigger_ref,
            "trigger_source": trigger_source,
            "service_name": service_name,
            "window_minutes": window_minutes,
            "since": since,
            "suppress_slack": suppress_slack,
            "text": text,
            "layer": layer,
        }

        if _sqs_configured(priority):
            queue_url = _queue_url(priority)
            _get_sqs().send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message),
                MessageGroupId=org_id,
                MessageDeduplicationId=inv_id,
            )
            log.info(f"Enqueued {inv_id} to SQS {priority} queue for org {org_id}")
        else:
            # Local / inline mode: run investigation in background thread
            log.info(
                f"SQS not configured — running {inv_id} inline for org {org_id}"
            )
            _run_inline(message)

        return inv_id

    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def _run_inline(message: dict) -> None:
    """Run investigation in a background daemon thread (no SQS needed)."""
    def _target(msg: dict) -> None:
        try:
            from backend.worker.orchestrator import run_investigation
            run_investigation(msg)
        except Exception as e:
            log.error(f"Inline investigation {msg.get('investigation_id')} failed: {e}", exc_info=True)

    t = threading.Thread(target=_target, args=(message,), daemon=True)
    t.start()
