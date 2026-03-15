"""
BugPilot Worker — SQS consumer.

Polls three SQS FIFO queues in priority order: p1 → p2 → retro.
Each message triggers run_investigation() in the orchestrator.

Signal handling: SIGTERM/SIGINT → finish current job then exit.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time

import boto3

log = logging.getLogger(__name__)

# ── Queue URLs ─────────────────────────────────────────────────────────────────
QUEUE_URLS = [
    os.environ.get("SQS_P1_URL", ""),
    os.environ.get("SQS_P2_URL", ""),
    os.environ.get("SQS_RETRO_URL", ""),
]

VISIBILITY_TIMEOUT = 300  # seconds — must exceed max investigation time
WAIT_SECONDS = 20         # long polling

# ── Graceful shutdown ──────────────────────────────────────────────────────────
_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    log.info(f"Received signal {signum}, shutting down after current job...")
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ── SQS helpers ────────────────────────────────────────────────────────────────

def _get_sqs():
    return boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _receive_message(sqs, queue_url: str):
    """Receive up to 1 message with long polling."""
    resp = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=WAIT_SECONDS,
        VisibilityTimeout=VISIBILITY_TIMEOUT,
        MessageAttributeNames=["All"],
    )
    messages = resp.get("Messages", [])
    return messages[0] if messages else None


def _delete_message(sqs, queue_url: str, receipt_handle: str):
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


def _extend_visibility(sqs, queue_url: str, receipt_handle: str, seconds: int = 60):
    """Extend visibility timeout to prevent re-delivery during long processing."""
    try:
        sqs.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=seconds,
        )
    except Exception as e:
        log.warning(f"Failed to extend visibility: {e}")


# ── Main loop ──────────────────────────────────────────────────────────────────

def run():
    log.info("BugPilot worker starting")
    sqs = _get_sqs()

    from worker.app.orchestrator import run_investigation

    while not _shutdown:
        message_found = False

        for queue_url in QUEUE_URLS:
            if not queue_url:
                continue
            if _shutdown:
                break

            try:
                msg = _receive_message(sqs, queue_url)
                if not msg:
                    continue

                message_found = True
                receipt = msg["ReceiptHandle"]
                body = json.loads(msg["Body"])

                inv_id = body.get("investigation_id", "?")
                job_type = body.get("job_type", "investigation")
                log.info(f"Processing {job_type}: {inv_id} from {queue_url.split('/')[-1]}")

                # Extend visibility every 60s during processing
                import threading
                stop_extend = threading.Event()

                def _extender():
                    while not stop_extend.wait(60):
                        _extend_visibility(sqs, queue_url, receipt, VISIBILITY_TIMEOUT)

                extender_thread = threading.Thread(target=_extender, daemon=True)
                extender_thread.start()

                try:
                    if job_type == "github_index":
                        _handle_github_index(body)
                    else:
                        run_investigation(body)

                    _delete_message(sqs, queue_url, receipt)
                    log.info(f"Completed {job_type}: {inv_id}")

                except Exception as e:
                    log.error(f"Job failed {job_type}: {inv_id}: {e}", exc_info=True)
                    # Don't delete — let SQS retry (up to DLQ redrive limit)
                finally:
                    stop_extend.set()

                # Process one message per queue scan cycle
                break

            except Exception as e:
                log.error(f"Queue poll error for {queue_url}: {e}")
                time.sleep(5)

        if not message_found:
            # All queues empty — short sleep before next scan
            time.sleep(1)

    log.info("BugPilot worker shutdown complete")


def _handle_github_index(message: dict) -> None:
    """Re-index a GitHub connector's PRs into AGE."""
    org_id = message["org_id"]
    connector_id = message.get("connector_id")
    connector_name = message.get("connector_name", "default")

    from backend.app.database import get_conn, release_conn, set_org_context
    from backend.app.services.secrets import get_secret
    from connectors.registry import get_connector
    from worker.app.graph_builder import upsert_pr_nodes
    from datetime import datetime, timedelta, timezone

    conn = get_conn()
    try:
        set_org_context(conn, org_id)
        config = get_secret(org_id, "github", connector_name)
        gh = get_connector("github", config, org_id, connector_name)
        window_start = datetime.now(timezone.utc) - timedelta(days=90)
        window_end = datetime.now(timezone.utc)
        data = gh.fetch_with_timeout(window_start=window_start, window_end=window_end)
        if data:
            count = upsert_pr_nodes(conn, org_id, data.normalised_events)
            log.info(f"GitHub index: upserted {count} PRs for org {org_id}")
    finally:
        release_conn(conn)


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    )
    run()
