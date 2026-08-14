import json
import os
import subprocess
import sys
from pathlib import Path


HOST_SKILLS = {
    "claude": ("marshal", "onboard", "plan-cost"),
    "codex": ("marshal", "onboard", "plan-cost", "marshal-pr-sweep"),
}


def _run(args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    proc = subprocess.run([sys.executable, "-m", "marshal_core.cli", *args],
                          capture_output=True, text=True, env=e,
                          cwd=os.path.dirname(os.path.dirname(__file__)))
    return proc


def test_classify_returns_json_tier():
    proc = _run(["classify", "--repo", "node",
                 "--paths", "execution/src/execution/engine.rs"])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["tier"] == "high"
    assert "review_dimensions" in out


def test_classify_docs_only_low():
    proc = _run(["classify", "--repo", "node", "--paths", "README.md"])
    out = json.loads(proc.stdout)
    assert out["tier"] == "low"


def test_invariants_lists_run_commands():
    proc = _run(["invariants", "--repo", "node",
                 "--paths", "execution/src/execution/transaction.rs"])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    ids = [i["id"] for i in out]
    assert "econ.fee_conservation" in ids
    assert all("run_command" in i for i in out)


def test_invariants_cross_repo_contract():
    proc = _run(["invariants", "--repo", "wallet", "--paths", "src/lib/cbor.js"])
    out = json.loads(proc.stdout)
    assert "contract.tx_encoding_roundtrip" in [i["id"] for i in out]


def test_review_quorum_escalates_high_and_drops_lone_low():
    findings = json.dumps([
        {"file": "x.rs", "line": 1, "dimension": "security", "severity": "high",
         "source": "lens-security", "title": "auth bypass"},
        {"file": "y.rs", "line": 2, "dimension": "style", "severity": "low",
         "source": "lens-correctness", "title": "nit"},
    ])
    proc = _run(["review-quorum", "--findings-json", findings])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["review_verdict"] == "escalate"
    assert len(out["escalate"]) == 1
    assert len(out["dropped"]) == 1


def test_refute_lenses_cmd_returns_distinct_lenses():
    # PYTHONPATH 指向本 checkout 的 src, 使子进程优先 worktree 而非 editable-install
    # 的主仓 (本地才需要; CI 从分支装包时该路径指向同一代码, 无害)。
    src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    proc = _run(["refute-lenses", "--count", "3"], env={"PYTHONPATH": src})
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["count"] == 3
    names = [x["name"] for x in out["lenses"]]
    assert len(names) == 3 and len(set(names)) == 3
    assert all(x["prompt"] for x in out["lenses"])


def test_spec_source_resolves_cip():
    proc = _run(["spec-source", "--ref", "CIP-3"])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["source"]["path_glob"] == "docs/cips/cip-3-*.md"
    assert out["source"]["repo"] == "cowboy"


def test_spec_source_unknown_ref_is_null():
    proc = _run(["spec-source", "--ref", "C-1"])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["source"] is None


def test_conformance_per_cip_breakdown(tmp_path):
    # Fake spec root: CIP-3 (covered by an econ invariant) with 2 MUST clauses,
    # CIP-99 (uncovered) with 1 MUST clause.
    cips = tmp_path / "docs" / "cips"
    cips.mkdir(parents=True)
    (cips / "cip-3-fee-model.md").write_text(
        "Fees MUST be burned.\nTips MUST be paid to proposers.\nprose only.\n")
    (cips / "cip-99-unknown.md").write_text("A node MUST do nothing.\n")
    proc = _run(["conformance", "--spec-root", str(tmp_path)])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["cip_total"] == 2
    assert out["cip_covered"] == 1            # CIP-3 cited by econ.fee_conservation
    assert out["cip_uncovered"] == ["CIP-99"]
    by = {c["cip"]: c for c in out["per_cip"]}
    assert by["CIP-3"]["must_requirements"] == 2 and by["CIP-3"]["covered"] is True
    assert by["CIP-99"]["must_requirements"] == 1 and by["CIP-99"]["covered"] is False
    # biggest gap (uncovered with most MUSTs) sorts first
    assert out["per_cip"][0]["cip"] == "CIP-99"


def test_ratchet_open_then_close(tmp_path):
    db = {"MARSHAL_DB": f"sqlite:///{tmp_path/'t.db'}"}
    op = _run(["ratchet-open", "--desc", "bare 2**10000 逃逸",
               "--root-cause", "determinism-gap", "--escape-id", "esc-t1"], env=db)
    assert op.returncode == 0, op.stderr
    assert json.loads(op.stdout)["escape_id"] == "esc-t1"

    inv = json.dumps({
        "id": "det.bare_pow_literal", "domain": "determinism", "spec_ref": "M-B",
        "executor_kind": "proptest", "location_repo": "node",
        "location_path": "execution/src/pvm_executor.rs",
        "location_test": "prop_bare_pow_literal_blocked", "severity": "high"})
    cl = _run(["ratchet-close", "--escape-id", "esc-t1",
               "--spawned-check", "det.bare_pow_literal", "--inv-json", inv], env=db)
    assert cl.returncode == 0, cl.stderr
    assert json.loads(cl.stdout)["ok"] is True


def test_ratchet_close_tolerates_run_command_in_inv_json(tmp_path):
    # 文档化的棘轮流程让 skill 起草含 run_command 的 InvariantDef;
    # InvariantRegistry 表没有 run_command 列,close 必须照样成功(丢弃该字段)。
    db = {"MARSHAL_DB": f"sqlite:///{tmp_path/'rc.db'}"}
    _run(["ratchet-open", "--desc", "d", "--root-cause", "determinism-gap",
          "--escape-id", "esc-rc"], env=db)
    inv = json.dumps({
        "id": "det.bare_pow_literal", "domain": "determinism", "spec_ref": "M-B",
        "executor_kind": "proptest", "location_repo": "node",
        "location_path": "execution/src/pvm_executor.rs",
        "location_test": "prop_bare_pow_literal_blocked", "severity": "high",
        "run_command": ["cargo", "test", "-p", "cowboy-execution",
                        "prop_bare_pow_literal_blocked", "--", "--exact"]})
    cl = _run(["ratchet-close", "--escape-id", "esc-rc",
               "--spawned-check", "det.bare_pow_literal", "--inv-json", inv], env=db)
    assert cl.returncode == 0, cl.stderr
    assert json.loads(cl.stdout)["ok"] is True


def test_ratchet_close_without_spawned_check_fails(tmp_path):
    db = {"MARSHAL_DB": f"sqlite:///{tmp_path/'t2.db'}"}
    _run(["ratchet-open", "--desc", "d", "--root-cause", "c",
          "--escape-id", "esc-t2"], env=db)
    cl = _run(["ratchet-close", "--escape-id", "esc-t2",
               "--spawned-check", "", "--inv-json", "{}"], env=db)
    assert cl.returncode == 1
    assert "error" in json.loads(cl.stdout)


def test_gate_record_persists_run(tmp_path):
    db = {"MARSHAL_DB": f"sqlite:///{tmp_path/'g.db'}"}
    ev = json.dumps([{"name": "invariants", "outcome": "pass", "evidence_ref": "inv-x"}])
    proc = _run(["gate-record", "--change-ref", "abc123", "--verdict", "pass",
                 "--evidence-json", ev], env=db)
    assert proc.returncode == 0, proc.stderr
    assert isinstance(json.loads(proc.stdout)["run_id"], int)


def test_setup_installs_all_skills_for_claude_and_codex(tmp_path):
    home = tmp_path / "fakehome"
    home.mkdir()
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run(["setup"], env={"HOME": str(home)})
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)

    expected = {
        (host, name) for host, names in HOST_SKILLS.items() for name in names
    }
    assert {(item["host"], item["name"]) for item in out["installed"]} == expected
    for host, host_dir in (("claude", ".claude"), ("codex", ".agents")):
        for name in HOST_SKILLS[host]:
            link = home / host_dir / "skills" / name
            assert link.is_symlink()
            assert (link / "SKILL.md").is_file()
            assert link.resolve() == repo_root / host_dir / "skills" / name

    # Backward-compatible response fields still identify Claude's marshal link.
    assert out["symlink"] == str(home / ".claude" / "skills" / "marshal")
    assert out["ok"] is True
    assert out["import_ok"] is True

    # Re-running setup reuses its managed symlinks and remains idempotent.
    again = _run(["setup"], env={"HOME": str(home)})
    assert again.returncode == 0, again.stderr
    assert {item["status"] for item in json.loads(again.stdout)["installed"]} == {
        "unchanged"
    }


