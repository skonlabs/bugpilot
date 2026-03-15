"""
Freshdesk connector — fetches support tickets in the investigation window.

Config keys:
  domain      — e.g. yourcompany.freshdesk.com
  api_key     — Freshdesk API key

UES event types emitted: ticket_created
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from connectors._base.connector_base import ConnectorBase, ConnectorData, ConnectorHealth
from connectors._base.normaliser_base import NormaliserBase, utcnow_iso
from connectors._base.pii_scrubber import scrub

log = logging.getLogger(__name__)


class FreshdeskNormaliser(NormaliserBase):
    def to_ues(self, raw: dict) -> dict:
        event = self._base_event(
            event_type="ticket_created",
            source="freshdesk",
            source_id=str(raw.get("id", "")),
        )
        event.update({
            "timestamp": raw.get("created_at") or utcnow_iso(),
            "title": scrub(raw.get("subject", "")),
            "description": scrub(raw.get("description_text", "")),
            "status": raw.get("status", 0),
            "priority": raw.get("priority", 0),
            "requester_email": scrub(raw.get("requester", {}).get("email", "")),
            "tags": raw.get("tags", []),
            "type": raw.get("type", ""),
            "url": f"https://{self._config.get('domain','')}/helpdesk/tickets/{raw.get('id','')}",
        })
        return event


class FreshdeskConnector(ConnectorBase):
    connector_type = "freshdesk"
    rate_limit_rpm = 60

    def validate_config(self) -> None:
        required = ["domain", "api_key"]
        missing = [k for k in required if not self._config.get(k)]
        if missing:
            raise ValueError(f"Freshdesk connector missing config keys: {missing}")

    def health_check(self) -> ConnectorHealth:
        try:
            resp = self._client().get(f"{self._base_url()}/api/v2/agents/me")
            resp.raise_for_status()
            agent = resp.json()
            return ConnectorHealth(
                status="ok",
                message=f"Connected as {agent.get('contact', {}).get('email', '')}",
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
        normaliser = FreshdeskNormaliser(self._config, self.org_id)

        start = window_start or datetime.now(timezone.utc)
        end = window_end or datetime.now(timezone.utc)

        events = []
        raw_count = 0
        page = 1

        try:
            while True:
                params = {
                    "updated_since": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "page": page,
                    "per_page": 100,
                    "include": "requester",
                }
                resp = self._client().get(
                    f"{self._base_url()}/api/v2/tickets",
                    params=params,
                )
                resp.raise_for_status()
                tickets = resp.json()

                if not tickets:
                    break

                for ticket in tickets:
                    # Filter by window_end
                    created = ticket.get("created_at", "")
                    if created and created > end.strftime("%Y-%m-%dT%H:%M:%SZ"):
                        continue
                    raw_count += 1
                    try:
                        events.append(normaliser.to_ues(ticket))
                    except Exception as e:
                        log.warning(f"Freshdesk normalise error: {e}")

                if len(tickets) < 100:
                    break
                page += 1

        except Exception as e:
            log.error(f"Freshdesk fetch error: {e}")
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
            metadata={"domain": self._config["domain"]},
            warnings=[],
        )

    def _base_url(self) -> str:
        domain = self._config["domain"].rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return domain

    def _client(self) -> httpx.Client:
        return httpx.Client(
            auth=(self._config["api_key"], "X"),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
