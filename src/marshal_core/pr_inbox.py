"""Repo-first PR inbox: open PRs across the bound repos, newest-first, each tagged with
review-eligibility and its last local review. GitHub calls are isolated behind
`list_open_prs`/`pr_detail`/`commit_status` (stubbed in tests; real calls need
$GITHUB_TOKEN). `build_inbox` is pure given those seams.
"""
import os

import httpx
from sqlalchemy import select

from .knowledge.models import GateRun
from .knowledge.store import Store

_DEFAULT_REPOS = ("cowboyinc/node", "cowboyinc/cbfs", "cowboyinc/cbss",
                  "cowboyinc/cowboy", "cowboyinc/runner", "shawhanken/marshal")


def bound_repos() -> list[tuple[str, str]]:
    raw = os.environ.get("MARSHAL_REPOS") or ",".join(_DEFAULT_REPOS)
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if "/" in tok:
            org, repo = tok.split("/", 1)
            out.append((org.strip(), repo.strip()))
    return out


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def list_open_prs(org: str, repo: str, per_page: int = 30) -> list:
    r = httpx.get(f"https://api.github.com/repos/{org}/{repo}/pulls",
                  params={"state": "open", "sort": "updated", "direction": "desc",
                          "per_page": per_page},
                  headers=_headers(), timeout=15)
    return r.json() if r.status_code == 200 and isinstance(r.json(), list) else []


def pr_detail(org: str, repo: str, number) -> dict:
    r = httpx.get(f"https://api.github.com/repos/{org}/{repo}/pulls/{number}",
                  headers=_headers(), timeout=15)
    return r.json() if r.status_code == 200 and isinstance(r.json(), dict) else {}


def commit_status(org: str, repo: str, sha: str):
    if not sha:
        return None
    r = httpx.get(f"https://api.github.com/repos/{org}/{repo}/commits/{sha}/status",
                  headers=_headers(), timeout=15)
    return r.json().get("state") if r.status_code == 200 else None


def eligibility(mergeable_state, ci_state):
    """(eligible, blocked_reason). Ineligible only on a *known* conflict or CI failure."""
    if mergeable_state == "dirty":
        return False, "merge conflict"
    if ci_state == "failure":
        return False, "CI failing"
    return True, None
