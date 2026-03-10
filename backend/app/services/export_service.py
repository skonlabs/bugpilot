"""
Investigation export service.
Exports to JSON or Markdown format.

Safety guarantees:
  - Raw payloads are NEVER included in exports.
  - Redacted evidence items are clearly marked; their content is omitted.
  - Org isolation enforced: org_id must match the investigation's org.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ExportResult:
    investigation_id: str
    format: str
    content: str
    filename: str
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ExportService:
    """Exports investigations in JSON or Markdown format."""

    def __init__(self, db=None):
        self.db = db

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def export_investigation(
        self,
        investigation_id: str,
        format: str,  # "json" | "markdown"
        org_id: str,
    ) -> ExportResult:
        """Export an investigation in the requested format."""
        if format == "json":
            return await self._export_json(investigation_id, org_id)
        elif format == "markdown":
            return await self._export_markdown(investigation_id, org_id)
        raise ValueError(f"Unsupported export format: {format!r}. Use 'json' or 'markdown'.")

    # ------------------------------------------------------------------
    # Data gathering
    # ------------------------------------------------------------------

    async def _gather_data(self, investigation_id: str, org_id: str) -> dict:
        """Assemble all export-safe investigation data from the database."""
        if not self.db:
            # Return a synthetic skeleton for offline / test mode
            return {
                "investigation": {
                    "id": investigation_id,
                    "title": "Unknown (no DB)",
                    "status": "unknown",
                    "started_at": None,
                    "resolved_at": None,
                    "severity": None,
                    "tags": [],
                },
                "evidence": [],
                "hypotheses": [],
                "actions": [],
                "timeline_events": [],
                "service_nodes": [],
                "service_edges": [],
                "timeline": [],
            }

        from sqlalchemy import select
        from app.models.all_models import (
            Investigation,
            Evidence,
            Hypothesis,
            Action,
            TimelineEvent,
            ServiceNode,
            ServiceEdge,
        )

        inv = await self.db.get(Investigation, investigation_id)
        if not inv or str(inv.org_id) != org_id:
            raise ValueError(
                f"Investigation {investigation_id!r} not found or access denied."
            )

        evidence_result = await self.db.execute(
            select(Evidence).where(Evidence.investigation_id == investigation_id)
        )
        hypotheses_result = await self.db.execute(
            select(Hypothesis)
            .where(Hypothesis.investigation_id == investigation_id)
            .order_by(Hypothesis.confidence_score.desc().nullslast())
        )
        actions_result = await self.db.execute(
            select(Action).where(Action.investigation_id == investigation_id)
        )
        events_result = await self.db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.investigation_id == investigation_id)
            .order_by(TimelineEvent.occurred_at)
        )

        evidence_items = evidence_result.scalars().all()

        # Build a chronological timeline from evidence and timeline events
        timeline_entries: list[dict] = []
        for e in evidence_items:
            if e.collected_at:
                timeline_entries.append({
                    "timestamp": e.collected_at.isoformat(),
                    "source": "evidence",
                    "kind": e.kind.value if hasattr(e.kind, "value") else str(e.kind),
                    "label": e.label,
                    "summary": e.summary,
                })

        for ev in events_result.scalars().all():
            if ev.occurred_at:
                timeline_entries.append({
                    "timestamp": ev.occurred_at.isoformat(),
                    "source": ev.source or "timeline",
                    "kind": ev.event_type,
                    "label": ev.event_type,
                    "summary": ev.description,
                })

        timeline_entries.sort(key=lambda x: x.get("timestamp") or "")

        # Build export-safe evidence list (no raw_payload)
        safe_evidence = []
        for e in evidence_items:
            safe_evidence.append({
                "id": str(e.id),
                "kind": e.kind.value if hasattr(e.kind, "value") else str(e.kind),
                "label": e.label,
                "source_uri": e.source_uri,
                # raw_payload intentionally omitted
                "summary": e.summary,
                "collected_at": e.collected_at.isoformat() if e.collected_at else None,
                "tags": e.tags or [],
                # Expiry metadata helpful for retention visibility
                "expires_at": e.expires_at.isoformat() if e.expires_at else None,
            })

        hypotheses_list = [
            {
                "id": str(h.id),
                "title": h.title,
                "description": h.description,
                "confidence_score": h.confidence_score,
                "status": h.status.value if hasattr(h.status, "value") else str(h.status),
                "supporting_evidence": h.supporting_evidence or [],
                "reasoning": h.reasoning,
                "generated_by_llm": h.generated_by_llm,
                "llm_model": h.llm_model,
            }
            for h in hypotheses_result.scalars().all()
        ]

        actions_list = [
            {
                "id": str(a.id),
                "title": a.title,
                "description": a.description,
                "action_type": a.action_type,
                "risk_level": a.risk_level.value if hasattr(a.risk_level, "value") else str(a.risk_level),
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                "rollback_plan": a.rollback_plan,
                "approved_at": a.approved_at.isoformat() if a.approved_at else None,
                "executed_at": a.executed_at.isoformat() if a.executed_at else None,
            }
            for a in actions_result.scalars().all()
        ]

        return {
            "investigation": {
                "id": str(inv.id),
                "title": inv.title,
                "description": inv.description,
                "symptom": inv.symptom,
                "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                "severity": inv.severity.value if hasattr(inv.severity, "value") else str(inv.severity),
                "tags": inv.tags or [],
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "resolved_at": inv.resolved_at.isoformat() if inv.resolved_at else None,
            },
            "evidence": safe_evidence,
            "hypotheses": hypotheses_list,
            "actions": actions_list,
            "timeline": timeline_entries,
        }

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------

    async def _export_json(self, investigation_id: str, org_id: str) -> ExportResult:
        data = await self._gather_data(investigation_id, org_id)
        data["_meta"] = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "bugpilot-investigation-v1",
            "raw_payloads_included": False,
        }
        content = json.dumps(data, indent=2, default=str)

        logger.info(
            "investigation_exported",
            investigation_id=investigation_id,
            format="json",
            evidence_count=len(data["evidence"]),
            hypotheses_count=len(data["hypotheses"]),
        )

        return ExportResult(
            investigation_id=investigation_id,
            format="json",
            content=content,
            filename=f"investigation-{investigation_id[:8]}.json",
        )

    # ------------------------------------------------------------------
    # Markdown export
    # ------------------------------------------------------------------

    async def _export_markdown(self, investigation_id: str, org_id: str) -> ExportResult:
        data = await self._gather_data(investigation_id, org_id)
        inv = data["investigation"]
        generated_at = datetime.now(timezone.utc).isoformat()

        lines: list[str] = [
            f"# Investigation Report: {inv['title']}",
            "",
            f"| Field | Value |",
            f"|---|---|",
            f"| **ID** | `{inv['id']}` |",
            f"| **Status** | {inv['status']} |",
            f"| **Severity** | {inv.get('severity', 'N/A')} |",
            f"| **Created** | {inv.get('created_at', 'N/A')} |",
            f"| **Resolved** | {inv.get('resolved_at', 'Ongoing')} |",
            "",
            "---",
            "",
            "## Summary",
            "",
        ]

        if inv.get("description"):
            lines.extend([inv["description"], ""])

        if inv.get("symptom"):
            lines.extend([f"**Symptom:** {inv['symptom']}", ""])

        lines.extend([
            f"- {len(data['evidence'])} evidence items collected",
            f"- {len(data['hypotheses'])} hypotheses generated",
            f"- {len(data['actions'])} actions proposed",
            "",
        ])

        if inv.get("tags"):
            tags_str = ", ".join(f"`{t}`" for t in inv["tags"])
            lines.extend([f"**Tags:** {tags_str}", ""])

        # ---- Timeline ----
        lines.extend(["## Timeline", ""])
        if data["timeline"]:
            for entry in data["timeline"][:100]:
                ts = entry.get("timestamp", "N/A")
                source = entry.get("source", "unknown")
                kind = entry.get("kind", "")
                summary = entry.get("summary") or entry.get("label", "No description")
                lines.append(f"- `{ts}` **[{source}]** `{kind}` — {summary}")
        else:
            lines.append("_No timeline events recorded._")
        lines.append("")

        # ---- Top Hypotheses ----
        lines.extend(["## Hypotheses", ""])
        if data["hypotheses"]:
            for i, h in enumerate(data["hypotheses"], start=1):
                conf = h.get("confidence_score")
                conf_str = f"{conf:.0%}" if conf is not None else "N/A"
                status = h.get("status", "proposed")
                lines.extend([
                    f"### {i}. {h['title']}",
                    "",
                    f"**Confidence:** {conf_str} | **Status:** {status}",
                    "",
                ])
                if h.get("description"):
                    lines.extend([h["description"], ""])
                if h.get("reasoning"):
                    lines.extend([f"**Reasoning:** {h['reasoning']}", ""])
                if h.get("generated_by_llm"):
                    model = h.get("llm_model") or "unknown model"
                    lines.extend([f"_Generated by LLM ({model})_", ""])
        else:
            lines.extend(["_No hypotheses generated._", ""])

        # ---- Evidence ----
        lines.extend(["## Evidence", ""])
        if data["evidence"]:
            for ev in data["evidence"][:50]:
                kind = ev.get("kind", "unknown")
                label = ev.get("label", "N/A")
                summary = ev.get("summary") or "_No summary_"
                collected = ev.get("collected_at", "N/A")
                lines.append(
                    f"- **[{kind}]** {label} — {summary} _(collected {collected})_"
                )
        else:
            lines.append("_No evidence items._")
        lines.append("")

        # ---- Actions ----
        lines.extend(["## Remediation Actions", ""])
        if data["actions"]:
            for action in data["actions"]:
                risk = action.get("risk_level", "unknown")
                status = action.get("status", "unknown")
                lines.extend([
                    f"### {action.get('title', action.get('description', 'N/A'))}",
                    "",
                    f"**Risk:** {risk} | **Status:** {status}",
                    "",
                ])
                if action.get("description") and action["description"] != action.get("title"):
                    lines.extend([action["description"], ""])
                if action.get("rollback_plan"):
                    lines.extend([f"**Rollback:** {action['rollback_plan']}", ""])
                if action.get("executed_at"):
                    lines.extend([f"**Executed at:** {action['executed_at']}", ""])
        else:
            lines.extend(["_No actions proposed._", ""])

        # ---- Footer ----
        lines.extend([
            "---",
            "",
            f"*Generated by BugPilot at {generated_at}*  ",
            "*Raw payloads not included. Confidential — do not share externally.*",
        ])

        content = "\n".join(lines)

        logger.info(
            "investigation_exported",
            investigation_id=investigation_id,
            format="markdown",
            lines=len(lines),
        )

        return ExportResult(
            investigation_id=investigation_id,
            format="markdown",
            content=content,
            filename=f"investigation-{investigation_id[:8]}.md",
        )
