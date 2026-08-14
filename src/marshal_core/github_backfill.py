"""Backfill repo/PR identity onto inbox gate_runs whose evidence lacks it, by asking
GitHub which PR a commit SHA belongs to.

A commit SHA alone doesn't name its repo, so we try each (org, repo) pair that already
appears in some other gate_run's GitHub links (the repo universe this db touches). The
network call is isolated in `fetch_pulls` so tests can stub it; the real call needs
$GITHUB_TOKEN. Results are written back into `evidence["_backfill"]` so the inbox reads
them without repeating the API call.
"""
import json
import os
import re

import httpx
from sqlalchemy import select

from .knowledge.models import GateRun
from .knowledge.store import Store, NEEDS_HUMAN_VERDICTS

_GH_PULL = re.compile(r"github\.com/([^/\s]+)/([^/\s]+)/pull/\d+")


def candidate_repos(session) -> list[tuple[str, str]]:
    """(org, repo) pairs seen in any gate_run's GitHub links — the repo universe."""
    pairs: dict[tuple[str, str], None] = {}
    for (ev,) in session.execute(select(GateRun.evidence)):
        if ev is None:
            continue
        for m in _GH_PULL.finditer(json.dumps(ev)):
            pairs[(m.group(1), m.group(2))] = None
    return list(pairs.keys())


def fetch_pulls(org: str, repo: str, sha: str) -> list:
    """Real GitHub call: PRs associated with a commit. [] on any non-200."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = httpx.get(f"https://api.github.com/repos/{org}/{repo}/commits/{sha}/pulls",
                  headers=headers, timeout=15)
    return r.json() if r.status_code == 200 and isinstance(r.json(), list) else []


def resolve_sha(sha: str, candidates, fetch=fetch_pulls):
    """Return (repo, pr) for the first candidate repo that owns this commit, else None."""
    for org, repo in candidates:
        try:
            pulls = fetch(org, repo, sha)
        except Exception:
            continue
        if pulls:
            num = pulls[0].get("number")
            if num is not None:
                return repo, num
    return None


def backfill(session, fetch=fetch_pulls, limit: int = 200) -> int:
    """Resolve repo/pr for inbox gate_runs that lack an identity and cache it into
    evidence['_backfill']. Returns the number of rows backfilled."""
    candidates = candidate_repos(session)
    if not candidates:
        return 0
    rows = session.scalars(
        select(GateRun).where(GateRun.verdict.in_(NEEDS_HUMAN_VERDICTS))
        .order_by(GateRun.id.desc()).limit(limit)).all()
    n = 0
    for gr in rows:
        s = Store.inbox_summary(gr.evidence)
        if s["repo"] and s["pr"] is not None:
            continue  # already identifiable
        found = resolve_sha(gr.change_ref, candidates, fetch=fetch)
        if not found:
            continue
        repo, pr = found
        ev = dict(gr.evidence or {})
        ev["_backfill"] = {"repo": repo, "pr": pr}
        gr.evidence = ev            # reassign so SQLAlchemy tracks the JSON change
        n += 1
    session.commit()
    return n
