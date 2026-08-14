#!/usr/bin/env python3
"""发版打包:从根 marshal.db 导出权威两表为只读快照,并把 src/ 包同步进 plugin。"""
import argparse
import os
import shutil
import subprocess
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 让脚本能 import marshal_core(repo 用 src 布局)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from marshal_core.knowledge.models import ensure_schema, InvariantRegistry, EscapeRegistry  # noqa: E402
from marshal_core.knowledge.store import Store  # noqa: E402


def _session(path):
    engine = create_engine(f"sqlite:///{path}")
    ensure_schema(engine)   # migrate a pre-existing source db before ORM read
    return sessionmaker(bind=engine)()


def export_snapshot(source_db: str, out_path: str, version: str,
                    allow_empty: bool = False) -> tuple[int, int]:
    """把 source_db 的 invariant_registry + escape_registry 复制进全新 out_path,
    写入 meta snapshot_version=version;不带 gate_run/audit_log。返回 (n_inv, n_esc)。
    若 invariant 数为 0 且未设 allow_empty=True,则 raise ValueError(防止空快照发布)。"""
    if os.path.exists(out_path):
        os.remove(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    src = _session(source_db)
    out = _session(out_path)
    try:
        store = Store(out)
        n_inv = store._replace_table(src, InvariantRegistry)
        n_esc = store._replace_table(src, EscapeRegistry)
        if n_inv == 0 and not allow_empty:
            raise ValueError(
                f"refusing to write empty snapshot (0 invariants) from {source_db}; "
                f"source db may be corrupt/wrong. Pass allow_empty=True to override.")
        store.set_meta("snapshot_version", version)
        out.commit()
        return n_inv, n_esc
    finally:
        src.close()
        out.close()


_PACKAGES = ("marshal_core", "marshal_pack_cowboy")


def sync_packages(src_dir: str, plugin_dir: str) -> list[str]:
    """把 src/ 下的消费侧包覆盖同步进 plugin_dir(先删后拷,幂等)。返回同步的包名。"""
    done = []
    for pkg in _PACKAGES:
        dst = os.path.join(plugin_dir, pkg)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(os.path.join(src_dir, pkg), dst,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        done.append(pkg)
    return done


def _manifest_version(repo: str) -> str:
    import json
    pj = os.path.join(repo, "plugins", "marshal", ".claude-plugin", "plugin.json")
    with open(pj) as fh:
        return json.load(fh)["version"]


def sync_references(repo: str) -> None:
    src = os.path.join(repo, ".claude", "skills", "marshal", "references")
    dst = os.path.join(repo, "plugins", "marshal", "skills", "marshal", "references")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    if os.path.isdir(src):
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def validate_bundle(plugin_dir: str) -> str:
    """冒烟:用 uv 跑一次 bundled CLI 的 classify,确认精简依赖足够。
    uv 不在 PATH → 跳过(返回 'skipped',告警但不失败);
    跑通且输出含 tier → 'ok';退出非零或缺 tier → raise(真漂移)。"""
    if shutil.which("uv") is None:
        print("validate: skipped (uv not found on PATH; bundle not smoke-tested)")
        return "skipped"
    proc = subprocess.run(
        ["uv", "run", "--project", plugin_dir, "-m", "marshal_core.cli",
         "classify", "--repo", "node", "--paths", "README.md"],
        capture_output=True, text=True)
    if proc.returncode != 0 or '"tier"' not in proc.stdout:
        raise RuntimeError(
            f"bundle smoke test FAILED (consumer deps may be incomplete):\n"
            f"  exit={proc.returncode}\n  stdout={proc.stdout.strip()}\n"
            f"  stderr={proc.stderr.strip()}")
    print("validate: ok (bundled CLI ran under trimmed deps)")
    return "ok"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="build_plugin")
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    p.add_argument("--source-db", default=os.path.join(repo, "marshal.db"))
    p.add_argument("--version", default=None)
    p.add_argument("--out",
                   default=os.path.join(repo, "plugins", "marshal", "data",
                                        "marshal.snapshot.db"))
    p.add_argument("--no-validate", action="store_true",
                   help="skip the uv smoke test of the bundled consumer CLI")
    p.add_argument("--allow-empty", action="store_true",
                   help="permit a 0-invariant snapshot (use only intentionally)")
    a = p.parse_args(argv)
    version = a.version or _manifest_version(repo)
    n_inv, n_esc = export_snapshot(a.source_db, a.out, version, allow_empty=a.allow_empty)
    print(f"snapshot v{version}: {n_inv} invariants, {n_esc} escapes -> {a.out}")
    pkgs = sync_packages(os.path.join(repo, "src"),
                         os.path.join(repo, "plugins", "marshal"))
    print(f"synced packages: {', '.join(pkgs)}")
    sync_references(repo)
    print("synced references")
    if not a.no_validate:
        validate_bundle(os.path.join(repo, "plugins", "marshal"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
