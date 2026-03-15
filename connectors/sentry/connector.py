"""
Sentry connector — fetches issues and events in the investigation window.

Config keys (stored in Secrets Manager):
  auth_token   — Sentry auth token (sentry.io/settings → API Tokens)
  org_slug     — Sentry organisation slug
  project_slugs — list of project slugs to query (optional; all if omitted)
  base_url     — Sentry base URL (default: https://sentry.io)

UES event types emitted: error_event
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from connectors._base.connector_base import ConnectorBase, ConnectorData, ConnectorHealth
from connectors._base.normaliser_base import NormaliserBase, utcnow_iso
from connectors._base.pii_scrubber import scrub

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://sentry.io"
ISSUES_PER_PAGE = 100


class SentryNormaliser(NormaliserBase):
    def to_ues(self, raw: dict) -> dict:
        event = self._base_event(
            event_type="error_event",
            source="sentry",
            source_id=raw.get("id", ""),
        )
        event.update({
            "timestamp": raw.get("firstSeen") or utcnow_iso(),
            "title": scrub(raw.get("title", "")),
            "level": raw.get("level", "error"),
            "count": raw.get("count", 1),
            "user_count": raw.get("userCount", 0),
            "project": raw.get("project", {}).get("slug", ""),
            "tags": scrub(raw.get("tags", [])),
            "culprit": raw.get("culprit", ""),
            "metadata": scrub(raw.get("metadata", {})),
            "first_seen": raw.get("firstSeen"),
            "last_seen": raw.get("lastSeen"),
        })
        return event


class SentryConnector(ConnectorBase):
    connector_type = "sentry"
    rate_limit_rpm = 60

    def validate_config(self) -> None:
        required = ["auth_token", "org_slug"]
        missing = [k for k in required if not self._config.get(k)]
        if missing:
            raise ValueError(f"Sentry connector missing config keys: {missing}")

    def health_check(self) -> ConnectorHealth:
        try:
            resp = self._client().get(
                f"{self._base_url()}/api/0/organizations/{self._config['org_slug']}/",
            )
            resp.raise_for_status()
            org = resp.json()
            return ConnectorHealth(
                status="ok",
                message=f"Connected to Sentry org: {org.get('name', '')}",
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
        normaliser = SentryNormaliser(self._config, self.org_id)
        events = []
        raw_count = 0

        start = window_start or datetime.now(timezone.utc)
        end = window_end or datetime.now(timezone.utc)
        start_str = start.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end.strftime("%Y-%m-%dT%H:%M:%S")

        project_slugs = self._config.get("project_slugs") or []
        if service_name and not project_slugs:
            smap = self._service_map or {}
            project_slugs = smap.get(service_name, [])

        query_params: dict[str, Any] = {
            "limit": ISSUES_PER_PAGE,
            "query": f"firstSeen:>{start_str} firstSeen:<{end_str}",
        }

        try:
            if project_slugs:
                for slug in project_slugs:
                    url = f"{self._base_url()}/api/0/projects/{self._config['org_slug']}/{slug}/issues/"
                    raw_count, events = self._fetch_issues(url, query_params, normaliser, raw_count, events)
            else:
                url = f"{self._base_url()}/api/0/organizations/{self._config['org_slug']}/issues/"
                raw_count, events = self._fetch_issues(url, query_params, normaliser, raw_count, events)
        except Exception as e:
            log.error(f"Sentry fetch error: {e}")
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
            metadata={"org_slug": self._config["org_slug"]},
            warnings=[],
        )

    def _fetch_issues(self, url, params, normaliser, raw_count, events):
        client = self._client()
        resp = client.get(url, params=params)
        resp.raise_for_status()
        issues = resp.json()
        for issue in issues:
            raw_count += 1
            try:
                events.append(normaliser.to_ues(issue))
            except Exception as e:
                log.warning(f"Sentry normalise error: {e}")
        return raw_count, events

    def _base_url(self) -> str:
        return self._config.get("base_url", DEFAULT_BASE_URL).rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            headers={"Authorization": f"Bearer {self._config['auth_token']}"},
            timeout=30,
        )
