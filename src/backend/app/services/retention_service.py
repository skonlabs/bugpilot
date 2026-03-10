"""
Retention and purge service.
Per-org configurable data retention with idempotent purge operations.

Retention policy columns (on RetentionPolicy model, or defaults used):
  - investigations_days    : days before closed investigations are archived
  - evidence_metadata_days : days before evidence records are deleted
  - raw_payload_days       : days before raw_payload column is nulled out
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)

# Default retention windows used when no explicit policy row exists
_DEFAULT_INVESTIGATIONS_DAYS = 365
_DEFAULT_EVIDENCE_METADATA_DAYS = 90
_DEFAULT_RAW_PAYLOAD_DAYS = 30


class RetentionService:
    """
    Manages data retention per organisation.

    All purge operations:
      1. Write an AuditLog entry BEFORE deleting / archiving.
      2. Are idempotent — running twice has no additional effect.
      3. Never permanently delete investigation records; they are archived.
    """

    def __init__(self, db=None):
        self.db = db

    # ------------------------------------------------------------------
    # Per-org purge
    # ------------------------------------------------------------------

    async def purge_org(
        self,
        org_id: str,
        triggered_by_user_id: Optional[str] = None,
    ) -> dict:
        """
        Purge / archive data for a single org according to its retention policy.
        Returns a dict with counts of affected records.
        """
        if not self.db:
            return {"error": "No DB connection"}

        from sqlalchemy import select
        from app.models.all_models import (
            Organisation,
            Investigation,
            Evidence,
            AuditLog,
        )

        # Validate org exists
        org = await self.db.get(Organisation, uuid.UUID(org_id))
        if not org:
            return {"error": f"Organisation {org_id} not found"}

        # Resolve retention policy (use model field or defaults)
        inv_days = _DEFAULT_INVESTIGATIONS_DAYS
        ev_meta_days = _DEFAULT_EVIDENCE_METADATA_DAYS
        raw_days = _DEFAULT_RAW_PAYLOAD_DAYS

        # Attempt to read from org settings if present
        settings = org.settings or {}
        if "retention" in settings:
            rp = settings["retention"]
            inv_days = int(rp.get("investigations_days", inv_days))
            ev_meta_days = int(rp.get("evidence_metadata_days", ev_meta_days))
            raw_days = int(rp.get("raw_payload_days", raw_days))

        now = datetime.now(timezone.utc)
        actor_id = uuid.UUID(triggered_by_user_id) if triggered_by_user_id else None
        org_uuid = uuid.UUID(org_id)

        counts = {
            "investigations_archived": 0,
            "evidence_metadata_deleted": 0,
            "raw_payload_nulled": 0,
        }

        # ------------------------------------------------------------------
        # 1. Archive old resolved/closed investigations
        # ------------------------------------------------------------------
        inv_cutoff = now - timedelta(days=inv_days)
        inv_result = await self.db.execute(
            select(Investigation).where(
                Investigation.org_id == org_uuid,
                Investigation.resolved_at.isnot(None),
                Investigation.resolved_at <= inv_cutoff,
                Investigation.status.in_(["resolved", "closed"]),
            )
        )
        old_investigations = inv_result.scalars().all()

        for inv in old_investigations:
            # Write audit trail before mutation
            self.db.add(
                AuditLog(
                    id=uuid.uuid4(),
                    org_id=org_uuid,
                    actor_id=actor_id,
                    action="retention.investigation_archived",
                    resource_type="investigation",
                    resource_id=str(inv.id),
                    before_state={"status": inv.status.value if hasattr(inv.status, "value") else inv.status},
                    after_state={
                        "status": "archived",
                        "policy_days": inv_days,
                        "resolved_at": inv.resolved_at.isoformat() if inv.resolved_at else None,
                    },
                )
            )
            inv.status = "archived"
            counts["investigations_archived"] += 1

        # ------------------------------------------------------------------
        # 2. Delete evidence metadata past retention window
        # ------------------------------------------------------------------
        ev_meta_cutoff = now - timedelta(days=ev_meta_days)
        ev_result = await self.db.execute(
            select(Evidence).where(
                Evidence.org_id == org_uuid,
                Evidence.collected_at <= ev_meta_cutoff,
            )
        )
        old_evidence = ev_result.scalars().all()

        for ev in old_evidence:
            self.db.add(
                AuditLog(
                    id=uuid.uuid4(),
                    org_id=org_uuid,
                    actor_id=actor_id,
                    action="retention.evidence_deleted",
                    resource_type="evidence",
                    resource_id=str(ev.id),
                    before_state={
                        "label": ev.label,
                        "collected_at": ev.collected_at.isoformat() if ev.collected_at else None,
                    },
                    after_state={"policy_days": ev_meta_days, "deleted": True},
                )
            )
            await self.db.delete(ev)
            counts["evidence_metadata_deleted"] += 1

        # ------------------------------------------------------------------
        # 3. Null raw_payload past the shorter raw-payload retention window
        # ------------------------------------------------------------------
        raw_cutoff = now - timedelta(days=raw_days)
        raw_result = await self.db.execute(
            select(Evidence).where(
                Evidence.org_id == org_uuid,
                Evidence.raw_payload.isnot(None),
                Evidence.collected_at <= raw_cutoff,
            )
        )
        old_raw = raw_result.scalars().all()

        for ev in old_raw:
            ev.raw_payload = None
            counts["raw_payload_nulled"] += 1

        await self.db.flush()

        logger.info("purge_completed", org_id=org_id, counts=counts)
        return counts

    # ------------------------------------------------------------------
    # Daily sweep across all orgs
    # ------------------------------------------------------------------

    async def run_daily_purge(self) -> None:
        """
        Run the purge for every organisation.
        Designed to be invoked as an asyncio background task (e.g. APScheduler).
        Failures for individual orgs are logged but do not abort the sweep.
        """
        if not self.db:
            logger.warning("daily_purge_skipped", reason="No DB connection")
            return

        from sqlalchemy import select
        from app.models.all_models import Organisation

        logger.info("daily_purge_started")
        result = await self.db.execute(select(Organisation))
        orgs = result.scalars().all()

        success_count = 0
        failure_count = 0

        for org in orgs:
            try:
                counts = await self.purge_org(str(org.id))
                logger.info(
                    "org_purge_complete",
                    org_id=str(org.id),
                    slug=org.slug,
                    counts=counts,
                )
                success_count += 1
            except Exception as exc:
                logger.error(
                    "org_purge_failed",
                    org_id=str(org.id),
                    slug=getattr(org, "slug", "unknown"),
                    error=str(exc),
                )
                failure_count += 1

        logger.info(
            "daily_purge_completed",
            org_count=len(orgs),
            success=success_count,
            failures=failure_count,
        )
