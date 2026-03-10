"""
Last-healthy comparison service.
Finds baseline windows and compares current state against them.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class BaselineStrategy(str, Enum):
    last_healthy_window = "last_healthy_window"
    last_stable_post_deploy = "last_stable_post_deploy"
    user_pinned = "user_pinned"


@dataclass
class Baseline:
    strategy: BaselineStrategy
    window_start: datetime
    window_end: datetime
    description: str
    metrics: dict[str, Any] = field(default_factory=dict)
    error_rate: float = 0.0
    alert_count: int = 0


@dataclass
class MetricDelta:
    metric_name: str
    service: str
    baseline_value: float
    current_value: float
    change_pct: float
    is_significant: bool  # True when |change| > 20%


@dataclass
class ComparisonResult:
    baseline: Baseline
    baseline_description: str  # Always shown explicitly in responses
    degraded_services: list[str]
    metric_deltas: list[MetricDelta]
    significant_changes: list[str]
    overall_degraded: bool


class BaselineService:
    """
    Selects the last-healthy baseline window and compares current metrics against it.

    Strategy precedence (caller chooses):
      1. user_pinned       – explicit window provided by the user
      2. last_healthy_window – most recent 1-hour window before the incident
                              with no alerts and low error rate
      3. last_stable_post_deploy – most recent window after a deploy that was stable
    """

    def __init__(self, db=None):
        self.db = db

    # ------------------------------------------------------------------
    # Public: strategy selector
    # ------------------------------------------------------------------

    async def select_baseline(
        self,
        investigation_id: str,
        strategy: BaselineStrategy,
        pinned_window_start: Optional[datetime] = None,
        pinned_window_end: Optional[datetime] = None,
        error_rate_threshold: float = 0.01,
    ) -> Optional[Baseline]:
        """Select a baseline window using the specified strategy."""
        if strategy == BaselineStrategy.user_pinned:
            return await self._user_pinned_baseline(
                pinned_window_start, pinned_window_end
            )
        elif strategy == BaselineStrategy.last_healthy_window:
            return await self._last_healthy_window(
                investigation_id, error_rate_threshold
            )
        elif strategy == BaselineStrategy.last_stable_post_deploy:
            return await self._last_stable_post_deploy(investigation_id)
        return None

    # ------------------------------------------------------------------
    # Private: strategy implementations
    # ------------------------------------------------------------------

    async def _last_healthy_window(
        self,
        investigation_id: str,
        error_rate_threshold: float = 0.01,
    ) -> Optional[Baseline]:
        """
        Scan backwards from incident start in 1-hour windows looking for the
        most recent window that had no alert evidence.
        """
        if not self.db:
            # Return a synthetic baseline for offline/test usage
            now = datetime.now(timezone.utc)
            return Baseline(
                strategy=BaselineStrategy.last_healthy_window,
                window_start=now - timedelta(hours=25),
                window_end=now - timedelta(hours=24),
                description="Last healthy window: 24-25 hours ago (synthetic - no DB)",
                error_rate=0.001,
                alert_count=0,
            )

        from sqlalchemy import select
        from app.models.all_models import Investigation, Evidence

        inv = await self.db.get(Investigation, investigation_id)
        if not inv:
            return None

        incident_start = inv.created_at or datetime.now(timezone.utc)
        if incident_start.tzinfo is None:
            incident_start = incident_start.replace(tzinfo=timezone.utc)

        # Scan backwards up to 7 days in 1-hour windows
        for hours_back in range(2, 168):
            window_end = incident_start - timedelta(hours=hours_back)
            window_start = window_end - timedelta(hours=1)

            # Check for alert-type evidence in this window
            result = await self.db.execute(
                select(Evidence).where(
                    Evidence.investigation_id == investigation_id,
                    Evidence.collected_at >= window_start,
                    Evidence.collected_at < window_end,
                )
            )
            evidence = result.scalars().all()

            # Filter for alert-sourced evidence (connectors that produce alert events)
            alert_evidence = [
                e for e in evidence
                if e.connector_id is not None
                or (e.label and any(
                    kw in (e.label or "").lower()
                    for kw in ("alert", "alarm", "error", "critical", "firing")
                ))
            ]

            if not alert_evidence:
                return Baseline(
                    strategy=BaselineStrategy.last_healthy_window,
                    window_start=window_start,
                    window_end=window_end,
                    description=(
                        f"Last healthy window: {hours_back}-{hours_back + 1} hours "
                        f"before incident start ({window_start.strftime('%Y-%m-%dT%H:%M')}Z "
                        f"to {window_end.strftime('%Y-%m-%dT%H:%M')}Z)"
                    ),
                    error_rate=0.0,
                    alert_count=0,
                )

        logger.warning(
            "no_healthy_window_found",
            investigation_id=investigation_id,
            hours_scanned=166,
        )
        return None

    async def _last_stable_post_deploy(
        self, investigation_id: str
    ) -> Optional[Baseline]:
        """
        Find the most recent 1-hour window that followed a deployment event
        without subsequent alert evidence.
        """
        if not self.db:
            now = datetime.now(timezone.utc)
            return Baseline(
                strategy=BaselineStrategy.last_stable_post_deploy,
                window_start=now - timedelta(hours=49),
                window_end=now - timedelta(hours=48),
                description="Last stable post-deployment window (synthetic - no DB)",
            )

        from sqlalchemy import select
        from app.models.all_models import Investigation, TimelineEvent, Evidence

        inv = await self.db.get(Investigation, investigation_id)
        if not inv:
            return None

        incident_start = inv.created_at or datetime.now(timezone.utc)
        if incident_start.tzinfo is None:
            incident_start = incident_start.replace(tzinfo=timezone.utc)

        # Look for deploy timeline events before the incident
        result = await self.db.execute(
            select(TimelineEvent).where(
                TimelineEvent.investigation_id == investigation_id,
                TimelineEvent.event_type == "deploy",
                TimelineEvent.occurred_at < incident_start,
            ).order_by(TimelineEvent.occurred_at.desc()).limit(10)
        )
        deploys = result.scalars().all()

        for deploy in deploys:
            deploy_time = deploy.occurred_at
            if deploy_time.tzinfo is None:
                deploy_time = deploy_time.replace(tzinfo=timezone.utc)

            # Stable window: 1-2 hours after deploy
            window_start = deploy_time + timedelta(hours=1)
            window_end = deploy_time + timedelta(hours=2)

            if window_end >= incident_start:
                continue  # Window overlaps with incident

            # Check no alert evidence in this window
            alert_result = await self.db.execute(
                select(Evidence).where(
                    Evidence.investigation_id == investigation_id,
                    Evidence.collected_at >= window_start,
                    Evidence.collected_at < window_end,
                    Evidence.label.ilike("%alert%"),
                )
            )
            alerts = alert_result.scalars().all()

            if not alerts:
                return Baseline(
                    strategy=BaselineStrategy.last_stable_post_deploy,
                    window_start=window_start,
                    window_end=window_end,
                    description=(
                        f"Last stable post-deploy window: "
                        f"{window_start.strftime('%Y-%m-%dT%H:%M')}Z to "
                        f"{window_end.strftime('%Y-%m-%dT%H:%M')}Z "
                        f"(after deploy at {deploy_time.strftime('%Y-%m-%dT%H:%M')}Z)"
                    ),
                )

        return None

    async def _user_pinned_baseline(
        self,
        window_start: Optional[datetime],
        window_end: Optional[datetime],
    ) -> Optional[Baseline]:
        """Return a user-specified baseline window."""
        if not window_start or not window_end:
            return None
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=timezone.utc)
        if window_end.tzinfo is None:
            window_end = window_end.replace(tzinfo=timezone.utc)
        return Baseline(
            strategy=BaselineStrategy.user_pinned,
            window_start=window_start,
            window_end=window_end,
            description=(
                f"User-pinned baseline: "
                f"{window_start.isoformat()} to {window_end.isoformat()}"
            ),
        )

    # ------------------------------------------------------------------
    # Public: comparison
    # ------------------------------------------------------------------

    async def compare_to_baseline(
        self,
        current_evidence: list[dict],
        baseline: Baseline,
    ) -> ComparisonResult:
        """
        Compare a list of current evidence dicts against a baseline.

        Each evidence dict is expected to have at least:
          - service (str)
          - severity (str: "error" | "critical" | ...)
        """
        degraded_services: list[str] = []
        metric_deltas: list[MetricDelta] = []
        significant_changes: list[str] = []

        # Group current items by service
        current_by_service: dict[str, list[dict]] = {}
        for item in current_evidence:
            svc = item.get("service", "unknown")
            current_by_service.setdefault(svc, []).append(item)

        for service, items in current_by_service.items():
            total = len(items)
            errors = sum(
                1 for i in items if i.get("severity") in ("error", "critical")
            )
            current_error_rate = errors / total if total > 0 else 0.0
            baseline_error_rate = baseline.error_rate

            change_pct = (
                (current_error_rate - baseline_error_rate)
                / max(baseline_error_rate, 0.001)
                * 100
            )
            is_significant = abs(change_pct) > 20

            delta = MetricDelta(
                metric_name="error_rate",
                service=service,
                baseline_value=baseline_error_rate,
                current_value=current_error_rate,
                change_pct=change_pct,
                is_significant=is_significant,
            )
            metric_deltas.append(delta)

            if is_significant and current_error_rate > baseline_error_rate:
                degraded_services.append(service)
                significant_changes.append(
                    f"{service}: error rate increased {change_pct:.1f}% "
                    f"(baseline {baseline_error_rate:.3f} -> current {current_error_rate:.3f})"
                )

        logger.info(
            "baseline_comparison_complete",
            baseline_strategy=baseline.strategy.value,
            degraded_services=degraded_services,
            total_services=len(current_by_service),
        )

        return ComparisonResult(
            baseline=baseline,
            baseline_description=baseline.description,  # Always shown explicitly
            degraded_services=degraded_services,
            metric_deltas=metric_deltas,
            significant_changes=significant_changes,
            overall_degraded=len(degraded_services) > 0,
        )
