"""ci-scan zizmor wrapper (Marshal P0 — deterministic CI-security backstop)."""
import json
import stat

from marshal_core.cli import _normalize_zizmor, main


def test_normalize_zizmor_real_schema():
    # zizmor 1.x schema: severity in .determinations, path in .key.Local.given_path,
    # line in .concrete.location.start_point.row.
    raw = json.dumps([{
        "ident": "unpinned-uses",
        "desc": "unpinned action reference",
        "determinations": {"confidence": "High", "severity": "High"},
        "locations": [{
            "symbolic": {"key": {"Local": {"given_path": "w.yml"}}},
            "concrete": {"location": {"start_point": {"row": 34, "column": 8}}},
        }],
    }])
    out = _normalize_zizmor(raw)
    assert out == [{"id": "unpinned-uses", "severity": "high", "path": "w.yml",
                    "location": "line 34", "message": "unpinned action reference"}]


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
        'echo \'[{"ident":"artipacked","determinations":{"severity":"Medium"},'
        '"desc":"d","locations":[{"symbolic":{"key":{"Local":{"given_path":"w.yml"}}},'
        '"concrete":{"location":{"start_point":{"row":3}}}}]},'
        '{"ident":"unpinned-uses","determinations":{"severity":"High"},"desc":"u",'
        '"locations":[{"symbolic":{"key":{"Local":{"given_path":"w.yml"}}},'
        '"concrete":{"location":{"start_point":{"row":9}}}}]}]\'\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)
    wf = tmp_path / "w.yml"
    wf.write_text("on: pull_request\n")
    rc = main(["ci-scan", "--paths", str(wf), "--zizmor-bin", str(fake)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["count"] == 2 and out["worst_severity"] == "high"
    assert out["by_severity"] == {"medium": 1, "high": 1}
    assert out["findings"][0]["location"] == "line 3"
