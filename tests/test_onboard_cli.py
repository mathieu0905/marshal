import json

from marshal_core.cli import main

PAGE = """---
type: concept
concept_id: gas
parent: ""
importance: constitutional
status: authoritative
last_updated: 2026-07-25
---
gas.
"""


def _repo(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution").mkdir(parents=True)
    (repo / "execution" / "gas.rs").write_text("pub struct GasReport {}\n")
    (repo / "README.md").write_text("# node\n")
    return repo


def test_onboard_estimate_cli(tmp_path, capsys):
    rc = main(["onboard-estimate", "--repo", str(_repo(tmp_path))])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["is_estimate"] is True and "method" in out


def test_onboard_detect_cli(tmp_path, capsys):
    rc = main(["onboard-detect", "--repo", str(_repo(tmp_path))])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "candidate_seeds" in out and out["languages"].get("rust") == 1


def test_onboard_report_cli(tmp_path, capsys):
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "gas.md").write_text(PAGE)          # constitutional, 无 anchor → doc_only
    rc = main(["onboard-report", "--domain-pack", "cowboy",
               "--concepts-dir", str(concepts), "--repo-root", f"node={_repo(tmp_path)}"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "gas" in out["unanchored_high"]          # 高重要性无锚定被拎出
