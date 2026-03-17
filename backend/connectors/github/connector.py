"""
GitHub connector — fetches merged PRs and their diffs for hypothesis ranking.

Config keys:
  token           — Personal Access Token (recommended: fine-grained or classic)
  org             — GitHub org or user login (optional with PAT; required for App auth)
  repos           — list of repo full names or short names to include (empty = all accessible)
  app_id          — GitHub App ID  (alternative to token)
  private_key     — GitHub App private key (PEM string)
  installation_id — GitHub App installation ID (auto-discovered from org if omitted)

UES event types emitted: code_change
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.connectors._base.connector_base import ConnectorBase, ConnectorData, ConnectorHealth
from backend.connectors._base.normaliser_base import NormaliserBase, utcnow_iso

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubNormaliser(NormaliserBase):
    def to_ues(self, raw: dict) -> dict:
        event = self._base_event(
            event_type="code_change",
            source="github",
            source_id=str(raw.get("number", "")),
        )
        event.update({
            "timestamp": raw.get("merged_at") or raw.get("created_at") or utcnow_iso(),
            "pr_id": raw.get("number"),
            "pr_title": raw.get("title", ""),
            "pr_url": raw.get("html_url", ""),
            "pr_author": raw.get("user", {}).get("login", ""),
            "pr_merged_at": raw.get("merged_at"),
            "base_branch": raw.get("base", {}).get("ref", ""),
            "head_branch": raw.get("head", {}).get("ref", ""),
            "additions": raw.get("additions", 0),
            "deletions": raw.get("deletions", 0),
            "changed_files": raw.get("changed_files", 0),
            "files": raw.get("_files", []),   # enriched by fetch()
            "repo": raw.get("_repo", ""),
            "labels": [label["name"] for label in raw.get("labels", [])],
        })
        return event


class GitHubConnector(ConnectorBase):
    connector_type = "github"
    rate_limit_rpm = 30

    def validate_config(self) -> None:
        has_app = self._config.get("app_id") and self._config.get("private_key")
        has_token = self._config.get("token")
        if not has_app and not has_token:
            raise ValueError(
                "GitHub connector requires either a Personal Access Token ('token') "
                "or GitHub App credentials ('app_id' + 'private_key')"
            )
        if has_app and not self._config.get("org"):
            raise ValueError("GitHub App auth requires the 'org' field")

    def health_check(self) -> ConnectorHealth:
        try:
            resp = self._client().get(f"{GITHUB_API}/user")
            resp.raise_for_status()
            user = resp.json()
            return ConnectorHealth(
                status="ok",
                message=f"Connected as {user.get('login', '')}",
            )
        except Exception as e:
            return ConnectorHealth(status="error", message=str(e))

    def fetch(
        self,
        service_name: Optional[str] = None,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        **kwargs,
    ) -> ConnectorData:
        normaliser = GitHubNormaliser(self._config, self.org_id)

        start = window_start or datetime.now(timezone.utc)
        end = window_end or datetime.now(timezone.utc)

        repos = self._config.get("repos", [])
        if service_name and not repos:
            smap = self._service_map or {}
            repos = smap.get(service_name, [])

        if not repos:
            repos = self._list_repos()

        # Normalise to full_name format (owner/repo)
        repos = [self._full_name(r) for r in repos]

        events = []
        raw_count = 0
        warnings = []

        for repo in repos:
            try:
                prs, count, warns = self._fetch_repo_prs(repo, start, end, normaliser)
                events.extend(prs)
                raw_count += count
                warnings.extend(warns)
            except Exception as e:
                warnings.append(f"Error fetching {repo}: {e}")
                log.error(f"GitHub fetch error for {repo}: {e}")

        return ConnectorData(
            connector_type=self.connector_type,
            normalised_events=events,
            raw_event_count=raw_count,
            metadata={"repos_queried": repos},
            warnings=warnings,
        )

    def _full_name(self, repo: str) -> str:
        """Ensure repo is in 'owner/repo' format. Prepend org if it's a bare name."""
        if "/" in repo:
            return repo
        org = self._config.get("org")
        if not org:
            raise ValueError(
                f"Cannot resolve repo '{repo}' to owner/repo — "
                "either provide full names ('owner/repo') or set 'org'"
            )
        return f"{org}/{repo}"

    def _fetch_repo_prs(
        self, full_name: str, start: datetime, end: datetime,
        normaliser: GitHubNormaliser
    ) -> tuple[list, int, list]:
        client = self._client()
        events = []
        raw_count = 0
        warnings = []
        page = 1

        while True:
            resp = client.get(
                f"{GITHUB_API}/repos/{full_name}/pulls",
                params={
                    "state": "closed",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": 100,
                    "page": page,
                },
            )
            resp.raise_for_status()
            prs = resp.json()

            if not prs:
                break

            done = False
            for pr in prs:
                merged_at = pr.get("merged_at")
                if not merged_at:
                    continue
                try:
                    merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                except Exception:
                    continue

                if merged_dt < start:
                    done = True
                    break
                if merged_dt > end:
                    continue

                try:
                    files_resp = client.get(
                        f"{GITHUB_API}/repos/{full_name}/pulls/{pr['number']}/files",
                        params={"per_page": 100},
                    )
                    files_resp.raise_for_status()
                    files = [
                        {
                            "filename": f["filename"],
                            "status": f["status"],
                            "additions": f.get("additions", 0),
                            "deletions": f.get("deletions", 0),
                            "patch": f.get("patch", "")[:2000],
                        }
                        for f in files_resp.json()
                    ]
                except Exception as e:
                    warnings.append(f"Could not fetch files for PR #{pr['number']}: {e}")
                    files = []

                pr["_files"] = files
                pr["_repo"] = full_name
                raw_count += 1
                try:
                    events.append(normaliser.to_ues(pr))
                except Exception as e:
                    warnings.append(f"Normalise error PR #{pr.get('number')}: {e}")

            if done or len(prs) < 100:
                break
            page += 1

        return events, raw_count, warnings

    def _list_repos(self) -> list[str]:
        """List repos accessible to the token (up to 300), as full names."""
        client = self._client()
        org = self._config.get("org")
        repos = []
        page = 1

        while len(repos) < 300:
            if org:
                resp = client.get(
                    f"{GITHUB_API}/orgs/{org}/repos",
                    params={"per_page": 100, "page": page},
                )
                if resp.status_code == 404:
                    resp = client.get(
                        f"{GITHUB_API}/users/{org}/repos",
                        params={"per_page": 100, "page": page},
                    )
            else:
                # PAT without org — list all repos accessible to the token
                resp = client.get(
                    f"{GITHUB_API}/user/repos",
                    params={"per_page": 100, "page": page, "affiliation": "owner,collaborator,organization_member"},
                )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            repos.extend(r["full_name"] for r in data)
            if len(data) < 100:
                break
            page += 1

        return repos

    def _get_token(self) -> str:
        """Get auth token — Personal Access Token or GitHub App JWT."""
        if self._config.get("token"):
            return self._config["token"]

        # GitHub App auth
        try:
            import jwt as pyjwt
        except ImportError:
            raise ImportError("PyJWT required for GitHub App auth: pip install PyJWT cryptography")

        app_id = self._config["app_id"]
        private_key = self._config["private_key"]
        installation_id = self._config.get("installation_id")

        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
        app_jwt = pyjwt.encode(payload, private_key, algorithm="RS256")

        if not installation_id:
            resp = httpx.get(
                f"{GITHUB_API}/app/installations",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
            resp.raise_for_status()
            installs = resp.json()
            org = self._config["org"]
            for inst in installs:
                if inst.get("account", {}).get("login") == org:
                    installation_id = inst["id"]
                    break

            if not installation_id:
                raise RuntimeError(
                    f"GitHub App not installed for org '{org}'. "
                    "Install the App or set 'installation_id' in the connector config."
                )

        resp = httpx.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["token"]

    def _client(self) -> httpx.Client:
        token = self._get_token()
        return httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
