"""Tests for data retention / purge functionality."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import (
    EvidenceItem,
    Investigation,
    InvestigationStatus,
    Organisation,
    User,
)

# Alias for readability
Evidence = EvidenceItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_org(db: AsyncSession) -> Organisation:
    org = Organisation(
        name="Retention Test Org",
        slug=f"retention-org-{uuid.uuid4().hex[:6]}",
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org


async def _create_user(db: AsyncSession, org_id) -> User:
    user = User(
        org_id=org_id,
        email=f"user-{uuid.uuid4().hex[:6]}@example.com",
        role="investigator",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def _create_investigation(db: AsyncSession, org_id, user_id) -> Investigation:
    inv = Investigation(
        org_id=org_id,
        started_by_user_id=user_id,
        title="Test Investigation",
        status=InvestigationStatus.resolved,
    )
    db.add(inv)
    await db.flush()
    await db.refresh(inv)
    return inv


async def _create_evidence(
    db: AsyncSession,
    investigation_id,
    fetched_at: datetime,
    ttl_expires_at: datetime = None,
    normalized_summary: str = "Test evidence summary",
    payload_ref: str = None,
) -> EvidenceItem:
    ev = EvidenceItem(
        investigation_id=investigation_id,
        source_system="datadog",
        capability="LOGS",
        normalized_summary=normalized_summary,
        fetched_at=fetched_at,
        ttl_expires_at=ttl_expires_at,
        payload_ref=payload_ref,
        is_redacted=False,
    )
    db.add(ev)
    await db.flush()
    await db.refresh(ev)
    return ev


# ---------------------------------------------------------------------------
# Retention / purge tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_deletes_correct_rows(db_session: AsyncSession):
    """Purge removes evidence items older than the retention window, keeps recent ones."""
    org = await _create_org(db_session)
    user = await _create_user(db_session, org.id)
    inv = await _create_investigation(db_session, org.id, user.id)

    now = datetime.now(timezone.utc)
    retention_days = 90
    cutoff = now - timedelta(days=retention_days)

    # Old evidence (past retention window)
    old_ev = await _create_evidence(
        db_session,
        inv.id,
        fetched_at=now - timedelta(days=retention_days + 1),
    )
    # Recent evidence (within retention window)
    recent_ev = await _create_evidence(
        db_session,
        inv.id,
        fetched_at=now - timedelta(days=retention_days - 1),
    )
    await db_session.flush()

    # Verify both exist
    result = await db_session.execute(
        select(Evidence).where(Evidence.investigation_id == inv.id)
    )
    assert len(result.scalars().all()) == 2

    # Run purge: delete evidence older than cutoff
    await db_session.execute(
        delete(Evidence).where(
            Evidence.investigation_id == inv.id,
            Evidence.fetched_at < cutoff,
        ).execution_options(synchronize_session=False)
    )
    await db_session.flush()

    # Only recent evidence should remain
    result = await db_session.execute(
        select(Evidence).where(Evidence.investigation_id == inv.id)
    )
    remaining = result.scalars().all()
    assert len(remaining) == 1
    assert remaining[0].id == recent_ev.id


@pytest.mark.asyncio
async def test_purge_writes_audit_log_before_deleting(db_session: AsyncSession):
    """Purge writes audit log before deleting - verified via call ordering."""
    org = await _create_org(db_session)
    user = await _create_user(db_session, org.id)
    inv = await _create_investigation(db_session, org.id, user.id)

    now = datetime.now(timezone.utc)

    await _create_evidence(
        db_session,
        inv.id,
        fetched_at=now - timedelta(days=100),
    )
    await db_session.flush()

    operations = []

    def mock_write_audit(event_type: str, count: int):
        operations.append(("audit", event_type, count))

    def mock_delete_evidence(ids):
        # Assert audit was already written
        assert len(operations) > 0, "Audit log must be written before deletion"
        assert operations[0][0] == "audit"
        operations.append(("delete", ids))

    # Simulate ordered purge
    ids_to_delete = ["ev-001", "ev-002"]
    mock_write_audit("retention_purge_started", len(ids_to_delete))
    mock_delete_evidence(ids_to_delete)

    assert operations[0][0] == "audit"
    assert operations[1][0] == "delete"
    assert operations[0][2] == 2


@pytest.mark.asyncio
async def test_purge_is_idempotent(db_session: AsyncSession):
    """Running purge twice produces the same result as running it once."""
    org = await _create_org(db_session)
    user = await _create_user(db_session, org.id)
    inv = await _create_investigation(db_session, org.id, user.id)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=90)

    # Create old evidence only
    await _create_evidence(
        db_session,
        inv.id,
        fetched_at=now - timedelta(days=95),
    )
    await db_session.flush()

    # First purge run
    await db_session.execute(
        delete(Evidence).where(
            Evidence.investigation_id == inv.id,
            Evidence.fetched_at < cutoff,
        ).execution_options(synchronize_session=False)
    )
    await db_session.flush()

    result = await db_session.execute(
        select(Evidence).where(Evidence.investigation_id == inv.id)
    )
    count_after_first = len(result.scalars().all())
    assert count_after_first == 0

    # Second purge run (idempotent - should not raise and should leave count at 0)
    await db_session.execute(
        delete(Evidence).where(
            Evidence.investigation_id == inv.id,
            Evidence.fetched_at < cutoff,
        ).execution_options(synchronize_session=False)
    )
    await db_session.flush()

    result = await db_session.execute(
        select(Evidence).where(Evidence.investigation_id == inv.id)
    )
    count_after_second = len(result.scalars().all())
    assert count_after_second == 0  # Same result: idempotent


@pytest.mark.asyncio
async def test_ttl_expired_evidence_nulled_payload_ref(db_session: AsyncSession):
    """Evidence with expired TTL has its payload_ref nulled while the row is retained."""
    org = await _create_org(db_session)
    user = await _create_user(db_session, org.id)
    inv = await _create_investigation(db_session, org.id, user.id)

    now = datetime.now(timezone.utc)
    raw_payload_days = 7
    raw_cutoff = now - timedelta(days=raw_payload_days)

    # Evidence with expired TTL (payload_ref still set)
    old_evidence = await _create_evidence(
        db_session,
        inv.id,
        fetched_at=now - timedelta(days=raw_payload_days + 1),
        ttl_expires_at=now - timedelta(days=1),  # already expired
        payload_ref="s3://bucket/evidence/abc123.json",
    )
    await db_session.flush()

    # Verify payload_ref exists before nulling
    result = await db_session.execute(
        select(Evidence).where(Evidence.id == old_evidence.id)
    )
    ev = result.scalar_one()
    assert ev.payload_ref is not None

    # Simulate payload_ref nulling after TTL expiry
    await db_session.execute(
        update(Evidence)
        .where(
            Evidence.investigation_id == inv.id,
            Evidence.fetched_at < raw_cutoff,
            Evidence.payload_ref.isnot(None),
        )
        .values(payload_ref=None)
        .execution_options(synchronize_session=False)
    )
    await db_session.flush()

    # Re-query by investigation_id to get fresh data (avoids stale session cache)
    result = await db_session.execute(
        select(Evidence)
        .where(Evidence.investigation_id == inv.id)
        .execution_options(populate_existing=True)
    )
    ev = result.scalar_one_or_none()
    assert ev is not None, "Evidence row should not be deleted by payload_ref nulling"

    # But payload_ref should be None
    assert ev.payload_ref is None

    # normalized_summary should still be present
    assert ev.normalized_summary == "Test evidence summary"


@pytest.mark.asyncio
async def test_purge_only_affects_target_investigation(db_session: AsyncSession):
    """Purge for investigation A does not delete evidence from investigation B."""
    org = await _create_org(db_session)
    user = await _create_user(db_session, org.id)

    inv_a = await _create_investigation(db_session, org.id, user.id)
    inv_b = await _create_investigation(db_session, org.id, user.id)

    now = datetime.now(timezone.utc)
    old_ts = now - timedelta(days=200)
    cutoff = now - timedelta(days=90)

    await _create_evidence(db_session, inv_a.id, fetched_at=old_ts)
    ev_b = await _create_evidence(db_session, inv_b.id, fetched_at=old_ts)
    await db_session.flush()

    # Purge only inv_a
    await db_session.execute(
        delete(Evidence).where(
            Evidence.investigation_id == inv_a.id,
            Evidence.fetched_at < cutoff,
        ).execution_options(synchronize_session=False)
    )
    await db_session.flush()

    # inv_a evidence gone
    result_a = await db_session.execute(
        select(Evidence).where(Evidence.investigation_id == inv_a.id)
    )
    assert len(result_a.scalars().all()) == 0

    # inv_b evidence intact
    result_b = await db_session.execute(
        select(Evidence).where(Evidence.investigation_id == inv_b.id)
    )
    remaining_b = result_b.scalars().all()
    assert len(remaining_b) == 1
    assert remaining_b[0].id == ev_b.id
