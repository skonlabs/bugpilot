"""
Backend test configuration and fixtures.
"""
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.connectors.base import BaseConnector, ConnectorCapability, RawEvidenceItem, ValidationResult
from app.core.db import Base, get_db
from app.core.security import create_session_token
from app.main import app
from app.models.all_models import (
    Investigation,
    InvestigationStatus,
    License,
    LicenseStatus,
    Organisation,
    Session,
    User,
)

# Use an in-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test database session."""
    AsyncTestSession = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with AsyncTestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide a test HTTP client with overridden database dependency."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# Keep backward-compatible alias
@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide a test HTTP client with overridden database dependency (alias for async_client)."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_org(db_session: AsyncSession) -> Organisation:
    """Creates a test organisation."""
    org = Organisation(
        name="Test Organisation",
        slug="test-org",
    )
    db_session.add(org)
    await db_session.flush()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_org: Organisation) -> User:
    """Creates a test user with investigator role."""
    user = User(
        org_id=test_org.id,
        email="investigator@test.example.com",
        role="investigator",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_license(db_session: AsyncSession, test_org: Organisation) -> License:
    """Creates a test license for the test organisation."""
    raw_key = "TEST-LICENSE-KEY-0001-ABCDEFGH"
    api_key = f"bp_{raw_key}"
    hashed_secret = hashlib.sha256(raw_key.encode()).hexdigest()
    license_obj = License(
        org_id=test_org.id,
        api_key=api_key,
        hashed_secret=hashed_secret,
        status=LicenseStatus.active,
        max_devices=5,
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
    )
    # Store the raw key on the object for test use
    license_obj._raw_key = raw_key  # type: ignore[attr-defined]
    db_session.add(license_obj)
    await db_session.flush()
    await db_session.refresh(license_obj)
    return license_obj


@pytest.fixture
def sample_org_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def auth_headers(sample_user_id: str, sample_org_id: str) -> dict:
    """Generate valid JWT headers for test requests (admin role)."""
    jwt_token, _, _, _ = create_session_token(
        user_id=sample_user_id,
        org_id=sample_org_id,
        device_fp="test-device-fp",
        role="admin",
    )
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest_asyncio.fixture
async def auth_headers_for_user(test_user: User, test_org: Organisation) -> dict:
    """Generate valid JWT headers for the test_user fixture."""
    jwt_token, _, _, _ = create_session_token(
        user_id=str(test_user.id),
        org_id=str(test_org.id),
        device_fp="test-device-fp",
        role=test_user.role,
    )
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest_asyncio.fixture
async def test_investigation(
    db_session: AsyncSession,
    test_org: Organisation,
    test_user: User,
) -> Investigation:
    """Creates a test investigation."""
    investigation = Investigation(
        org_id=test_org.id,
        started_by_user_id=test_user.id,
        title="High error rate on payment-service",
        status=InvestigationStatus.open,
        linked_services=["payment-service"],
    )
    db_session.add(investigation)
    await db_session.flush()
    await db_session.refresh(investigation)
    return investigation


@pytest.fixture
def mock_connector() -> BaseConnector:
    """A mock BaseConnector for testing."""

    class MockConnector(BaseConnector):
        def __init__(self):
            self._capabilities = [
                ConnectorCapability.LOGS,
                ConnectorCapability.METRICS,
            ]
            self.fetch_called_with = []
            self.validate_result = ValidationResult(is_valid=True, latency_ms=42.0)
            self.should_raise = None
            self.fetch_result = []

        def capabilities(self) -> list[ConnectorCapability]:
            return list(self._capabilities)

        async def validate(self) -> ValidationResult:
            if self.should_raise:
                raise self.should_raise
            return self.validate_result

        async def fetch_evidence(
            self,
            capability: ConnectorCapability,
            service: str,
            since: datetime,
            until: datetime,
            limit: int = 500,
        ) -> list[RawEvidenceItem]:
            self.fetch_called_with.append(
                {"capability": capability, "service": service, "since": since, "until": until}
            )
            if self.should_raise:
                raise self.should_raise
            return list(self.fetch_result)

    return MockConnector()