def test_setup_can_target_each_host_only_with_its_complete_skill_set(tmp_path):
    for host, host_dir, other_dir in (
        ("claude", ".claude", ".agents"),
        ("codex", ".agents", ".claude"),
    ):
        home = tmp_path / host
        home.mkdir()
        proc = _run(["setup", "--host", host], env={"HOME": str(home)})
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout)
        assert {(item["host"], item["name"]) for item in out["installed"]} == {
            (host, name) for name in HOST_SKILLS[host]
        }
        assert not (home / other_dir).exists()
        assert all(
            (home / host_dir / "skills" / name).is_symlink()
            for name in HOST_SKILLS[host]
        )
        if host == "codex":
            assert out["symlink"] is None


def test_setup_repeatable_host_selection_is_complete_and_deduplicated(tmp_path):
    home = tmp_path / "fakehome"
    home.mkdir()
    proc = _run(
        ["setup", "--host", "claude", "--host", "codex", "--host", "claude"],
        env={"HOME": str(home)},
    )
    assert proc.returncode == 0, proc.stderr
    installed = json.loads(proc.stdout)["installed"]
    assert len(installed) == 7
    assert {(item["host"], item["name"]) for item in installed} == {
        (host, name)
        for host, names in HOST_SKILLS.items()
        for name in names
    }


