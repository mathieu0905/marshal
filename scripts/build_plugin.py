#!/usr/bin/env python3
"""发版打包:从根 marshal.db 导出权威两表为只读快照,并把 src/ 包同步进 plugin。"""
import argparse
import os
import shutil
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 让脚本能 import marshal_core(repo 用 src 布局)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from marshal_core.knowledge.models import Base, InvariantRegistry, EscapeRegistry  # noqa: E402
from marshal_core.knowledge.store import Store  # noqa: E402


def _session(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def export_snapshot(source_db: str, out_path: str, version: str) -> tuple[int, int]:
    """把 source_db 的 invariant_registry + escape_registry 复制进全新 out_path,
    写入 meta snapshot_version=version;不带 gate_run/audit_log。返回 (n_inv, n_esc)。"""
    if os.path.exists(out_path):
        os.remove(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    src = _session(source_db)
    out = _session(out_path)
    try:
        store = Store(out)
        n_inv = store._replace_table(src, InvariantRegistry)
        n_esc = store._replace_table(src, EscapeRegistry)
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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="build_plugin")
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    p.add_argument("--source-db", default=os.path.join(repo, "marshal.db"))
    p.add_argument("--version", required=True)
    p.add_argument("--out",
                   default=os.path.join(repo, "plugins", "marshal", "data",
                                        "marshal.snapshot.db"))
    a = p.parse_args(argv)
    n_inv, n_esc = export_snapshot(a.source_db, a.out, a.version)
    print(f"snapshot: {n_inv} invariants, {n_esc} escapes -> {a.out}")
    pkgs = sync_packages(os.path.join(repo, "src"),
                         os.path.join(repo, "plugins", "marshal"))
    print(f"synced packages: {', '.join(pkgs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
