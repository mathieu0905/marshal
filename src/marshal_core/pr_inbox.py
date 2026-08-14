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


def _review_index(session) -> dict:
    """{(repo, str(pr)): {verdict, head_sha}} for the newest gate_run of each PR."""
    idx = {}
    for gr in session.scalars(select(GateRun).order_by(GateRun.id)):
        s = Store.inbox_summary(gr.evidence)
        if s["repo"] and s["pr"] is not None:
            idx[(s["repo"], str(s["pr"]))] = {"verdict": gr.verdict, "head_sha": gr.change_ref}
    return idx  # later (higher-id) rows overwrite earlier ones -> newest wins


def build_inbox(session, repos=None) -> list[dict]:
    repos = repos if repos is not None else bound_repos()
    review_idx = _review_index(session)
    prs = []
    for org, repo in repos:
        for pr in list_open_prs(org, repo):
            num = pr.get("number")
            head_sha = (pr.get("head") or {}).get("sha", "")
            detail = pr_detail(org, repo, num)
            ci = commit_status(org, repo, head_sha)
            eligible, reason = eligibility(detail.get("mergeable_state"), ci)
            last = review_idx.get((repo, str(num)))
            last_review = None
            if last:
                last_review = {"verdict": last["verdict"], "reviewed_head": last["head_sha"],
                               "stale": last["head_sha"] != head_sha}
            prs.append({
                "org": org, "repo": repo, "number": num,
                "title": pr.get("title", ""), "url": pr.get("html_url", ""),
                "head_sha": head_sha, "updated_at": pr.get("updated_at", ""),
                "draft": bool(pr.get("draft")),
                "eligible": eligible, "blocked_reason": reason,
                "last_review": last_review,
            })
    prs.sort(key=lambda p: p["updated_at"], reverse=True)
    return prs