def test_setup_codex_conflict_does_not_block_safe_claude_links(tmp_path):
    home = tmp_path / "fakehome"
    conflict = home / ".agents" / "skills" / "marshal"
    conflict.mkdir(parents=True)
    (conflict / "SKILL.md").write_text("user-owned", encoding="utf-8")

    proc = _run(["setup"], env={"HOME": str(home)})
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert {(item["host"], item["name"]) for item in out["installed"]} == {
        (host, name)
        for host, names in HOST_SKILLS.items()
        for name in names
    } - {("codex", "marshal")}
    for item in out["installed"]:
        assert Path(item["symlink"]).resolve() == Path(item["target"]).resolve()
    assert len(out["conflicts"]) == 1
    assert out["conflicts"][0]["path"] == str(conflict)
    assert (conflict / "SKILL.md").read_text(encoding="utf-8") == "user-owned"


def test_setup_does_not_take_over_any_foreign_skill_symlink(tmp_path):
    for host, host_dir in (("claude", ".claude"), ("codex", ".agents")):
        for name in HOST_SKILLS[host]:
            case = tmp_path / f"{host}-{name}"
            home = case / "home"
            foreign = case / "foreign"
            foreign.mkdir(parents=True)
            (foreign / "SKILL.md").write_text("foreign", encoding="utf-8")
            link = home / host_dir / "skills" / name
            link.parent.mkdir(parents=True)
            link.symlink_to(foreign, target_is_directory=True)

            proc = _run(["setup", "--host", host], env={"HOME": str(home)})
            assert proc.returncode == 1
            out = json.loads(proc.stdout)
            assert {item["path"] for item in out["conflicts"]} == {str(link)}
            assert link.resolve() == foreign
            for safe_name in set(HOST_SKILLS[host]) - {name}:
                assert (home / host_dir / "skills" / safe_name).is_symlink()


def test_setup_preflights_non_directory_parent(tmp_path):
    home = tmp_path / "fakehome"
    home.mkdir()
    (home / ".agents").write_text("not-a-directory", encoding="utf-8")

    proc = _run(["setup"], env={"HOME": str(home)})
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert all("parent is not a directory" in item["reason"] for item in out["conflicts"])
    assert (home / ".claude" / "skills" / "marshal").is_symlink()


def _old_checkout(root: Path, host_dir: str, name: str, project_name="marshal") -> Path:
    skill = root / host_dir / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: old\n---\n", encoding="utf-8"
    )
    (root / "src" / "marshal_core").mkdir(parents=True)
    (root / "src" / "marshal_core" / "cli.py").write_text("", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{project_name}"\n', encoding="utf-8"
    )
    return skill


