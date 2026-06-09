"""CI/CD threat-model guard (Marshal P1+P2) — permanent check for ratchet
esc-20260609-marshal-missed-ci-pwn-request (node PR #649: Almanax caught a
self-hosted-runner-on-pull_request HIGH + open privileged ephemeral deploy/destroy
that Marshal passed blind). These assert DETECTION capability, not just labeling."""
from marshal_pack_cowboy import ci_security
from marshal_pack_cowboy.pack import CowboyPack

P = ".github/workflows/x.yml"


def ids(content):
    return {h["id"] for h in ci_security.hazards_for_workflow(P, content)}


# --- the exact #649 coverage.yml shape: PR-triggered job on a custom runner w/ a token ---
PWN_COVERAGE = """\
name: Coverage
on:
  pull_request:
  push:
    branches: [main, devnet]
jobs:
  coverage:
    runs-on: ubuntu-latest-lx
    env:
      CROSS_REPO_TOKEN: ${{ secrets.CROSS_REPO_TOKEN }}
    steps:
      - uses: actions/checkout@v4
"""


def test_custom_runner_on_pull_request_is_high():
    got = ids(PWN_COVERAGE)
    assert "ci.custom-runner-on-untrusted-event" in got
    assert "ci.secret-exposed-to-untrusted-trigger" in got


def test_default_runner_on_pull_request_no_runner_hazard():
    safe = PWN_COVERAGE.replace("ubuntu-latest-lx", "ubuntu-latest")
    assert "ci.custom-runner-on-untrusted-event" not in ids(safe)


# --- push-only build job on a custom runner must NOT alarm (the pipeline.yml FP) ---
PUSH_ONLY = """\
name: Build
on:
  pull_request:
  push:
    branches: [main, devnet]
jobs:
  build:
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/devnet'
    runs-on: ubuntu-latest-l
    env:
      CROSS_REPO_TOKEN: ${{ secrets.CROSS_REPO_TOKEN }}
    steps:
      - run: echo build
"""


def test_push_gated_custom_runner_not_reachable():
    assert ids(PUSH_ONLY) == set()


# --- open privileged cross-repo dispatch: fires without an actor allowlist, clears with ---
DISPATCH_OPEN = """\
name: Pipeline
on:
  push:
  delete:
jobs:
  deploy:
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/ephemeral/')
    runs-on: ubuntu-latest
    steps:
      - uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.CROSS_REPO_TOKEN }}
          repository: cowboyinc/aws-infrastructure
"""
DISPATCH_GATED = DISPATCH_OPEN.replace(
    "startsWith(github.ref, 'refs/heads/ephemeral/')",
    "startsWith(github.ref, 'refs/heads/ephemeral/') && "
    "contains(format(',{0},', vars.ALLOWED), format(',{0},', github.actor))")


def test_open_privileged_dispatch_is_medium():
    assert "ci.open-privileged-dispatch" in ids(DISPATCH_OPEN)


def test_actor_allowlist_clears_open_dispatch():
    assert "ci.open-privileged-dispatch" not in ids(DISPATCH_GATED)


# --- delete-only job exposing a token is NOT pull_request-reachable ---
DELETE_ONLY = """\
name: Pipeline
on:
  pull_request:
  delete:
jobs:
  destroy:
    if: github.event_name == 'delete' && startsWith(github.event.ref, 'ephemeral/')
    runs-on: ubuntu-latest
    env:
      CROSS_REPO_TOKEN: ${{ secrets.CROSS_REPO_TOKEN }}
    steps:
      - run: echo destroy
"""


def test_delete_event_job_not_pr_reachable():
    assert "ci.secret-exposed-to-untrusted-trigger" not in ids(DELETE_ONLY)


# --- pwn request: pull_request_target is privileged regardless of job ---
def test_pull_request_target_is_high():
    wf = "on:\n  pull_request_target:\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: x\n"
    assert "ci.privileged-untrusted-trigger" in ids(wf)


def test_script_injection_detected():
    wf = ("on:\n  issue_comment:\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
          "    steps:\n      - run: echo ${{ github.event.comment.body }}\n")
    assert "ci.script-injection" in ids(wf)


# --- integration: a CI hazard escalates classify to high via security_hazards ---
def test_ci_hazard_escalates_classify_to_high():
    pack = CowboyPack()
    d = pack.classify_detailed({
        "repo": "node",
        "diff_paths": [".github/workflows/coverage.yml"],
        "workflow_files": {".github/workflows/coverage.yml": PWN_COVERAGE},
    })
    assert d["tier"] == "high"
    assert any("ci.custom-runner-on-untrusted-event" in r for r in d["reasons"])
    assert any(h["id"].startswith("ci.") for h in d["security_hazards"])


def test_scan_scope_flags_degraded_without_whole_file():
    _, meta = ci_security.scan_scope({
        "diff_paths": [".github/workflows/coverage.yml"], "diff_text": "runs-on: x"})
    assert meta["degraded_no_whole_file"] is True
