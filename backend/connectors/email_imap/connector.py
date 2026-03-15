"""
Email IMAP connector — fetches emails from a support mailbox.

Config keys:
  host        — IMAP host (e.g. imap.gmail.com)
  port        — IMAP port (default 993)
  username    — email address
  password    — app password or OAuth token
  folder      — mailbox folder (default: INBOX)
  subject_filter — optional string that must appear in subject

UES event types emitted: ticket_created
"""
from __future__ import annotations

import email
import imaplib
import logging
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional

from backend.connectors._base.connector_base import ConnectorBase, ConnectorData, ConnectorHealth
from backend.connectors._base.normaliser_base import NormaliserBase, utcnow_iso
from backend.connectors._base.pii_scrubber import scrub

log = logging.getLogger(__name__)


def _decode_header_value(value: str) -> str:
    parts = decode_header(value or "")
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


class EmailNormaliser(NormaliserBase):
    def to_ues(self, raw: dict) -> dict:
        event = self._base_event(
            event_type="ticket_created",
            source="email_imap",
            source_id=raw.get("message_id", ""),
        )
        event.update({
            "timestamp": raw.get("date") or utcnow_iso(),
            "title": scrub(raw.get("subject", "(no subject)")),
            "description": scrub(raw.get("body", "")),
            "from_address": scrub(raw.get("from", "")),
            "to_address": scrub(raw.get("to", "")),
        })
        return event


class EmailImapConnector(ConnectorBase):
    connector_type = "email_imap"
    rate_limit_rpm = 30

    def validate_config(self) -> None:
        required = ["host", "username", "password"]
        missing = [k for k in required if not self._config.get(k)]
        if missing:
            raise ValueError(f"Email IMAP connector missing config keys: {missing}")

    def health_check(self) -> ConnectorHealth:
        try:
            imap = self._connect()
            imap.logout()
            return ConnectorHealth(status="ok", message="IMAP connection successful")
        except Exception as e:
            return ConnectorHealth(status="error", message=str(e))

    def fetch(
        self,
        service_name: Optional[str] = None,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        **kwargs,
    ) -> ConnectorData:
        normaliser = EmailNormaliser(self._config, self.org_id)

        start = window_start or datetime.now(timezone.utc)
        folder = self._config.get("folder", "INBOX")
        subject_filter = self._config.get("subject_filter", "")

        # IMAP date format: DD-Mon-YYYY
        since_str = start.strftime("%d-%b-%Y")

        events = []
        raw_count = 0

        try:
            imap = self._connect()
            imap.select(folder)

            criteria = [f'SINCE "{since_str}"']
            if subject_filter:
                criteria.append(f'SUBJECT "{subject_filter}"')

            search_str = " ".join(criteria) if len(criteria) > 1 else criteria[0]
            _, msg_nums = imap.search(None, search_str)

            for num in (msg_nums[0] or b"").split():
                try:
                    _, msg_data = imap.fetch(num, "(RFC822)")
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    subject = _decode_header_value(msg.get("Subject", ""))
                    from_addr = _decode_header_value(msg.get("From", ""))
                    to_addr = _decode_header_value(msg.get("To", ""))
                    message_id = msg.get("Message-ID", "")
                    date_str = msg.get("Date", "")

                    # Extract body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            ct = part.get_content_type()
                            if ct == "text/plain":
                                body = part.get_payload(decode=True).decode(
                                    part.get_content_charset() or "utf-8", errors="replace"
                                )
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(
                            msg.get_content_charset() or "utf-8", errors="replace"
                        )

                    raw_count += 1
                    raw = {
                        "subject": subject,
                        "from": from_addr,
                        "to": to_addr,
                        "message_id": message_id,
                        "date": date_str,
                        "body": body[:5000],  # cap at 5KB
                    }
                    events.append(normaliser.to_ues(raw))
                except Exception as e:
                    log.warning(f"Email parse error for msg {num}: {e}")

            imap.logout()

        except Exception as e:
            log.error(f"IMAP fetch error: {e}")
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
            metadata={"host": self._config["host"], "folder": folder},
            warnings=[],
        )

    def _connect(self) -> imaplib.IMAP4_SSL:
        port = int(self._config.get("port", 993))
        imap = imaplib.IMAP4_SSL(self._config["host"], port)
        imap.login(self._config["username"], self._config["password"])
        return imap
