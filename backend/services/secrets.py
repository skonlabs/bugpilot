"""
AWS Secrets Manager wrapper.

All connector credentials are stored as JSON secrets under:
  bugpilot/{env}/{org_id}/{connector_type}/{connector_name}

The secret value is a JSON object whose shape is connector-specific.

Local dev mode (BUGPILOT_ENV != "production"):
  Secrets are stored as JSON files in <project-root>/.local-secrets/
  instead of AWS Secrets Manager so the backend works without AWS credentials.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_client = None

# ── Local dev helpers ─────────────────────────────────────────────────────────

def _is_local() -> bool:
    return os.environ.get("BUGPILOT_ENV", "development") != "production"


def _local_dir() -> Path:
    base = Path(__file__).resolve().parent.parent.parent / ".local-secrets"
    base.mkdir(exist_ok=True)
    return base


def _local_path(org_id: str, connector_type: str, connector_name: str) -> Path:
    safe_name = f"{org_id}__{connector_type}__{connector_name}.json"
    return _local_dir() / safe_name

# ── AWS helpers ───────────────────────────────────────────────────────────────

def _get_client():
    global _client
    if _client is None:
        import boto3
        _client = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return _client


def _secret_name(org_id: str, connector_type: str, connector_name: str) -> str:
    env = os.environ.get("BUGPILOT_ENV", "production")
    return f"bugpilot/{env}/{org_id}/{connector_type}/{connector_name}"

# ── Public API ────────────────────────────────────────────────────────────────

def get_secret(org_id: str, connector_type: str, connector_name: str = "default") -> dict[str, Any]:
    """Fetch and decode a connector secret. Raises KeyError if not found."""
    if _is_local():
        path = _local_path(org_id, connector_type, connector_name)
        if not path.exists():
            raise KeyError(f"Secret not found: {path}")
        return json.loads(path.read_text())

    from botocore.exceptions import ClientError
    name = _secret_name(org_id, connector_type, connector_name)
    try:
        resp = _get_client().get_secret_value(SecretId=name)
        raw = resp.get("SecretString") or resp.get("SecretBinary", b"").decode()
        return json.loads(raw)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("ResourceNotFoundException", "NoSuchEntityException"):
            raise KeyError(f"Secret not found: {name}") from e
        raise


def put_secret(
    org_id: str,
    connector_type: str,
    connector_name: str,
    value: dict[str, Any],
) -> None:
    """Create or update a connector secret."""
    if _is_local():
        path = _local_path(org_id, connector_type, connector_name)
        path.write_text(json.dumps(value, indent=2))
        log.info(f"[local] Secret written to {path}")
        return

    from botocore.exceptions import ClientError
    name = _secret_name(org_id, connector_type, connector_name)
    client = _get_client()
    try:
        client.put_secret_value(SecretId=name, SecretString=json.dumps(value))
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            client.create_secret(Name=name, SecretString=json.dumps(value))
        else:
            raise


def delete_secret(org_id: str, connector_type: str, connector_name: str = "default") -> None:
    """Delete a connector secret."""
    if _is_local():
        path = _local_path(org_id, connector_type, connector_name)
        path.unlink(missing_ok=True)
        return

    from botocore.exceptions import ClientError
    name = _secret_name(org_id, connector_type, connector_name)
    try:
        _get_client().delete_secret(SecretId=name, ForceDeleteWithoutRecovery=True)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
