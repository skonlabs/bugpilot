"""
Database connector — two modes:

1. blast_radius: query the customer DB to count affected records
2. error_log_table: read an error_log table for structured error events

Config keys:
  dsn          — PostgreSQL DSN (or MySQL/etc if driver supports it)
  driver       — postgresql | mysql | sqlite (default: postgresql)
  role         — blast_radius | error_log_table | both
  blast_query  — SQL template for blast radius (params: :window_start, :window_end, :trigger_ref)
  error_log_table — table name for structured error log (default: error_log)
  error_log_columns — mapping of UES fields to column names

UES event types emitted:
  - error_event (error_log_table mode)
  - blast_radius_record (blast_radius mode)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from connectors._base.connector_base import ConnectorBase, ConnectorData, ConnectorHealth
from connectors._base.normaliser_base import NormaliserBase, utcnow_iso
from connectors._base.pii_scrubber import scrub

log = logging.getLogger(__name__)

DEFAULT_ERROR_LOG_COLUMNS = {
    "id": "id",
    "created_at": "created_at",
    "level": "level",
    "message": "message",
    "service": "service",
    "user_id": "user_id",
    "request_id": "request_id",
    "stack_trace": "stack_trace",
}


class DatabaseNormaliser(NormaliserBase):
    def to_ues(self, raw: dict) -> dict:
        event_type = raw.get("_event_type", "error_event")
        event = self._base_event(
            event_type=event_type,
            source="database",
            source_id=str(raw.get("id", "")),
        )
        event.update({
            "timestamp": str(raw.get("created_at") or utcnow_iso()),
            "title": scrub(str(raw.get("message", ""))[:200]),
            "level": raw.get("level", "error"),
            "service": raw.get("service", ""),
            "user_id": scrub(str(raw.get("user_id", ""))),
            "request_id": raw.get("request_id", ""),
            "stack_trace": scrub(str(raw.get("stack_trace", ""))[:2000]),
            "count": raw.get("count", 1),
        })
        return event


class DatabaseConnector(ConnectorBase):
    connector_type = "database"
    rate_limit_rpm = 30

    def validate_config(self) -> None:
        if not self._config.get("dsn"):
            raise ValueError("Database connector requires 'dsn' field")

    def health_check(self) -> ConnectorHealth:
        try:
            import psycopg2
            conn = psycopg2.connect(self._config["dsn"], connect_timeout=5)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            return ConnectorHealth(status="ok", message="Database connection successful")
        except Exception as e:
            return ConnectorHealth(status="error", message=str(e))

    def fetch(
        self,
        service_name: Optional[str] = None,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        trigger_ref: Optional[str] = None,
        **kwargs,
    ) -> ConnectorData:
        role = self._config.get("role", "error_log_table")
        normaliser = DatabaseNormaliser(self._config, self.org_id)

        start = window_start or datetime.now(timezone.utc)
        end = window_end or datetime.now(timezone.utc)

        events = []
        raw_count = 0
        warnings = []
        metadata: dict = {}

        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(self._config["dsn"])

            if role in ("error_log_table", "both"):
                events, raw_count, warns = self._fetch_error_log(
                    conn, normaliser, service_name, start, end
                )
                warnings.extend(warns)

            if role in ("blast_radius", "both") and trigger_ref:
                br_events, br_count, br_meta, warns = self._fetch_blast_radius(
                    conn, normaliser, start, end, trigger_ref
                )
                events.extend(br_events)
                raw_count += br_count
                metadata.update(br_meta)
                warnings.extend(warns)

            conn.close()

        except Exception as e:
            log.error(f"Database fetch error: {e}")
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
            metadata=metadata,
            warnings=warnings,
        )

    def _fetch_error_log(self, conn, normaliser, service_name, start, end):
        table = self._config.get("error_log_table", "error_log")
        col_map = {**DEFAULT_ERROR_LOG_COLUMNS, **self._config.get("error_log_columns", {})}

        created_col = col_map["created_at"]
        service_col = col_map.get("service", "service")

        params = [start, end]
        where = f"{created_col} >= %s AND {created_col} <= %s"
        if service_name:
            where += f" AND {service_col} = %s"
            params.append(service_name)

        events = []
        warnings = []
        raw_count = 0

        try:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {table} WHERE {where} ORDER BY {created_col} DESC LIMIT 500",
                    params,
                )
                rows = cur.fetchall()

            for row in rows:
                raw_count += 1
                d = dict(row)
                d["_event_type"] = "error_event"
                # Remap columns to standard names
                for std_name, col_name in col_map.items():
                    if col_name in d and col_name != std_name:
                        d[std_name] = d.pop(col_name)
                try:
                    events.append(normaliser.to_ues(d))
                except Exception as e:
                    warnings.append(f"Row normalise error: {e}")

        except Exception as e:
            warnings.append(f"Error log query failed: {e}")
            log.warning(f"error_log fetch: {e}")

        return events, raw_count, warnings

    def _fetch_blast_radius(self, conn, normaliser, start, end, trigger_ref):
        blast_query = self._config.get("blast_query")
        events = []
        warnings = []
        raw_count = 0
        metadata = {}

        if not blast_query:
            return events, raw_count, metadata, warnings

        try:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(blast_query, {
                    "window_start": start,
                    "window_end": end,
                    "trigger_ref": trigger_ref,
                })
                rows = cur.fetchall()

            metadata["blast_count"] = len(rows)
            for row in rows:
                raw_count += 1
                d = dict(row)
                d["_event_type"] = "blast_radius_record"
                try:
                    events.append(normaliser.to_ues(d))
                except Exception as e:
                    warnings.append(f"Blast row normalise error: {e}")

        except Exception as e:
            warnings.append(f"Blast radius query failed: {e}")
            log.warning(f"blast_radius fetch: {e}")

        return events, raw_count, metadata, warnings
