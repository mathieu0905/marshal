from marshal_core.onboard.detect import detect_repo


def _mk(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct GasReport {}\n")
    (repo / "execution" / "src" / "basefee.rs").write_text("pub const X: u64 = 1;\n")
    (repo / "docs" / "cip-3.md").write_text("# CIP-3\n")
    (repo / "README.md").write_text("# node\n")
    (repo / "CODEOWNERS").write_text("execution/ @alice\n")
    return repo


def test_detect_profile_and_seeds(tmp_path):
    brief = detect_repo(str(_mk(tmp_path)))
    assert brief["languages"].get("rust", 0) >= 2            # 2 个 .rs
    assert "README.md" in [d["path"] for d in brief["doc_inventory"]]
    assert any("cip-3.md" in d["path"] for d in brief["doc_inventory"])
    # 模块图: execution 是一个候选顶层模块
    assert any("execution" in m for m in brief["module_map"])
    # 候选概念种子来自模块/目录名(不是概念定义, 只是起点)
    assert "execution" in brief["candidate_seeds"]
    assert brief["has_codeowners"] is True


def test_detect_empty_repo_is_honest(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    brief = detect_repo(str(empty))
    assert brief["languages"] == {}
    assert brief["candidate_seeds"] == []
    assert brief["doc_inventory"] == []


def test_detect_excludes_vendored(tmp_path):
    """真 repo 画像不能被 target/.venv/node_modules 里的依赖代码淹没。"""
    repo = _mk(tmp_path)
    (repo / "target" / "debug").mkdir(parents=True)
    (repo / "target" / "debug" / "dep.rs").write_text("pub struct Dep {}\n")
    (repo / "node_modules" / "x").mkdir(parents=True)
    (repo / "node_modules" / "x" / "y.js").write_text("var z=1\n")
    brief = detect_repo(str(repo))
    assert "target" not in brief["candidate_seeds"]
    assert "node_modules" not in brief["candidate_seeds"]
    assert brief["languages"].get("js", 0) == 0        # vendored js 不计入
