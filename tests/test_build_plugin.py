import json as _json
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


def test_manifests_are_valid_and_consistent():
    mp = _json.load(open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")))
    assert mp["name"] and isinstance(mp["plugins"], list)
    names = [p["name"] for p in mp["plugins"]]
    assert "marshal" in names

    pj = _json.load(open(os.path.join(
        ROOT, "plugins", "marshal", ".claude-plugin", "plugin.json")))
    assert pj["name"] == "marshal" and pj["version"]

    pp = open(os.path.join(ROOT, "plugins", "marshal", "pyproject.toml")).read()
    assert "sqlalchemy" in pp and "pydantic" in pp
    assert "fastapi" not in pp and "uvicorn" not in pp  # 服务端依赖不进消费侧


def test_build_plugin_default_version_from_manifest(tmp_path):
    # main() 不传 --version 时,应从 plugins/marshal/.claude-plugin/plugin.json 取。
    src = _session(tmp_path / "root.db")
    Store(src).register_invariant(
        id="econ.fee_conservation", domain_pack="cowboy", domain="econ",
        spec_ref="CIP-3", executor_kind="proptest", location_repo="node",
        location_path="x.rs", location_test="prop_fee", severity="high")
    src.commit()
    src.close()
    out = tmp_path / "snap.db"
    rc = build_plugin.main([
        "--source-db", str(tmp_path / "root.db"), "--out", str(out),
        "--no-validate"])
    assert rc == 0
    pj = _json.load(open(os.path.join(
        ROOT, "plugins", "marshal", ".claude-plugin", "plugin.json")))
    assert Store(_session(out)).get_meta("snapshot_version") == pj["version"]


def test_validate_bundle_skips_when_uv_absent(tmp_path, monkeypatch):
    # No uv on PATH → returns "skipped", does not raise.
    plugin_dir = tmp_path / "plugins" / "marshal"
    plugin_dir.mkdir(parents=True)
    monkeypatch.setenv("PATH", str(tmp_path / "empty_bin"))  # nothing here
    assert build_plugin.validate_bundle(str(plugin_dir)) == "skipped"


def test_validate_bundle_ok_with_stub_uv(tmp_path, monkeypatch):
    # Stub `uv` on PATH that emits classify-shaped JSON with a tier → returns "ok".
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    (fakebin / "uv").write_text(
        "#!/usr/bin/env bash\n"
        'echo \'{"tier":"high","review_dimensions":[]}\'\n'
        "exit 0\n")
    (fakebin / "uv").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fakebin}:/usr/bin:/bin")
    plugin_dir = tmp_path / "plugins" / "marshal"
    plugin_dir.mkdir(parents=True)
    assert build_plugin.validate_bundle(str(plugin_dir)) == "ok"


def test_validate_bundle_raises_on_bad_cli(tmp_path, monkeypatch):
    # Stub `uv` that exits nonzero → must raise (real drift/regression).
    fakebin = tmp_path / "bin2"
    fakebin.mkdir()
    (fakebin / "uv").write_text(
        "#!/usr/bin/env bash\n"
        'echo \'{"error":"ModuleNotFoundError: pydantic"}\'\n'
        "exit 1\n")
    (fakebin / "uv").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fakebin}:/usr/bin:/bin")
    plugin_dir = tmp_path / "plugins" / "marshal"
    plugin_dir.mkdir(parents=True)
    import pytest
    with pytest.raises(RuntimeError):
        build_plugin.validate_bundle(str(plugin_dir))
