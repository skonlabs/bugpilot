"""
GitHub connector for BugPilot.
Supports CODE_CHANGES (commits) and DEPLOYMENTS capabilities.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx
import structlog

from app.connectors.base import (
    BaseConnector,
    ConnectorCapability,
    RawEvidenceItem,
    ValidationResult,
)
from app.connectors.retry import async_retry

logger = structlog.get_logger(__name__)

_SUPPORTED_CAPABILITIES = [
    ConnectorCapability.CODE_CHANGES,
    ConnectorCapability.DEPLOYMENTS,
]

_REQUEST_TIMEOUT = 30.0
_GITHUB_API_BASE = "https://api.github.com"
_MAX_PAGES = 20  # Safety cap on pagination


def _to_iso8601(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_link_header(link_header: Optional[str]) -> Optional[str]:
    """
    Parse GitHub's Link header and return the 'next' URL if present.

    Example header value:
      <https://api.github.com/repos/...?page=2>; rel="next",
      <https://api.github.com/repos/...?page=5>; rel="last"
    """
    if not link_header:
        return None
    for part in link_header.split(","):
        part = part.strip()
        sections = part.split(";")
        if len(sections) < 2:
            continue
        url = sections[0].strip().strip("<>")
        rel = sections[1].strip()
        if rel == 'rel="next"':
            return url
    return None


class GitHubConnector(BaseConnector):
    """
    Connector for the GitHub API.

    Supports:
    - CODE_CHANGES  via GET /repos/:owner/:repo/commits (with since/until)
    - DEPLOYMENTS   via GET /repos/:owner/:repo/deployments (with created filter)

    If `org` and `repo` are not provided at construction time, they must be
    derivable from the `service` string passed to `fetch_evidence` in the
    format "org/repo". Falls back to listing repos for the authenticated user.
    """

    def __init__(
        self,
        token: str,
        org: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> None:
        self._token = token
        self._org = org
        self._repo = repo
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def capabilities(self) -> list[ConnectorCapability]:
        return list(_SUPPORTED_CAPABILITIES)

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def validate(self) -> ValidationResult:
        """Validate token via GET /user (or /app for GitHub App tokens)."""
        start = time.monotonic()
        for endpoint in ("/user", "/app"):
            try:
                async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                    resp = await client.get(
                        f"{_GITHUB_API_BASE}{endpoint}",
                        headers=self._headers,
                    )
                latency_ms = (time.monotonic() - start) * 1000
                if resp.status_code == 200:
                    return ValidationResult(is_valid=True, latency_ms=latency_ms)
                if resp.status_code not in (401, 403):
                    # Unexpected error - try next endpoint
                    continue
                # 401/403 from /user usually means it's an app token - try /app
                if endpoint == "/app":
                    return ValidationResult(
                        is_valid=False,
                        error=f"Authentication failed: HTTP {resp.status_code}",
                        latency_ms=latency_ms,
                    )
            except Exception as exc:
                latency_ms = (time.monotonic() - start) * 1000
                logger.error("github_validate_error", error=str(exc))
                return ValidationResult(is_valid=False, error=str(exc), latency_ms=latency_ms)
        latency_ms = (time.monotonic() - start) * 1000
        return ValidationResult(
            is_valid=False, error="Could not validate with /user or /app", latency_ms=latency_ms
        )

    async def fetch_evidence(
        self,
        capability: ConnectorCapability,
        service: str,
        since: datetime,
        until: datetime,
        limit: int = 500,
    ) -> list[RawEvidenceItem]:
        if capability == ConnectorCapability.CODE_CHANGES:
            return await self._fetch_commits(service, since, until, limit)
        elif capability == ConnectorCapability.DEPLOYMENTS:
            return await self._fetch_deployments(service, since, until, limit)
        else:
            logger.warning("github_unsupported_capability", capability=capability.value)
            return []

    # ------------------------------------------------------------------
    # Helper: resolve owner/repo from service string
    # ------------------------------------------------------------------

    def _resolve_owner_repo(self, service: str) -> tuple[str, str]:
        """
        Return (owner, repo) tuple.

        Priority:
        1. Constructor-level org + repo
        2. service string formatted as "owner/repo"
        3. Fall back to org/service or service/service
        """
        if self._org and self._repo:
            return self._org, self._repo
        if "/" in service:
            parts = service.split("/", 1)
            return parts[0], parts[1]
        if self._org:
            return self._org, service
        return service, service

    # ------------------------------------------------------------------
    # Paginated GET helper
    # ------------------------------------------------------------------

    async def _paginated_get(
        self, url: str, params: dict[str, Any], limit: int
    ) -> list[dict[str, Any]]:
        """Fetch all pages up to `limit` items, following Link: next headers."""
        items: list[dict[str, Any]] = []
        page_count = 0
        current_url: Optional[str] = url

        while current_url and len(items) < limit and page_count < _MAX_PAGES:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    current_url,
                    headers=self._headers,
                    params=params if page_count == 0 else None,
                )
            resp.raise_for_status()
            page_items = resp.json()
            if not isinstance(page_items, list):
                break
            items.extend(page_items)
            page_count += 1
            current_url = _parse_link_header(resp.headers.get("Link"))

        return items[:limit]

    # ------------------------------------------------------------------
    # Private fetch methods
    # ------------------------------------------------------------------

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_commits(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """Fetch commits via GET /repos/:owner/:repo/commits."""
        owner, repo = self._resolve_owner_repo(service)
        params: dict[str, Any] = {
            "since": _to_iso8601(since),
            "until": _to_iso8601(until),
            "per_page": min(100, limit),
        }
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
        try:
            commits = await self._paginated_get(url, params, limit)
            items: list[RawEvidenceItem] = []
            for commit in commits:
                commit_data = commit.get("commit", {})
                ts_str = (
                    commit_data.get("committer", {}).get("date")
                    or commit_data.get("author", {}).get("date")
                    or since.isoformat()
                )
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = since
                message = commit_data.get("message", "")
                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.CODE_CHANGES,
                        source_system="github",
                        service=service,
                        timestamp=ts,
                        payload=commit,
                        message=message.splitlines()[0] if message else None,
                        raw_ref=commit.get("sha"),
                        metadata={
                            "author": commit_data.get("author", {}).get("name"),
                            "committer": commit_data.get("committer", {}).get("name"),
                            "url": commit.get("html_url"),
                            "owner": owner,
                            "repo": repo,
                        },
                    )
                )
            logger.info("github_commits_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "github_commits_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("github_commits_error", service=service, error=str(exc))
            return []

    @async_retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def _fetch_deployments(
        self, service: str, since: datetime, until: datetime, limit: int
    ) -> list[RawEvidenceItem]:
        """
        Fetch deployments via GET /repos/:owner/:repo/deployments.

        GitHub's deployments API does not natively support a 'since/until' filter,
        so we fetch up to `limit` recent deployments and filter client-side by
        `created_at` timestamp.
        """
        owner, repo = self._resolve_owner_repo(service)
        params: dict[str, Any] = {
            "per_page": min(100, limit),
        }
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/deployments"
        try:
            deployments = await self._paginated_get(url, params, limit * 2)
            items: list[RawEvidenceItem] = []
            for deployment in deployments:
                created_at_str = deployment.get("created_at") or deployment.get("updated_at", "")
                try:
                    ts = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = since

                # Client-side time range filtering
                if ts.replace(tzinfo=timezone.utc) < since.replace(tzinfo=timezone.utc):
                    continue
                if ts.replace(tzinfo=timezone.utc) > until.replace(tzinfo=timezone.utc):
                    continue

                items.append(
                    RawEvidenceItem(
                        capability=ConnectorCapability.DEPLOYMENTS,
                        source_system="github",
                        service=service,
                        timestamp=ts,
                        payload=deployment,
                        message=(
                            f"Deploy {deployment.get('ref', '')} "
                            f"to {deployment.get('environment', 'unknown')}"
                        ),
                        raw_ref=str(deployment.get("id", "")),
                        metadata={
                            "environment": deployment.get("environment"),
                            "ref": deployment.get("ref"),
                            "sha": deployment.get("sha"),
                            "creator": deployment.get("creator", {}).get("login"),
                            "owner": owner,
                            "repo": repo,
                        },
                    )
                )
                if len(items) >= limit:
                    break

            logger.info("github_deployments_fetched", service=service, count=len(items))
            return items
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "github_deployments_http_error",
                service=service,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("github_deployments_error", service=service, error=str(exc))
            return []


__all__ = ["GitHubConnector"]
