import os
from pathlib import Path
import subprocess
import textwrap

import yaml


ROOT = Path(__file__).resolve().parents[1]
SHARED_SKILLS = ("marshal", "onboard", "plan-cost")
CODEX_SKILLS = (*SHARED_SKILLS, "marshal-pr-sweep")
HOST_SKILLS = {".claude": SHARED_SKILLS, ".agents": CODEX_SKILLS}
SKILLS = SHARED_SKILLS


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


def _bootstrap(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    raw = text.split("# marshal-bootstrap:start", 1)[1]
    raw = raw.split("# marshal-bootstrap:end", 1)[0]
    return textwrap.dedent(raw)


def _run_bootstrap(path: Path, *, home: Path, cwd: Path, extra_env=None):
    env = {**os.environ, "HOME": str(home)}
    env.pop("MARSHAL_HOME", None)
    env.pop("MARSHAL_PYTHON", None)
    if extra_env:
        env.update(extra_env)
    script = "set -eu\n" + _bootstrap(path) + '\nprintf "%s\\n" "$PY"\n'
    return subprocess.run(
        ["sh", "-c", script],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


def test_both_hosts_publish_the_complete_skill_surface():
    for host_dir, names in HOST_SKILLS.items():
        for name in names:
            path = ROOT / host_dir / "skills" / name / "SKILL.md"
            assert path.is_file(), path
            metadata = _frontmatter(path)
            assert metadata["name"] == name
            assert metadata["description"]


def test_codex_marshal_skill_uses_codex_invocation_and_orchestration():
    skill = (ROOT / ".agents/skills/marshal/SKILL.md").read_text(encoding="utf-8")
    review = (
        ROOT / ".agents/skills/marshal/references/review-orchestration.md"
    ).read_text(encoding="utf-8")
    deep = ROOT / ".agents/skills/marshal/references/deep-review-flow.md"

    assert "$marshal" in skill
    assert "subagent" in skill
    assert "/code-review ultra" not in skill
    assert "/code-review ultra" not in review
    assert "--proximity 10" in review
    assert "refute-lenses" in review
    assert "- $marshal deep →" in skill
    assert deep.is_file()
    assert not any(
        "/code-review ultra" in path.read_text(encoding="utf-8")
        for path in (ROOT / ".agents/skills").rglob("*.md")
    )


def test_claude_skill_surface_remains_slash_based():
    for name in SHARED_SKILLS:
        skill = (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert f"/{name}" in skill
    marshal = (ROOT / ".claude/skills/marshal/SKILL.md").read_text(encoding="utf-8")
    assert "- `/marshal deep` →" in marshal


def test_skills_resolve_checkout_instead_of_using_a_machine_path():
    for host_dir, names in HOST_SKILLS.items():
        for name in names:
            skill = (ROOT / host_dir / "skills" / name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            assert "/home/ubuntu/workspace/marshal" not in skill
            assert "SKILL_DIR" in skill
            assert "MARSHAL_PYTHON" in skill
            assert "marshal-bootstrap:start" in skill


def test_codex_pr_sweep_is_native_and_does_not_modify_claude_surface():
    sweep = ROOT / ".agents/skills/marshal-pr-sweep"
    skill = (sweep / "SKILL.md").read_text(encoding="utf-8")
    runner = (sweep / "scripts/run_sweep.sh").read_text(encoding="utf-8")

    assert "$marshal-pr-sweep" in skill
    assert "$marshal deep <repo> <pr>" in skill
    assert "references/deep-review-flow.md" in skill
    assert "marker_author" not in skill
    assert '"$CODEX_BIN" exec' in runner
    assert "approval_policy=\"never\"" in runner
    assert "--yolo" not in runner
    assert "claude -p" not in runner
    assert not (ROOT / ".claude/skills/marshal-pr-sweep").exists()


def test_all_skill_bootstraps_resolve_installed_symlink_under_set_e(tmp_path):
    cwd = tmp_path / "unrelated"
    cwd.mkdir()
    for host_dir in (".claude", ".agents"):
        for name in SKILLS:
            home = tmp_path / f"{host_dir[1:]}-{name}"
            link = home / host_dir / "skills" / name
            link.parent.mkdir(parents=True)
            source = ROOT / host_dir / "skills" / name
            link.symlink_to(source, target_is_directory=True)
            proc = _run_bootstrap(source / "SKILL.md", home=home, cwd=cwd)
            assert proc.returncode == 0, proc.stderr
            assert proc.stdout.strip() == str(ROOT / ".venv/bin/python")


def test_all_skill_bootstraps_honor_python_and_home_overrides(tmp_path):
    for host_dir in (".claude", ".agents"):
        for name in SKILLS:
            skill = ROOT / host_dir / "skills" / name / "SKILL.md"
            python_proc = _run_bootstrap(
                skill,
                home=tmp_path / "empty-home",
                cwd=tmp_path,
                extra_env={"MARSHAL_PYTHON": "/opt/marshal/python"},
            )
            assert python_proc.returncode == 0, python_proc.stderr
            assert python_proc.stdout.strip() == "/opt/marshal/python"

            explicit_home = tmp_path / f"explicit-{host_dir[1:]}-{name}"
            home_proc = _run_bootstrap(
                skill,
                home=tmp_path / "empty-home",
                cwd=tmp_path,
                extra_env={"MARSHAL_HOME": str(explicit_home)},
            )
            assert home_proc.returncode == 0, home_proc.stderr
            assert home_proc.stdout.strip() == str(explicit_home / ".venv/bin/python")

            both_proc = _run_bootstrap(
                skill,
                home=tmp_path / "empty-home",
                cwd=tmp_path,
                extra_env={
                    "MARSHAL_PYTHON": "/opt/marshal/python",
                    "MARSHAL_HOME": str(explicit_home),
                },
            )
            assert both_proc.returncode == 0, both_proc.stderr
            assert both_proc.stdout.strip() == "/opt/marshal/python"


def test_sweep_bootstrap_resolves_link_and_override_priority(tmp_path):
    skill = ROOT / ".agents/skills/marshal-pr-sweep/SKILL.md"
    home = tmp_path / "home"
    link = home / ".agents/skills/marshal-pr-sweep"
    link.parent.mkdir(parents=True)
    link.symlink_to(skill.parent, target_is_directory=True)
    cwd = tmp_path / "unrelated"
    cwd.mkdir()

    linked = _run_bootstrap(skill, home=home, cwd=cwd)
    assert linked.returncode == 0, linked.stderr
    assert linked.stdout.strip() == str(ROOT / ".venv/bin/python")

    overridden = _run_bootstrap(
        skill,
        home=tmp_path / "empty-home",
        cwd=tmp_path,
        extra_env={
            "MARSHAL_HOME": str(ROOT),
            "MARSHAL_PYTHON": "/opt/marshal/python",
        },
    )
    assert overridden.returncode == 0, overridden.stderr
    assert overridden.stdout.strip() == "/opt/marshal/python"


def test_repo_skill_checkout_wins_over_an_older_global_link(tmp_path):
    for host_dir in (".claude", ".agents"):
        for name in SKILLS:
            home = tmp_path / f"home-{host_dir[1:]}-{name}"
            old_skill = tmp_path / f"old-{host_dir[1:]}-{name}" / host_dir / "skills" / name
            old_skill.mkdir(parents=True)
            link = home / host_dir / "skills" / name
            link.parent.mkdir(parents=True)
            link.symlink_to(old_skill, target_is_directory=True)
            skill = ROOT / host_dir / "skills" / name / "SKILL.md"

            proc = _run_bootstrap(skill, home=home, cwd=ROOT)
            assert proc.returncode == 0, proc.stderr
            assert proc.stdout.strip() == str(ROOT / ".venv/bin/python")


def test_copied_skill_fails_cleanly_instead_of_treating_home_as_checkout(tmp_path):
    home = tmp_path / "home"
    copied = home / ".agents/skills/marshal"
    copied.mkdir(parents=True)
    (copied / "SKILL.md").write_text("copied", encoding="utf-8")
    skill = ROOT / ".agents/skills/marshal/SKILL.md"
    proc = _run_bootstrap(skill, home=home, cwd=tmp_path)
    assert proc.returncode == 1
    assert "Marshal checkout not found" in proc.stderr


def test_local_deep_docs_include_dirty_and_untracked_worktree_inputs():
    for host_dir, invocation in ((".agents", "$marshal deep"), (".claude", "/marshal deep")):
        gate = (
            ROOT / host_dir / "skills/marshal/references/gate-flow.md"
        ).read_text(encoding="utf-8")
        assert invocation in gate
        assert "marshal_core.cli worktree-diff" in gate
        assert "`invariant_checkout`" in gate
        assert "`dirty-worktree`" in gate
        assert "不得 detach HEAD 后测试旧代码" in gate


def test_both_deep_flows_define_low_tier_fallback_lenses():
    for host_dir in (".claude", ".agents"):
        deep = (
            ROOT / host_dir / "skills/marshal/references/deep-review-flow.md"
        ).read_text(encoding="utf-8")
        assert "correctness" in deep
        assert "spec" in deep
        assert "test-validity" in deep
        assert "fallback" in deep


def test_readme_documents_executable_codex_mcp_command():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "codex mcp add marshal-plan-gate --" in readme
    assert "[mcp_servers.marshal-plan-gate]" in readme
    assert "$marshal-pr-sweep" in readme
    assert "~/.agents/skills/marshal-pr-sweep/scripts/run_sweep.sh" in readme
