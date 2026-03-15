"""
Connector registry.

The worker and orchestrator import ONLY from this module — never directly
from individual connector packages.

Usage:
    from connectors.registry import get_connectors_for_service, get_connector

get_connectors_for_service() returns a list of ConnectorBase instances
configured for a given org and service_name.
"""
from __future__ import annotations

import logging
from typing import Optional

from connectors._base.connector_base import ConnectorBase

log = logging.getLogger(__name__)

# Registry maps connector type string → import path
_REGISTRY: dict[str, str] = {
    "sentry":       "connectors.sentry.connector",
    "jira":         "connectors.jira.connector",
    "freshdesk":    "connectors.freshdesk.connector",
    "email_imap":   "connectors.email_imap.connector",
    "github":       "connectors.github.connector",
    "database":     "connectors.database.connector",
    "log_files":    "connectors.log_files.connector",
}

_CLASS_NAMES: dict[str, str] = {
    "sentry":       "SentryConnector",
    "jira":         "JiraConnector",
    "freshdesk":    "FreshdeskConnector",
    "email_imap":   "EmailImapConnector",
    "github":       "GitHubConnector",
    "database":     "DatabaseConnector",
    "log_files":    "LogFilesConnector",
}


def _load_connector_class(connector_type: str):
    module_path = _REGISTRY.get(connector_type)
    if not module_path:
        raise ValueError(f"Unknown connector type: {connector_type}")
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, _CLASS_NAMES[connector_type])
    return cls


def get_connector(
    connector_type: str,
    config: dict,
    org_id: str,
    connector_name: str = "default",
    service_map: Optional[dict] = None,
) -> ConnectorBase:
    """Instantiate a single connector."""
    cls = _load_connector_class(connector_type)
    instance = cls(config=config, org_id=org_id)
    instance._connector_name = connector_name
    instance._service_map = service_map or {}
    return instance


def get_connectors_for_service(
    org_id: str,
    service_name: Optional[str],
    db_conn,
) -> list[ConnectorBase]:
    """
    Load all active connectors for an org, filtered by service_map.

    Fetches connector rows from DB, loads credentials from Secrets Manager,
    and returns instantiated connectors scoped to service_name.
    """
    from backend.app.database import set_org_context
    from backend.app.services.secrets import get_secret

    set_org_context(db_conn, org_id)

    with db_conn.cursor() as cur:
        cur.execute(
            """SELECT type, name, config, service_map, role, status
               FROM connectors
               WHERE org_id = %s AND status IN ('pending', 'healthy')
               ORDER BY type, name""",
            (org_id,),
        )
        rows = cur.fetchall()

    connectors: list[ConnectorBase] = []
    for conn_type, conn_name, _config_bytes, service_map, role, status in rows:
        if conn_type not in _REGISTRY:
            log.debug(f"Skipping unknown connector type: {conn_type}")
            continue

        # If service_map is set and service_name is specified, check scope
        smap = service_map or {}
        if service_name and smap:
            # service_map is {"service_name": ["connector_name1", ...]} or
            # {"service_name": true} — skip if service not mapped
            services_in_map = list(smap.keys())
            if service_name not in services_in_map:
                continue

        # Load credentials from Secrets Manager
        try:
            config = get_secret(org_id, conn_type, conn_name)
        except KeyError:
            log.warning(f"No secret for connector {conn_type}/{conn_name}, skipping")
            continue
        except Exception as e:
            log.error(f"Failed to load secret for {conn_type}/{conn_name}: {e}")
            continue

        try:
            instance = get_connector(conn_type, config, org_id, conn_name, smap)
            instance._service_name = service_name
            instance._role = role
            connectors.append(instance)
        except Exception as e:
            log.error(f"Failed to instantiate {conn_type}/{conn_name}: {e}")
            continue

    return connectors