def test_setup_migrates_all_live_links_from_recognizable_old_checkout(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    for host, host_dir in (("claude", ".claude"), ("codex", ".agents")):
        for name in HOST_SKILLS[host]:
            case = tmp_path / f"{host}-{name}"
            home = case / "home"
            old_skill = _old_checkout(case / "old-marshal", host_dir, name)
            link = home / host_dir / "skills" / name
            link.parent.mkdir(parents=True)
            link.symlink_to(old_skill, target_is_directory=True)

            proc = _run(["setup", "--host", host], env={"HOME": str(home)})
            assert proc.returncode == 0, proc.stderr
            out = json.loads(proc.stdout)
            migrated = next(item for item in out["installed"] if item["name"] == name)
            assert migrated["status"] == "migrated"
            assert link.resolve() == repo_root / host_dir / "skills" / name


def test_setup_rejects_foreign_checkout_that_only_looks_like_marshal(tmp_path):
    home = tmp_path / "home"
    foreign_skill = _old_checkout(
        tmp_path / "lookalike", ".agents", "marshal", project_name="not-marshal"
    )
    link = home / ".agents" / "skills" / "marshal"
    link.parent.mkdir(parents=True)
    link.symlink_to(foreign_skill, target_is_directory=True)

    proc = _run(["setup", "--host", "codex"], env={"HOME": str(home)})
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert {item["path"] for item in out["conflicts"]} == {str(link)}
    assert link.resolve() == foreign_skill


def test_setup_rejects_foreign_checkout_with_non_table_project_metadata(tmp_path):
    home = tmp_path / "home"
    foreign_skill = _old_checkout(tmp_path / "lookalike", ".agents", "marshal")
    (tmp_path / "lookalike" / "pyproject.toml").write_text(
        'project = "marshal"\n', encoding="utf-8"
    )
    link = home / ".agents" / "skills" / "marshal"
    link.parent.mkdir(parents=True)
    link.symlink_to(foreign_skill, target_is_directory=True)

    proc = _run(["setup", "--host", "codex"], env={"HOME": str(home)})
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert {item["path"] for item in out["conflicts"]} == {str(link)}
    assert {item["name"] for item in out["installed"]} == {
        "onboard", "plan-cost", "marshal-pr-sweep"
    }
    assert link.resolve() == foreign_skill


def test_setup_migration_error_does_not_abort_later_safe_destinations(
    tmp_path, monkeypatch, capsys
):
    from marshal_core import cli

    home = tmp_path / "home"
    old_skill = _old_checkout(tmp_path / "old", ".agents", "marshal")
    link = home / ".agents" / "skills" / "marshal"
    link.parent.mkdir(parents=True)
    link.symlink_to(old_skill, target_is_directory=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        cli,
        "_replace_skill_link",
        lambda *_: (_ for _ in ()).throw(OSError("migration denied")),
    )
    args = cli.build_parser().parse_args(["setup", "--host", "codex"])

    assert args.func(args) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["errors"][0]["name"] == "marshal"
    assert {
        item["name"] for item in out["installed"]
    } == {"onboard", "plan-cost", "marshal-pr-sweep"}
    assert link.resolve() == old_skill


def test_setup_serializes_concurrent_writers(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    command = [sys.executable, "-m", "marshal_core.cli", "setup", "--host", "codex"]
    env = {**os.environ, "HOME": str(home)}
    writers = [
        subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=Path(__file__).resolve().parents[1],
        )
        for _ in range(4)
    ]
    results = [proc.communicate(timeout=10) for proc in writers]
    for proc, (stdout, stderr) in zip(writers, results, strict=True):
        assert proc.returncode == 0, stderr
        assert json.loads(stdout)["ok"] is True
    assert all(
        (home / ".agents" / "skills" / name).is_symlink()
        for name in HOST_SKILLS["codex"]
    )
    assert not list((home / ".agents" / "skills").glob(".*.marshal-*"))


def test_setup_lock_requests_exclusive_posix_lock(tmp_path, monkeypatch):
    if os.name == "nt":
        return
    import fcntl

    from marshal_core import cli

    operations = []
    monkeypatch.setattr(fcntl, "flock", lambda _fd, operation: operations.append(operation))

    with cli._setup_lock(tmp_path):
        assert operations == [fcntl.LOCK_EX]
    assert operations == [fcntl.LOCK_EX, fcntl.LOCK_UN]


def test_worktree_diff_covers_committed_staged_unstaged_and_untracked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    git("init")
    git("config", "user.email", "marshal@example.test")
    git("config", "user.name", "Marshal Test")
    for name in ("committed.txt", "staged.txt", "unstaged.txt"):
        (repo / name).write_text("base\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/master", base)

    (repo / "committed.txt").write_text("committed-change\n", encoding="utf-8")
    git("add", "committed.txt")
    git("commit", "-m", "committed change")
    (repo / "staged.txt").write_text("staged-change\n", encoding="utf-8")
    git("add", "staged.txt")
    (repo / "unstaged.txt").write_text("unstaged-change\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("untracked-change\n", encoding="utf-8")

    proc = _run(["worktree-diff", "--repo-root", str(repo)])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["base"] == base
    assert out["base_source"] == "origin/master"
    assert set(out["paths"]) == {
        "committed.txt",
        "staged.txt",
        "unstaged.txt",
        "untracked.txt",
    }
    assert out["untracked_paths"] == ["untracked.txt"]
    assert out["dirty"] is True
    assert out["invariant_checkout"] == "worktree"
    assert out["change_ref"].endswith("+worktree")
    for content in (
        "committed-change",
        "staged-change",
        "unstaged-change",
        "untracked-change",
    ):
        assert content in out["diff_text"]


def test_worktree_diff_requires_explicit_base_when_none_is_discoverable(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init")
    git("config", "user.email", "marshal@example.test")
    git("config", "user.name", "Marshal Test")
    (repo / "change.txt").write_text("base\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")
    (repo / "change.txt").write_text("committed-change\n", encoding="utf-8")
    git("commit", "-am", "feature change")

    proc = _run(["worktree-diff", "--repo-root", str(repo)])
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert "cannot determine review base" in out["error"]


def test_review_lenses_empty_ratchet_history_is_not_degraded(tmp_path):
    proc = _run(
        [
            "review-lenses",
            "--repo",
            "node",
            "--paths",
            "README.md",
            "--ratchet-top",
            "2",
        ],
        env={"MARSHAL_DB": f"sqlite:///{tmp_path / 'empty.db'}"},
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ratchet"] == []
    assert "ratchet_note" in out
    assert "degraded" not in out
