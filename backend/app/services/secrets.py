"""
AWS Secrets Manager wrapper.

All connector credentials are stored as JSON secrets under:
  bugpilot/{env}/{org_id}/{connector_type}/{connector_name}

The secret value is a JSON object whose shape is connector-specific.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return _client


def _secret_name(org_id: str, connector_type: str, connector_name: str) -> str:
    env = os.environ.get("BUGPILOT_ENV", "production")
    return f"bugpilot/{env}/{org_id}/{connector_type}/{connector_name}"


def get_secret(org_id: str, connector_type: str, connector_name: str = "default") -> dict[str, Any]:
    """Fetch and decode a connector secret. Raises if not found."""
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
    """Delete a connector secret (no recovery window for cleanliness)."""
    name = _secret_name(org_id, connector_type, connector_name)
    try:
        _get_client().delete_secret(SecretId=name, ForceDeleteWithoutRecovery=True)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
