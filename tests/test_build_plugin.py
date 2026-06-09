import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.knowledge.models import Base, InvariantRegistry, EscapeRegistry, GateRun, Meta  # noqa: F401
from marshal_core.knowledge.store import Store

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_plugin  # noqa: E402


def _session(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_export_snapshot_only_authoritative_tables(tmp_path):
    src = _session(tmp_path / "root.db")
    st = Store(src)
    st.register_invariant(
        id="econ.fee_conservation", domain_pack="cowboy", domain="econ",
        spec_ref="CIP-3", executor_kind="proptest", location_repo="node",
        location_path="x.rs", location_test="prop_fee", severity="high")
    st.open_escape(id="esc-1", description="d", root_cause_class="c", change_ref=None)
    st.record_gate_run(change_ref="r", job_id="r", verdict="pass", evidence={})
    src.commit()
    src.close()

    out = tmp_path / "snap.db"
    n_inv, n_esc = build_plugin.export_snapshot(
        str(tmp_path / "root.db"), str(out), version="0.0.1")
    assert (n_inv, n_esc) == (1, 1)

    chk = _session(out)
    assert chk.get(InvariantRegistry, "econ.fee_conservation") is not None
    assert chk.get(EscapeRegistry, "esc-1") is not None
    # 快照不含任何 gate_run(只发权威两表)
    assert chk.query(GateRun).count() == 0
    # 版本标记写入快照
    assert Store(chk).get_meta("snapshot_version") == "0.0.1"


def test_sync_packages_copies_core_and_pack(tmp_path):
    plugin_dir = tmp_path / "plugins" / "marshal"
    plugin_dir.mkdir(parents=True)
    build_plugin.sync_packages(os.path.join(ROOT, "src"), str(plugin_dir))
    assert (plugin_dir / "marshal_core" / "cli.py").exists()
    assert (plugin_dir / "marshal_pack_cowboy" / "pack.py").exists()
    # 重跑应幂等(先清旧目录),不报错
    build_plugin.sync_packages(os.path.join(ROOT, "src"), str(plugin_dir))
    assert (plugin_dir / "marshal_core" / "cli.py").exists()
