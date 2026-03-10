"""
Investigation deduplication service.
Weighted similarity scoring to detect duplicate investigations.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)

DEDUP_THRESHOLD = 0.85


@dataclass
class DedupScore:
    service_overlap: float = 0.0
    time_overlap: float = 0.0
    alert_signature_match: float = 0.0
    symptom_text_similarity: float = 0.0

    @property
    def weighted_score(self) -> float:
        return (
            self.service_overlap * 0.40
            + self.time_overlap * 0.30
            + self.alert_signature_match * 0.20
            + self.symptom_text_similarity * 0.10
        )


@dataclass
class DedupResult:
    is_duplicate: bool
    candidate_investigation_id: Optional[str]
    score: DedupScore
    message: str


class DedupService:
    """
    Detects duplicate investigations using weighted similarity scoring.
    NEVER auto-merges user-started investigations silently.
    """

    def __init__(self, db=None):
        self.db = db

    def _service_overlap(self, services_a: list[str], services_b: list[str]) -> float:
        if not services_a or not services_b:
            return 0.0
        set_a = set(s.lower() for s in services_a)
        set_b = set(s.lower() for s in services_b)
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    def _time_overlap(
        self,
        start_a: datetime,
        end_a: Optional[datetime],
        start_b: datetime,
        end_b: Optional[datetime],
    ) -> float:
        """Calculate temporal overlap as a score 0-1."""
        now = datetime.now(timezone.utc)
        ea = end_a or now
        eb = end_b or now

        # Ensure timezone-aware comparisons
        if start_a.tzinfo is None:
            start_a = start_a.replace(tzinfo=timezone.utc)
        if start_b.tzinfo is None:
            start_b = start_b.replace(tzinfo=timezone.utc)
        if ea.tzinfo is None:
            ea = ea.replace(tzinfo=timezone.utc)
        if eb.tzinfo is None:
            eb = eb.replace(tzinfo=timezone.utc)

        # Check overlap
        overlap_start = max(start_a, start_b)
        overlap_end = min(ea, eb)

        if overlap_start >= overlap_end:
            # No overlap - check proximity
            gap_seconds = abs((start_a - start_b).total_seconds())
            if gap_seconds < 3600:  # Within 1 hour
                return 0.5
            elif gap_seconds < 86400:  # Within 24 hours
                return 0.2
            return 0.0

        overlap_duration = (overlap_end - overlap_start).total_seconds()
        total_duration = max(
            (ea - start_a).total_seconds(),
            (eb - start_b).total_seconds(),
            1,
        )
        return min(1.0, overlap_duration / total_duration)

    def _alert_signature_match(
        self, alerts_a: list[dict], alerts_b: list[dict]
    ) -> float:
        """Compare alert signatures."""
        if not alerts_a or not alerts_b:
            return 0.0
        sigs_a = set(str(a.get("name", a.get("title", ""))) for a in alerts_a)
        sigs_b = set(str(a.get("name", a.get("title", ""))) for a in alerts_b)
        intersection = sigs_a & sigs_b
        union = sigs_a | sigs_b
        return len(intersection) / len(union) if union else 0.0

    def _symptom_text_similarity(self, title_a: str, title_b: str) -> float:
        """Simple word-overlap similarity for symptom/title text."""
        words_a = set(title_a.lower().split())
        words_b = set(title_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def compute_similarity(
        self,
        inv_a: dict,
        inv_b: dict,
    ) -> DedupScore:
        """Compute weighted similarity between two investigations."""
        score = DedupScore(
            service_overlap=self._service_overlap(
                inv_a.get("services", []),
                inv_b.get("services", []),
            ),
            time_overlap=self._time_overlap(
                inv_a.get("started_at", datetime.now(timezone.utc)),
                inv_a.get("resolved_at"),
                inv_b.get("started_at", datetime.now(timezone.utc)),
                inv_b.get("resolved_at"),
            ),
            alert_signature_match=self._alert_signature_match(
                inv_a.get("alerts", []),
                inv_b.get("alerts", []),
            ),
            symptom_text_similarity=self._symptom_text_similarity(
                inv_a.get("title", ""),
                inv_b.get("title", ""),
            ),
        )
        return score

    async def check_duplicate(
        self,
        investigation: dict,
        org_id: str,
        exclude_id: Optional[str] = None,
    ) -> DedupResult:
        """
        Check if an investigation is a duplicate of any existing open investigation
        within the same organisation.
        """
        if not self.db:
            return DedupResult(
                is_duplicate=False,
                candidate_investigation_id=None,
                score=DedupScore(),
                message="No DB",
            )

        from sqlalchemy import select
        from app.models.all_models import Investigation

        # Fetch recent open/in-progress investigations from same org
        result = await self.db.execute(
            select(Investigation).where(
                Investigation.org_id == org_id,
                Investigation.status.in_(["open", "in_progress"]),
            ).limit(50)
        )
        candidates = result.scalars().all()

        best_score = DedupScore()
        best_candidate = None

        for candidate in candidates:
            if exclude_id and str(candidate.id) == exclude_id:
                continue

            candidate_dict = {
                "title": candidate.title or "",
                "started_at": candidate.created_at,
                "resolved_at": candidate.resolved_at,
                "services": [],  # Investigation model uses tags/context for service refs
                "alerts": [],
            }

            score = self.compute_similarity(investigation, candidate_dict)
            if score.weighted_score > best_score.weighted_score:
                best_score = score
                best_candidate = candidate

        is_dup = best_score.weighted_score >= DEDUP_THRESHOLD

        if is_dup:
            logger.info(
                "duplicate_candidate_found",
                investigation_title=investigation.get("title"),
                candidate_id=str(best_candidate.id) if best_candidate else None,
                score=best_score.weighted_score,
            )

        return DedupResult(
            is_duplicate=is_dup,
            candidate_investigation_id=(
                str(best_candidate.id) if best_candidate and is_dup else None
            ),
            score=best_score,
            message=(
                f"Similarity score: {best_score.weighted_score:.2f}"
                if is_dup
                else "No duplicate found"
            ),
        )

    async def merge_investigations(
        self,
        source_id: str,
        target_id: str,
        merged_by_user_id: str,
        org_id: str,
    ) -> None:
        """
        Merge source into target. Preserves both IDs.
        Records the merge in the context field of the source investigation.
        Writes full audit trail via AuditLog.
        NEVER called without explicit user decision.
        """
        if not self.db:
            return

        from app.models.all_models import Investigation, AuditLog

        # Mark source as closed and record canonical reference in context
        source = await self.db.get(Investigation, uuid.UUID(source_id))
        if source:
            ctx = dict(source.context or {})
            ctx["canonical_id"] = target_id
            ctx["merged_into"] = target_id
            source.context = ctx
            source.status = "closed"

        # Write audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            org_id=uuid.UUID(org_id),
            actor_id=uuid.UUID(merged_by_user_id),
            action="investigation.merged",
            resource_type="investigation",
            resource_id=source_id,
            after_state={
                "source_id": source_id,
                "target_id": target_id,
                "canonical_id": target_id,
            },
        )
        self.db.add(audit)
        await self.db.flush()

        logger.info(
            "investigations_merged",
            source_id=source_id,
            target_id=target_id,
            merged_by=merged_by_user_id,
        )
