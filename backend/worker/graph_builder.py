"""
Apache AGE graph builder.

Builds a property graph of PRs, files, authors, and tickets for an org.
Graph is used by the hypothesis ranker for relationship traversal.

Node types: PR, File, Author, Ticket, Service
Edge types: MODIFIES (PR→File), AUTHORED_BY (PR→Author), REFERENCES (PR→Ticket),
            AFFECTS (PR→Service), CAUSED_BY (Ticket→PR)

AGE is loaded per-connection via LOAD 'age' + SET search_path.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

log = logging.getLogger(__name__)

GRAPH_NAME = "bugpilot"


def _ensure_graph(conn) -> None:
    """Create the AGE graph if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("LOAD 'age'")
        cur.execute("SET search_path = ag_catalog, public")
        try:
            cur.execute(
                "SELECT * FROM ag_catalog.create_graph(%s)",
                (GRAPH_NAME,),
            )
        except Exception:
            conn.rollback()  # graph already exists — that's fine


def upsert_pr_nodes(conn, org_id: str, pr_events: list[dict]) -> int:
    """
    Upsert PR, File, and Author nodes + edges from GitHub UES events.
    Returns count of PRs processed.
    """
    _ensure_graph(conn)
    count = 0

    for event in pr_events:
        pr_id = str(event.get("pr_id", ""))
        pr_title = event.get("pr_title", "").replace("'", "\\'")
        pr_url = event.get("pr_url", "")
        pr_author = event.get("pr_author", "").replace("'", "\\'")
        pr_merged_at = event.get("pr_merged_at") or ""
        repo = event.get("repo", "")
        files = event.get("files", [])

        try:
            with conn.cursor() as cur:
                cur.execute("LOAD 'age'")
                cur.execute("SET search_path = ag_catalog, public")

                # Upsert PR node
                cur.execute(
                    f"""SELECT * FROM cypher('{GRAPH_NAME}', $$
                        MERGE (pr:PR {{
                            org_id: '{org_id}',
                            pr_id: '{pr_id}',
                            repo: '{repo}'
                        }})
                        SET pr.title = '{pr_title}',
                            pr.url = '{pr_url}',
                            pr.merged_at = '{pr_merged_at}'
                        RETURN pr
                    $$) AS (pr agtype)"""
                )

                # Upsert Author node + edge
                if pr_author:
                    cur.execute(
                        f"""SELECT * FROM cypher('{GRAPH_NAME}', $$
                            MERGE (a:Author {{login: '{pr_author}', org_id: '{org_id}'}})
                            WITH a
                            MATCH (pr:PR {{pr_id: '{pr_id}', org_id: '{org_id}'}})
                            MERGE (pr)-[:AUTHORED_BY]->(a)
                            RETURN a
                        $$) AS (a agtype)"""
                    )

                # Upsert File nodes + MODIFIES edges
                for file_info in files[:50]:  # cap at 50 files per PR
                    fname = file_info.get("filename", "").replace("'", "\\'")
                    if not fname:
                        continue
                    cur.execute(
                        f"""SELECT * FROM cypher('{GRAPH_NAME}', $$
                            MERGE (f:File {{
                                path: '{fname}',
                                org_id: '{org_id}'
                            }})
                            WITH f
                            MATCH (pr:PR {{pr_id: '{pr_id}', org_id: '{org_id}'}})
                            MERGE (pr)-[:MODIFIES {{
                                status: '{file_info.get("status","modified")}',
                                additions: {file_info.get("additions", 0)},
                                deletions: {file_info.get("deletions", 0)}
                            }}]->(f)
                            RETURN f
                        $$) AS (f agtype)"""
                    )

            count += 1
        except Exception as e:
            log.warning(f"AGE upsert error for PR {pr_id}: {e}")
            conn.rollback()

    return count


def get_prs_touching_files(conn, org_id: str, file_paths: list[str]) -> list[dict]:
    """
    Return all PRs that modified any of the given file paths.
    Used for cross-PR file overlap detection.
    """
    results = []
    if not file_paths:
        return results

    try:
        with conn.cursor() as cur:
            cur.execute("LOAD 'age'")
            cur.execute("SET search_path = ag_catalog, public")

            for fpath in file_paths[:20]:  # limit for performance
                fpath_escaped = fpath.replace("'", "\\'")
                cur.execute(
                    f"""SELECT * FROM cypher('{GRAPH_NAME}', $$
                        MATCH (pr:PR {{org_id: '{org_id}'}})-[:MODIFIES]->(f:File {{path: '{fpath_escaped}'}})
                        RETURN pr.pr_id AS pr_id, pr.title AS title,
                               pr.merged_at AS merged_at, pr.url AS url
                        ORDER BY pr.merged_at DESC
                        LIMIT 20
                    $$) AS (pr_id agtype, title agtype, merged_at agtype, url agtype)"""
                )
                for row in cur.fetchall():
                    results.append({
                        "pr_id": row[0],
                        "title": row[1],
                        "merged_at": row[2],
                        "url": row[3],
                        "file": fpath,
                    })
    except Exception as e:
        log.warning(f"AGE query error: {e}")

    return results


def set_pr_confirmed(conn, org_id: str, pr_id: str, confirmed: bool) -> None:
    """
    Mark a PR node as confirmed (or refuted) root cause in the AGE graph.
    Called by the feedback endpoint so get_author_risk_score() can use it.
    """
    try:
        value = "true" if confirmed else "false"
        with conn.cursor() as cur:
            cur.execute("LOAD 'age'")
            cur.execute("SET search_path = ag_catalog, public")
            pr_id_esc = str(pr_id).replace("'", "\\'")
            cur.execute(
                f"""SELECT * FROM cypher('{GRAPH_NAME}', $$
                    MATCH (pr:PR {{pr_id: '{pr_id_esc}', org_id: '{org_id}'}})
                    SET pr.confirmed = {value}
                    RETURN pr
                $$) AS (pr agtype)"""
            )
        conn.commit()
    except Exception as e:
        log.warning(f"AGE set_pr_confirmed error for PR {pr_id}: {e}")
        conn.rollback()


def get_author_risk_score(conn, org_id: str, pr_author: str) -> float:
    """
    Compute a risk score for an author based on their past PR history
    (proportion of their PRs that led to confirmed bugs).
    Returns 0.0–1.0.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("LOAD 'age'")
            cur.execute("SET search_path = ag_catalog, public")
            pr_author_esc = pr_author.replace("'", "\\'")
            cur.execute(
                f"""SELECT * FROM cypher('{GRAPH_NAME}', $$
                    MATCH (pr:PR {{org_id: '{org_id}'}})-[:AUTHORED_BY]->(a:Author {{login: '{pr_author_esc}'}})
                    RETURN count(pr) AS total,
                           sum(CASE WHEN pr.confirmed = true THEN 1 ELSE 0 END) AS confirmed
                $$) AS (total agtype, confirmed agtype)"""
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return 0.5  # neutral prior
            total = int(row[0])
            confirmed = int(row[1] or 0)
            if total < 3:
                return 0.5
            return min(1.0, confirmed / total)
    except Exception as e:
        log.warning(f"AGE author risk error: {e}")
        return 0.5
