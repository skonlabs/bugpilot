"""
Jira connector — fetches bug tickets in the investigation window.

Config keys:
  base_url    — e.g. https://yourcompany.atlassian.net
  email       — Jira account email
  api_token   — Jira API token
  project_keys — list of project keys to query (e.g. ["ENG", "BUG"])
  jql_filter  — optional additional JQL filter

UES event types emitted: ticket_created
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.connectors._base.connector_base import ConnectorBase, ConnectorData, ConnectorHealth
from backend.connectors._base.normaliser_base import NormaliserBase, utcnow_iso
from backend.connectors._base.pii_scrubber import scrub

log = logging.getLogger(__name__)


class JiraNormaliser(NormaliserBase):
    def to_ues(self, raw: dict) -> dict:
        fields = raw.get("fields", {})
        event = self._base_event(
            event_type="ticket_created",
            source="jira",
            source_id=raw.get("key", raw.get("id", "")),
        )
        event.update({
            "timestamp": fields.get("created") or utcnow_iso(),
            "title": scrub(fields.get("summary", "")),
            "description": scrub(fields.get("description") or ""),
            "status": fields.get("status", {}).get("name", ""),
            "priority": fields.get("priority", {}).get("name", ""),
            "reporter": scrub(fields.get("reporter", {}).get("emailAddress", "")),
            "assignee": scrub(
                (fields.get("assignee") or {}).get("emailAddress", "")
            ),
            "labels": fields.get("labels", []),
            "components": [c.get("name") for c in fields.get("components", [])],
            "project_key": fields.get("project", {}).get("key", ""),
            "issue_type": fields.get("issuetype", {}).get("name", ""),
            "url": f"{self._config.get('base_url','')}/browse/{raw.get('key','')}",
        })
        return event


class JiraConnector(ConnectorBase):
    connector_type = "jira"
    rate_limit_rpm = 60

    def validate_config(self) -> None:
        required = ["base_url", "email", "api_token"]
        missing = [k for k in required if not self._config.get(k)]
        if missing:
            raise ValueError(f"Jira connector missing config keys: {missing}")

    def health_check(self) -> ConnectorHealth:
        try:
            resp = self._client().get(
                f"{self._base_url()}/rest/api/3/myself"
            )
            resp.raise_for_status()
            user = resp.json()
            return ConnectorHealth(
                status="ok",
                message=f"Connected as {user.get('emailAddress', '')}",
            )
        except Exception as e:
            return ConnectorHealth(status="error", message=str(e))

    def fetch(
        self,
        service_name: Optional[str] = None,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        **kwargs,
    ) -> ConnectorData:
        normaliser = JiraNormaliser(self._config, self.org_id)

        start = window_start or datetime.now(timezone.utc)
        end = window_end or datetime.now(timezone.utc)
        start_jira = start.strftime("%Y-%m-%d %H:%M")
        end_jira = end.strftime("%Y-%m-%d %H:%M")

        project_keys = self._config.get("project_keys", [])
        if service_name and not project_keys:
            smap = self._service_map or {}
            project_keys = smap.get(service_name, [])

        jql_parts = [
            f"created >= '{start_jira}'",
            f"created <= '{end_jira}'",
            "issuetype in (Bug)",
        ]
        if project_keys:
            keys_str = ", ".join(f'"{k}"' for k in project_keys)
            jql_parts.append(f"project in ({keys_str})")
        extra = self._config.get("jql_filter", "")
        if extra:
            jql_parts.append(extra)

        jql = " AND ".join(jql_parts)

        events = []
        raw_count = 0
        start_at = 0
        page_size = 100

        try:
            while True:
                resp = self._client().post(
                    f"{self._base_url()}/rest/api/3/search",
                    json={
                        "jql": jql,
                        "startAt": start_at,
                        "maxResults": page_size,
                        "fields": [
                            "summary", "description", "status", "priority",
                            "reporter", "assignee", "labels", "components",
                            "project", "issuetype", "created",
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                issues = data.get("issues", [])
                for issue in issues:
                    raw_count += 1
                    try:
                        events.append(normaliser.to_ues(issue))
                    except Exception as e:
                        log.warning(f"Jira normalise error: {e}")

                if start_at + page_size >= data.get("total", 0):
                    break
                start_at += page_size

        except Exception as e:
            log.error(f"Jira fetch error: {e}")
            return ConnectorData(
                connector_type=self.connector_type,
                normalised_events=[],
                raw_event_count=0,
                metadata={},
                warnings=[str(e)],
            )

        return ConnectorData(
            connector_type=self.connector_type,
            normalised_events=events,
            raw_event_count=raw_count,
            metadata={"base_url": self._base_url()},
            warnings=[],
        )

    def _base_url(self) -> str:
        return self._config["base_url"].rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            auth=(self._config["email"], self._config["api_token"]),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
