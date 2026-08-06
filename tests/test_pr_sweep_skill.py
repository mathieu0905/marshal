import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / ".agents/skills/marshal-pr-sweep"
FIND_TARGETS = SWEEP / "scripts/find_targets.sh"
RUN_SWEEP = SWEEP / "scripts/run_sweep.sh"
HEAD = "a" * 40
OLD_HEAD = "b" * 40


def _write_executable(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fake_gh(tmp_path: Path) -> Path:
    fake = tmp_path / "bin" / "gh"
    fake.parent.mkdir(parents=True)
    _write_executable(
        fake,
        r"""
        #!/usr/bin/env bash
        set -eu
        case "$1:$2" in
          auth:status)
            [ "${GH_AUTH_MODE:-clean}" != "failure" ] || exit 6
            exit 0
            ;;
          api:user)
            printf '%s\n' 'marshal-bot'
            ;;
          pr:list)
            if [ -n "${GH_PRS_JSON:-}" ]; then
              printf '%s\n' "$GH_PRS_JSON"
            else
              printf '[{"number":7,"headRefOid":"%s","isDraft":false,"title":"%s","url":"https://example.test/pr/7"}]\n' "$GH_HEAD" "${GH_TITLE:-Safe change}"
            fi
            ;;
          api:repos/*/issues/*/comments)
            if [ "${GH_COMMENTS_MODE:-empty}" = "failure" ]; then
              exit 9
            elif [ "${GH_COMMENTS_MODE:-empty}" = "attacker" ]; then
              printf '[{"user":{"login":"attacker"},"body":"<!-- marshal-deep sha=%s -->"}]\n' "$GH_HEAD"
            elif [ "${GH_COMMENTS_MODE:-empty}" = "reviewed" ]; then
              marker_sha="${GH_MARKER_SHA:-$GH_HEAD}"
              case "${GH_MARKER_STYLE:-exact}" in
                exact) marker="<!-- marshal-deep sha=$marker_sha -->" ;;
                prose) marker="note marshal-deep sha=$marker_sha done" ;;
                overlong) marker="<!-- marshal-deep sha=${marker_sha}f -->" ;;
                uppercase) marker="<!-- marshal-deep sha=$(printf '%s' "$marker_sha" | tr 'a-f' 'A-F') -->" ;;
                *) exit 65 ;;
              esac
              printf '[{"user":{"login":"marshal-bot"},"body":"%s"}]\n' "$marker"
            else
              printf '[]\n'
            fi
            ;;
          pr:view)
            [ "${GH_CI_MODE:-clean}" != "failure" ] || exit 8
            jq_filter=''
            while [ "$#" -gt 0 ]; do
              if [ "$1" = "--jq" ]; then
                shift
                jq_filter="$1"
              fi
              shift
            done
            case "${GH_CI_MODE:-clean}" in
              clean) payload='{"statusCheckRollup":[]}' ;;
              stale) payload='{"statusCheckRollup":[{"__typename":"CheckRun","status":"COMPLETED","conclusion":"STALE"}]}' ;;
              unknown) payload='{"statusCheckRollup":[{"__typename":"CheckRun","status":"COMPLETED","conclusion":null}]}' ;;
              *) exit 66 ;;
            esac
            printf '%s\n' "$payload" | jq -r "$jq_filter"
            ;;
          api:repos/*/commits/*)
            [ "${GH_COMMIT_MODE:-clean}" != "failure" ] || exit 7
            printf '%s\n' '2026-08-02T00:00:00Z'
            ;;
          *)
            printf 'unexpected fake gh call: %s\n' "$*" >&2
            exit 64
            ;;
        esac
        """,
    )
    return fake


def _run_find_targets(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess:
    fake_gh = _fake_gh(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{fake_gh.parent}:{os.environ['PATH']}",
        "REPOS": "node",
        "GH_HEAD": HEAD,
        **overrides,
    }
    return subprocess.run(
        [str(FIND_TARGETS)], capture_output=True, text=True, env=env, cwd=ROOT
    )


@pytest.mark.skipif(shutil.which("jq") is None, reason="find_targets requires jq")
def test_find_targets_only_trusts_marker_from_authenticated_user(tmp_path):
    attacker = _run_find_targets(tmp_path / "attacker", GH_COMMENTS_MODE="attacker")
    assert attacker.returncode == 0, attacker.stderr
    target = json.loads(attacker.stdout)
    assert target["head"] == HEAD
    assert target["reason"] == "never"

    reviewed = _run_find_targets(tmp_path / "reviewed", GH_COMMENTS_MODE="reviewed")
    assert reviewed.returncode == 0, reviewed.stderr
    assert reviewed.stdout == ""

    short_marker = _run_find_targets(
        tmp_path / "short",
        GH_COMMENTS_MODE="reviewed",
        GH_MARKER_SHA=HEAD[:7],
    )
    assert short_marker.returncode == 0, short_marker.stderr
    assert json.loads(short_marker.stdout)["reason"] == "never"

    for style in ("prose", "overlong", "uppercase"):
        malformed_marker = _run_find_targets(
            tmp_path / style,
            GH_COMMENTS_MODE="reviewed",
            GH_MARKER_STYLE=style,
        )
        assert malformed_marker.returncode == 0, malformed_marker.stderr
        assert json.loads(malformed_marker.stdout)["reason"] == "never"

    updated = _run_find_targets(
        tmp_path / "updated",
        GH_COMMENTS_MODE="reviewed",
        GH_MARKER_SHA=OLD_HEAD,
    )
    assert updated.returncode == 0, updated.stderr
    assert json.loads(updated.stdout)["reason"] == "updated"


@pytest.mark.skipif(shutil.which("jq") is None, reason="find_targets requires jq")
def test_find_targets_fails_closed_on_incomplete_discovery(tmp_path):
    auth_failure = _run_find_targets(tmp_path / "auth", GH_AUTH_MODE="failure")
    assert auth_failure.returncode != 0
    assert auth_failure.stdout == ""
    assert "authentication is not healthy" in auth_failure.stderr

    comments_failure = _run_find_targets(
        tmp_path / "comments", GH_COMMENTS_MODE="failure"
    )
    assert comments_failure.returncode != 0
    assert comments_failure.stdout == ""
    assert "cannot read comments" in comments_failure.stderr

    ci_failure = _run_find_targets(tmp_path / "ci", GH_CI_MODE="failure")
    assert ci_failure.returncode != 0
    assert ci_failure.stdout == ""
    assert "cannot read CI state" in ci_failure.stderr

    commit_failure = _run_find_targets(tmp_path / "commit", GH_COMMIT_MODE="failure")
    assert commit_failure.returncode != 0
    assert commit_failure.stdout == ""
    assert "cannot read head commit time" in commit_failure.stderr

    invalid_toggle = _run_find_targets(tmp_path / "toggle", REQUIRE_CI_PASS="yes")
    assert invalid_toggle.returncode == 2
    assert "REQUIRE_CI_PASS must be 0 or 1" in invalid_toggle.stderr

    truncated = _run_find_targets(tmp_path / "cap", PR_LIMIT="1")
    assert truncated.returncode != 0
    assert truncated.stdout == ""
    assert "discovery may be truncated" in truncated.stderr

    malformed = _run_find_targets(tmp_path / "metadata", GH_PRS_JSON="[{}]")
    assert malformed.returncode != 0
    assert malformed.stdout == ""
    assert "invalid PR metadata" in malformed.stderr

    mixed_rows = json.dumps(
        [
            {
                "number": 7,
                "headRefOid": HEAD,
                "isDraft": False,
                "title": "Safe change",
                "url": "https://example.test/pr/7",
            },
            {},
        ]
    )
    mixed = _run_find_targets(tmp_path / "mixed", GH_PRS_JSON=mixed_rows)
    assert mixed.returncode != 0
    assert mixed.stdout == ""
    assert "invalid PR metadata" in mixed.stderr

    invalid_limit = _run_find_targets(tmp_path / "limit", PR_LIMIT="none")
    assert invalid_limit.returncode == 2
    assert "PR_LIMIT must be a positive integer" in invalid_limit.stderr


@pytest.mark.skipif(shutil.which("jq") is None, reason="find_targets requires jq")
def test_find_targets_fails_closed_on_unknown_ci_and_cip10_variants(tmp_path):
    for mode in ("stale", "unknown"):
        ci_unknown = _run_find_targets(tmp_path / mode, GH_CI_MODE=mode)
        assert ci_unknown.returncode == 0, ci_unknown.stderr
        assert ci_unknown.stdout == ""
        assert "ci-pending" in ci_unknown.stderr

    for title in ("CIP 10 rollout", "CIP_10 registry migration"):
        cip10 = _run_find_targets(tmp_path / title.split()[0], GH_TITLE=title)
        assert cip10.returncode == 0, cip10.stderr
        assert cip10.stdout == ""
        assert "cip-10 avoidance" in cip10.stderr


def test_sweep_scripts_are_executable_and_parse_as_bash():
    for script in (FIND_TARGETS, RUN_SWEEP):
        assert os.access(script, os.X_OK)
        proc = subprocess.run(
            ["bash", "-n", str(script)], capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stderr


def test_fake_gh_supports_the_skill_authentication_preflight(tmp_path):
    fake_gh = _fake_gh(tmp_path)
    proc = subprocess.run(
        [str(fake_gh), "auth", "status"], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_run_sweep_uses_safe_codex_exec_defaults(tmp_path):
    fake_codex = tmp_path / "bin" / "codex"
    fake_codex.parent.mkdir()
    capture = tmp_path / "codex-args"
    _write_executable(
        fake_codex,
        r"""
        #!/usr/bin/env bash
        printf '%s\n' "$@" >"$CAPTURE"
        exit "${FAKE_CODEX_STATUS:-0}"
        """,
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log_dir = tmp_path / "logs"
    env = {
        **os.environ,
        "CODEX_BIN": str(fake_codex),
        "CAPTURE": str(capture),
        "MARSHAL_HOME": str(ROOT),
        "WORKSPACE": str(workspace),
        "LOG_DIR": str(log_dir),
        "MAX_PER_RUN": "7",
    }

    proc = subprocess.run(
        [str(RUN_SWEEP)], capture_output=True, text=True, env=env, cwd=ROOT
    )
    assert proc.returncode == 0, proc.stderr
    args = capture.read_text(encoding="utf-8").splitlines()
    assert args[:3] == ["exec", "--cd", str(workspace)]
    assert "--skip-git-repo-check" in args
    assert "--add-dir" not in args
    assert "workspace-write" in args
    assert 'approval_policy="never"' in args
    assert "sandbox_workspace_write.network_access=true" in args
    assert "--dangerously-bypass-approvals-and-sandbox" not in args
    assert "--yolo" not in args
    assert "--model" not in args
    assert "$marshal-pr-sweep" in args[-1]
    assert "MAX_PER_RUN is '7'" in args[-1]
    assert "untrusted data" in args[-1]
    assert "read-only reference material" in args[-1]
    assert str(SWEEP / "SKILL.md") in args[-1]
    logs = list(log_dir.glob("sweep-*.log"))
    assert len(logs) == 1
    assert "done (exit 0)" in logs[0].read_text(encoding="utf-8")

    invalid = subprocess.run(
        [str(RUN_SWEEP)],
        capture_output=True,
        text=True,
        env={**env, "MAX_PER_RUN": "0"},
        cwd=ROOT,
    )
    assert invalid.returncode == 2
    assert "positive integer" in invalid.stderr

    state_home = tmp_path / "state"
    default_capture = tmp_path / "default-codex-args"
    default_env = {
        key: value
        for key, value in env.items()
        if key not in {"WORKSPACE", "LOG_DIR"}
    }
    default_env.update(
        {"CAPTURE": str(default_capture), "XDG_STATE_HOME": str(state_home)}
    )
    default = subprocess.run(
        [str(RUN_SWEEP)], capture_output=True, text=True, env=default_env, cwd=ROOT
    )
    assert default.returncode == 0, default.stderr
    default_args = default_capture.read_text(encoding="utf-8").splitlines()
    isolated_workspace = state_home / "marshal-pr-sweep/workspace"
    assert default_args[:3] == ["exec", "--cd", str(isolated_workspace)]
    assert isolated_workspace.is_dir()
    assert str(ROOT.parent) not in default_args
