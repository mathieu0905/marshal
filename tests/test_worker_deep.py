import json
import pytest
from marshal_core.worker import _parse_verdict, DeepReviewError, VERDICT_FILE


def _write(tmp_path, obj):
    p = tmp_path / VERDICT_FILE
    p.write_text(json.dumps(obj))
    return str(p)


def test_parse_verdict_valid(tmp_path):
    path = _write(tmp_path, {"verdict": "needs_human", "summary": "s",
                             "findings": ["f1"], "invariants_run": 5, "invariants_pass": 5})
    v = _parse_verdict(path)
    assert v["verdict"] == "needs_human"
    assert v["findings"] == ["f1"]


def test_parse_verdict_missing_file_raises(tmp_path):
    with pytest.raises(DeepReviewError, match="not written"):
        _parse_verdict(str(tmp_path / VERDICT_FILE))


def test_parse_verdict_bad_json_raises(tmp_path):
    p = tmp_path / VERDICT_FILE
    p.write_text("{not json")
    with pytest.raises(DeepReviewError, match="unparseable"):
        _parse_verdict(str(p))


def test_parse_verdict_invalid_verdict_value_raises(tmp_path):
    path = _write(tmp_path, {"verdict": "lgtm"})
    with pytest.raises(DeepReviewError, match="invalid verdict"):
        _parse_verdict(path)


import os
import subprocess
from marshal_core.worker import _deep_worktree


def _make_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "f.txt").write_text("hi")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)
    sha = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return sha


def test_deep_worktree_creates_and_tears_down(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    sha = _make_repo(ws / "node")
    monkeypatch.setenv("MARSHAL_WORKSPACE", str(ws))
    # Use a stable non-/tmp path for worktrees (default ~/.marshal/worktrees)
    wt_base = tmp_path / "stable_wts"
    wt_base.mkdir()
    monkeypatch.setenv("MARSHAL_WORKTREE_BASE", str(wt_base))

    seen = {}
    with _deep_worktree("node", sha) as wt:
        seen["wt"] = wt
        assert os.path.isdir(wt)
        assert os.path.exists(os.path.join(wt, "f.txt"))  # checked out at the ref
        assert str(wt_base) in wt                          # uses the configured base
    assert not os.path.isdir(seen["wt"])
