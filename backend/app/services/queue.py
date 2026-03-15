"""
SQS investigation enqueue service.

Priority routing:
  p1  — ticket_source in (sentry, pagerduty) or explicitly urgent
  retro — layer == 'retro'
  p2  — everything else (default)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

import boto3

from backend.app.database import get_conn, release_conn, set_org_context

log = logging.getLogger(__name__)

_sqs: boto3.client = None  # type: ignore[assignment]


def _get_sqs():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _sqs


def _queue_url(priority: str) -> str:
    env_map = {
        "p1":    "SQS_P1_URL",
        "retro": "SQS_RETRO_URL",
        "p2":    "SQS_P2_URL",
    }
    key = env_map.get(priority, "SQS_P2_URL")
    url = os.environ.get(key, "")
    if not url:
        raise RuntimeError(f"SQS queue URL not configured: {key} is not set")
    return url


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
                    service_name, window_minutes, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 'queued')
                   RETURNING id""",
                (
                    org_id,
                    trigger_type,
                    trigger_ref,
                    trigger_source,
                    service_name,
                    window_minutes,
                ),
            )
            inv_id = cur.fetchone()[0]

        conn.commit()

        # Enqueue SQS message
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

        sqs = _get_sqs()
        queue_url = _queue_url(priority)
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
            MessageGroupId=org_id,           # FIFO group per org
            MessageDeduplicationId=inv_id,   # INV-XXX is unique
        )

        log.info(f"Enqueued {inv_id} to {priority} queue for org {org_id}")
        return inv_id

    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)
