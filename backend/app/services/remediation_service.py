"""
Remediation candidate generation and approval flow.

Approval rules:
  - low / safe risk  : no approval required
  - medium risk      : requires approver role
  - high / critical  : requires approver role
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class RiskLevel(str, Enum):
    safe = "safe"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ActionStatus(str, Enum):
    pending = "pending"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


@dataclass
class ActionCandidate:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hypothesis_id: str = ""
    description: str = ""
    rationale: str = ""
    expected_effect: str = ""
    risk_level: RiskLevel = RiskLevel.low
    rollback_path: str = ""
    dry_run_command: Optional[str] = None
    requires_approval: bool = False


@dataclass
class DryRunResult:
    action_id: str
    predicted_changes: list[str]
    estimated_impact: str
    is_safe: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class ActionResult:
    action_id: str
    status: ActionStatus
    output: str
    completed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    error: Optional[str] = None


class RemediationService:
    """
    Generates remediation action candidates from hypotheses and manages the
    human-in-the-loop approval flow before execution.
    """

    def __init__(self, db=None):
        self.db = db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _requires_approval(self, risk_level: RiskLevel) -> bool:
        """Return True for any risk level that demands an explicit human approval."""
        return risk_level in (RiskLevel.medium, RiskLevel.high, RiskLevel.critical)

    # ------------------------------------------------------------------
    # Candidate generation
    # ------------------------------------------------------------------

    async def generate_candidates(
        self,
        hypothesis_id: str,
        investigation_id: str,
    ) -> list[ActionCandidate]:
        """Generate remediation candidates for a given hypothesis."""
        if not self.db:
            return self._rule_based_candidates(hypothesis_id, {})

        from app.models.all_models import Hypothesis

        hyp = await self.db.get(Hypothesis, uuid.UUID(hypothesis_id))
        if not hyp:
            return []

        hyp_data = {
            "title": hyp.title or "",
            "description": hyp.description or "",
            "confidence_score": hyp.confidence_score,
        }
        return self._rule_based_candidates(hypothesis_id, hyp_data)

    def _rule_based_candidates(
        self,
        hypothesis_id: str,
        hypothesis: dict,
    ) -> list[ActionCandidate]:
        """
        Map well-known hypothesis patterns to concrete action candidates.
        Returns a generic diagnostic action when no pattern matches.
        """
        title = hypothesis.get("title", "").lower()
        candidates: list[ActionCandidate] = []

        # ---- Memory / OOM ----
        if "memory" in title or "oom" in title or "heap" in title:
            candidates.extend([
                ActionCandidate(
                    hypothesis_id=hypothesis_id,
                    description="Increase memory limits for affected pods",
                    rationale=(
                        "Memory exhaustion hypothesis — increasing limits provides "
                        "immediate relief while root-cause investigation continues."
                    ),
                    expected_effect="Prevents OOMKill events; pods remain stable",
                    risk_level=RiskLevel.low,
                    rollback_path=(
                        "Revert deployment: kubectl rollout undo deployment/<name>"
                    ),
                    dry_run_command=(
                        "kubectl patch deployment <name> --dry-run=client "
                        "-p '{\"spec\":{\"template\":{\"spec\":{\"containers\":"
                        "[{\"name\":\"<container>\",\"resources\":{\"limits\":"
                        "{\"memory\":\"512Mi\"}}}}]}}}'"
                    ),
                    requires_approval=False,
                ),
                ActionCandidate(
                    hypothesis_id=hypothesis_id,
                    description="Rolling restart of affected pods to clear memory leak",
                    rationale=(
                        "Forces garbage collection and releases accumulated memory. "
                        "Temporary fix — may recur without a code fix."
                    ),
                    expected_effect=(
                        "Immediate memory reduction; service briefly disrupted "
                        "during rollout (one pod at a time)"
                    ),
                    risk_level=RiskLevel.medium,
                    rollback_path=(
                        "Pods restart automatically if health checks fail. "
                        "Re-deploy previous image if needed."
                    ),
                    dry_run_command=(
                        "kubectl rollout restart deployment/<name> --dry-run=client"
                    ),
                    requires_approval=True,
                ),
            ])

        # ---- Deployment regression ----
        if "deployment" in title or "regression" in title or "rollback" in title:
            candidates.extend([
                ActionCandidate(
                    hypothesis_id=hypothesis_id,
                    description="Roll back to the previous deployment version",
                    rationale=(
                        "Deployment-correlated regression detected — rollback is the "
                        "fastest recovery path and eliminates the bad version immediately."
                    ),
                    expected_effect=(
                        "Restores previous working state and eliminates the regression; "
                        "minimal downtime during rollout."
                    ),
                    risk_level=RiskLevel.high,
                    rollback_path=(
                        "This action IS the rollback. To undo: redeploy the current "
                        "version once fixed."
                    ),
                    dry_run_command=(
                        "kubectl rollout undo deployment/<name> --dry-run=client"
                    ),
                    requires_approval=True,
                ),
            ])

        # ---- Latency / dependency ----
        if "latency" in title or "timeout" in title or "dependency" in title or "slow" in title:
            candidates.extend([
                ActionCandidate(
                    hypothesis_id=hypothesis_id,
                    description="Increase circuit breaker timeout thresholds",
                    rationale=(
                        "Downstream latency is causing cascading timeouts. Increasing "
                        "thresholds buys time for the upstream service to recover."
                    ),
                    expected_effect=(
                        "Reduces cascading failures; downstream service has more time "
                        "to respond before the circuit opens."
                    ),
                    risk_level=RiskLevel.low,
                    rollback_path="Revert the timeout configuration change.",
                    requires_approval=False,
                ),
                ActionCandidate(
                    hypothesis_id=hypothesis_id,
                    description="Enable read-replica failover for database connections",
                    rationale=(
                        "If the primary database is the bottleneck, routing reads to a "
                        "replica reduces load by 40-60% for read-heavy services."
                    ),
                    expected_effect=(
                        "Primary DB load reduced; read queries served from replica. "
                        "Slight replication lag may be observed."
                    ),
                    risk_level=RiskLevel.medium,
                    rollback_path=(
                        "Revert database connection string back to the primary host."
                    ),
                    requires_approval=True,
                ),
            ])

        # ---- High error rate / 5xx ----
        if "error rate" in title or "5xx" in title or "exception" in title:
            candidates.extend([
                ActionCandidate(
                    hypothesis_id=hypothesis_id,
                    description="Scale up the affected service horizontally",
                    rationale=(
                        "High error rate may indicate resource saturation. Additional "
                        "replicas distribute load and reduce per-instance error rates."
                    ),
                    expected_effect=(
                        "Increased request capacity; error rate should drop as load is "
                        "spread across more instances."
                    ),
                    risk_level=RiskLevel.low,
                    rollback_path=(
                        "Scale back down: kubectl scale deployment/<name> --replicas=<prev>"
                    ),
                    dry_run_command=(
                        "kubectl scale deployment/<name> --replicas=<n> --dry-run=client"
                    ),
                    requires_approval=False,
                ),
            ])

        # ---- Disk / storage ----
        if "disk" in title or "storage" in title or "iops" in title:
            candidates.append(
                ActionCandidate(
                    hypothesis_id=hypothesis_id,
                    description="Purge old log files and temporary artefacts",
                    rationale=(
                        "Disk exhaustion prevents writes. Clearing stale logs frees "
                        "space immediately without service disruption."
                    ),
                    expected_effect="Disk utilisation drops; write errors cease.",
                    risk_level=RiskLevel.low,
                    rollback_path="N/A — deletes only rotated/temp files.",
                    requires_approval=False,
                )
            )

        # ---- Fallback: generic diagnostic ----
        if not candidates:
            candidates.append(
                ActionCandidate(
                    hypothesis_id=hypothesis_id,
                    description="Collect additional diagnostic information",
                    rationale=(
                        "Current evidence is insufficient for targeted remediation. "
                        "Gathering more data will clarify the root cause."
                    ),
                    expected_effect=(
                        "Provides a clearer picture of the root cause for follow-up "
                        "targeted remediation."
                    ),
                    risk_level=RiskLevel.low,
                    rollback_path="N/A — read-only operation.",
                    requires_approval=False,
                )
            )

        return candidates

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------

    async def dry_run(self, action_id: str) -> DryRunResult:
        """Simulate an action without side effects and return predicted changes."""
        if not self.db:
            return DryRunResult(
                action_id=action_id,
                predicted_changes=[
                    "[Simulation] No DB available — cannot determine exact changes"
                ],
                estimated_impact="Unknown",
                is_safe=True,
                warnings=["Connect to database for accurate dry-run simulation"],
            )

        from app.models.all_models import Action

        action = await self.db.get(Action, uuid.UUID(action_id))
        if not action:
            return DryRunResult(
                action_id=action_id,
                predicted_changes=[],
                estimated_impact="Action not found",
                is_safe=False,
                warnings=["No action found with this ID"],
            )

        risk = RiskLevel(action.risk_level.value) if action.risk_level else RiskLevel.low
        warnings: list[str] = []

        if risk == RiskLevel.critical:
            warnings.append(
                "CRITICAL risk action — execution may cause irreversible changes. "
                "Requires explicit approval."
            )
        elif risk == RiskLevel.high:
            warnings.append(
                "HIGH risk action — review rollback plan carefully before approving."
            )
        elif risk == RiskLevel.medium:
            warnings.append("MEDIUM risk action — approval required before execution.")

        return DryRunResult(
            action_id=action_id,
            predicted_changes=[
                f"[Simulated] {action.description or action.title}",
                f"Expected effect: {action.rollback_plan or 'See action description'}",
            ],
            estimated_impact=f"Risk level: {risk.value}",
            is_safe=risk not in (RiskLevel.critical,),
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Approval flow
    # ------------------------------------------------------------------

    async def approve_action(
        self,
        action_id: str,
        approver_user_id: str,
        decision: str,  # "approved" | "rejected"
        note: str,
        org_id: str,
    ) -> None:
        """Record an approval or rejection decision and write an audit trail."""
        if not self.db:
            return

        from app.models.all_models import Action, AuditLog
        from app.models.all_models import ActionStatus as DBActionStatus

        action = await self.db.get(Action, uuid.UUID(action_id))
        if action:
            action.status = (
                DBActionStatus.approved if decision == "approved" else DBActionStatus.cancelled
            )
            if decision == "approved":
                action.approved_by = uuid.UUID(approver_user_id)
                action.approved_at = datetime.now(timezone.utc)

        audit = AuditLog(
            id=uuid.uuid4(),
            org_id=uuid.UUID(org_id),
            actor_id=uuid.UUID(approver_user_id),
            action=f"action.{decision}",
            resource_type="action",
            resource_id=action_id,
            after_state={"decision": decision, "note": note},
        )
        self.db.add(audit)
        await self.db.flush()

        logger.info(
            "action_approval",
            action_id=action_id,
            decision=decision,
            approver=approver_user_id,
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_action(
        self,
        action_id: str,
        executed_by_user_id: str,
        org_id: str,
    ) -> ActionResult:
        """
        Execute an action. Enforces approval gate for medium/high/critical risk.
        For MVP the actual execution is stubbed — the audit trail is real.
        """
        if not self.db:
            return ActionResult(
                action_id=action_id,
                status=ActionStatus.failed,
                output="",
                error="No database connection",
            )

        from sqlalchemy import select
        from app.models.all_models import Action, AuditLog
        from app.models.all_models import ActionStatus as DBActionStatus
        from app.models.all_models import ActionRiskLevel

        action = await self.db.get(Action, uuid.UUID(action_id))
        if not action:
            return ActionResult(
                action_id=action_id,
                status=ActionStatus.failed,
                output="",
                error="Action not found",
            )

        risk = RiskLevel(action.risk_level.value) if action.risk_level else RiskLevel.low

        # Enforce approval gate
        if self._requires_approval(risk):
            if action.status != DBActionStatus.approved:
                return ActionResult(
                    action_id=action_id,
                    status=ActionStatus.pending_approval,
                    output="",
                    error=(
                        f"Action requires approval (risk: {risk.value}). "
                        f"Use 'bugpilot fix approve {action_id}'."
                    ),
                )

        # Mark as running
        action.status = DBActionStatus.running
        await self.db.flush()

        # Write pre-execution audit log
        audit_start = AuditLog(
            id=uuid.uuid4(),
            org_id=uuid.UUID(org_id),
            actor_id=uuid.UUID(executed_by_user_id),
            action="action.run",
            resource_type="action",
            resource_id=action_id,
            before_state={"status": "approved"},
            after_state={
                "status": "running",
                "risk_level": risk.value,
                "description": action.description or action.title,
            },
        )
        self.db.add(audit_start)

        # MVP: record as completed (actual execution out of scope)
        action.status = DBActionStatus.completed
        action.executed_by = uuid.UUID(executed_by_user_id)
        action.executed_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "action_run",
            action_id=action_id,
            run_by=executed_by_user_id,
            risk=risk.value,
        )

        return ActionResult(
            action_id=action_id,
            status=ActionStatus.completed,
            output=(
                f"Action '{action.description or action.title}' recorded as executed.\n"
                f"Risk level: {risk.value}\n"
                f"Rollback plan: {action.rollback_plan or 'N/A'}"
            ),
        )
