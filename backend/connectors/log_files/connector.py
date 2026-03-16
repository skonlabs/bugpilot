"""
Log files connector — reads structured (JSON) or unstructured log files.

Config keys:
  paths        — list of file paths or glob patterns
  format       — json | text (default: json)
  json_fields  — mapping of UES fields to JSON log fields
  text_pattern — regex pattern for parsing text logs (named groups: timestamp, level, message, service)
  encoding     — file encoding (default: utf-8)

UES event types emitted: error_event
"""
from __future__ import annotations

import glob
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from backend.connectors._base.connector_base import ConnectorBase, ConnectorData, ConnectorHealth
from backend.connectors._base.normaliser_base import NormaliserBase, utcnow_iso
from backend.connectors._base.pii_scrubber import scrub

log = logging.getLogger(__name__)

DEFAULT_TEXT_PATTERN = (
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"
    r".*?(?P<level>ERROR|WARN|INFO|DEBUG)"
    r".*?(?P<message>.+)$"
)

DEFAULT_JSON_FIELDS = {
    "timestamp": "timestamp",
    "level": "level",
    "message": "message",
    "service": "service",
    "request_id": "request_id",
}


class LogFilesNormaliser(NormaliserBase):
    def to_ues(self, raw: dict) -> dict:
        event = self._base_event(
            event_type="error_event",
            source="log_files",
            source_id=raw.get("_line_id", ""),
        )
        event.update({
            "timestamp": raw.get("timestamp") or utcnow_iso(),
            "title": scrub(str(raw.get("message", ""))[:200]),
            "level": raw.get("level", "ERROR"),
            "service": raw.get("service", ""),
            "request_id": raw.get("request_id", ""),
            "raw_line": scrub(raw.get("_raw", "")[:500]),
        })
        return event


class LogFilesConnector(ConnectorBase):
    connector_type = "log_files"
    rate_limit_rpm = 60

    def validate_config(self) -> None:
        if not self._config.get("paths"):
            raise ValueError("Log files connector requires 'paths' list")

    def health_check(self) -> ConnectorHealth:
        paths = self._config.get("paths", [])
        found = []
        missing = []
        for pattern in paths:
            matched = glob.glob(pattern)
            if matched:
                found.extend(matched)
            else:
                missing.append(pattern)

        if not found:
            return ConnectorHealth(
                status="error",
                message=f"No log files found. Missing: {missing}",
            )
        return ConnectorHealth(
            status="ok",
            message=f"Found {len(found)} log file(s)",
            details={"found": found[:10], "missing": missing},
        )

    def fetch(
        self,
        service_name: Optional[str] = None,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        **kwargs,
    ) -> ConnectorData:
        normaliser = LogFilesNormaliser(self._config, self.org_id)

        start = window_start or datetime.now(timezone.utc)
        end = window_end or datetime.now(timezone.utc)
        fmt = self._config.get("format", "json")
        encoding = self._config.get("encoding", "utf-8")
        paths_config = self._config.get("paths", [])

        # Expand globs
        all_files = []
        for pattern in paths_config:
            all_files.extend(glob.glob(pattern))

        events = []
        raw_count = 0
        warnings = []

        for filepath in all_files:
            try:
                file_events, file_count, file_warns = self._read_file(
                    filepath, fmt, encoding, normaliser, start, end, service_name
                )
                events.extend(file_events)
                raw_count += file_count
                warnings.extend(file_warns)
            except Exception as e:
                warnings.append(f"Error reading {filepath}: {e}")
                log.warning(f"Log file read error {filepath}: {e}")

        return ConnectorData(
            connector_type=self.connector_type,
            normalised_events=events,
            raw_event_count=raw_count,
            metadata={"files_read": len(all_files)},
            warnings=warnings,
        )

    def _read_file(
        self, filepath: str, fmt: str, encoding: str,
        normaliser: LogFilesNormaliser,
        start: datetime, end: datetime,
        service_name: Optional[str],
    ) -> tuple[list, int, list]:
        events = []
        raw_count = 0
        warnings = []

        json_fields = {**DEFAULT_JSON_FIELDS, **self._config.get("json_fields", {})}
        raw_pattern = self._config.get("text_pattern", DEFAULT_TEXT_PATTERN)
        try:
            text_pattern = re.compile(raw_pattern, re.MULTILINE | re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid text_pattern regex in log_files config: {e}") from e

        with open(filepath, encoding=encoding, errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    if fmt == "json":
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Map fields
                        mapped = {}
                        for std, src in json_fields.items():
                            if src in data:
                                mapped[std] = data[src]

                        # Filter by level (only errors)
                        level = mapped.get("level", "").upper()
                        if level not in ("ERROR", "FATAL", "CRITICAL"):
                            continue

                    else:  # text
                        m = text_pattern.match(line)
                        if not m:
                            continue
                        mapped = m.groupdict()
                        level = mapped.get("level", "").upper()
                        if level not in ("ERROR", "FATAL", "CRITICAL", "WARN", "WARNING"):
                            continue

                    # Filter by service_name
                    if service_name and mapped.get("service") and mapped["service"] != service_name:
                        continue

                    # Filter by timestamp window
                    ts_str = mapped.get("timestamp", "")
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(
                                ts_str.replace("T", " ").replace("Z", "+00:00")
                            )
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts < start or ts > end:
                                continue
                        except Exception:
                            pass  # include if can't parse timestamp

                    mapped["_line_id"] = f"{filepath}:{line_num}"
                    mapped["_raw"] = line
                    raw_count += 1
                    events.append(normaliser.to_ues(mapped))

                except Exception as e:
                    warnings.append(f"{filepath}:{line_num}: {e}")

        return events, raw_count, warnings
