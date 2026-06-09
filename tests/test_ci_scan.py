"""ci-scan zizmor wrapper (Marshal P0 — deterministic CI-security backstop)."""
import json
import stat

from marshal_core.cli import _normalize_zizmor, main


def test_normalize_zizmor_array_schema():
    raw = json.dumps([{
        "ident": "self-hosted-runner",
        "determinations": {"severity": "High"},
        "desc": "self-hosted runner used in pull_request",
        "locations": [{"symbolic": {"key": {"filename": ".github/workflows/coverage.yml"},
                                    "location": "line 22"}}],
    }])
    out = _normalize_zizmor(raw)
    assert out == [{"id": "self-hosted-runner", "severity": "high",
                    "path": ".github/workflows/coverage.yml", "location": "line 22",
                    "message": "self-hosted runner used in pull_request"}]


def test_normalize_zizmor_bad_json_returns_none():
    assert _normalize_zizmor("not json") is None


def test_ci_scan_missing_binary_is_degraded(capsys):
    rc = main(["ci-scan", "--paths", "x.yml", "--zizmor-bin", "/nonexistent/zizmor"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["degraded"] is True and out["error"] == "zizmor not installed"


def test_ci_scan_success_with_fake_zizmor(tmp_path, capsys):
    fake = tmp_path / "zizmor"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'echo \'[{"ident":"artipacked","determinations":{"severity":"Low"},'
        '"desc":"d","locations":[{"symbolic":{"key":{"filename":"w.yml"},'
        '"location":"l1"}}]}]\'\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)
    wf = tmp_path / "w.yml"
    wf.write_text("on: pull_request\n")
    rc = main(["ci-scan", "--paths", str(wf), "--zizmor-bin", str(fake)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["count"] == 1 and out["worst_severity"] == "low"
    assert out["findings"][0]["id"] == "artipacked"
