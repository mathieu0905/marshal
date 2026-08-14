import json
import os
import subprocess
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.knowledge.models import Base, Meta
from marshal_core.knowledge.store import Store

ROOT = os.path.dirname(os.path.dirname(__file__))


def _session(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_meta_model_roundtrips(tmp_path):
    s = _session(tmp_path / "m.db")
    s.add(Meta(key="snapshot_version", value="1.2.3"))
    s.commit()
    got = s.get(Meta, "snapshot_version")
    assert got.value == "1.2.3"


def _seed_source(path):
    """A snapshot-shaped db with 1 invariant + 1 escape + 1 gate_run."""
    s = _session(path)
    st = Store(s)
    st.register_invariant(
        id="econ.fee_conservation", domain_pack="cowboy", domain="econ",
        spec_ref="CIP-3", executor_kind="proptest", location_repo="node",
        location_path="execution/src/x.rs", location_test="prop_fee", severity="high")
    st.open_escape(id="esc-1", description="d", root_cause_class="c", change_ref=None)
    st.record_gate_run(change_ref="src-ref", job_id="src-ref", verdict="pass", evidence={})
    return s


def test_seed_replaces_authoritative_preserves_local(tmp_path):
    src = _seed_source(tmp_path / "snap.db")

    tgt = _session(tmp_path / "user.db")
    tgt_store = Store(tgt)
    # 本地已有一条 gate_run(队友自己跑过的门禁),seed 必须保留它。
    tgt_store.record_gate_run(change_ref="local-ref", job_id="local-ref",
                              verdict="block", evidence={})
    tgt.commit()

    n_inv, n_esc = tgt_store.seed_authoritative_tables(src)
    tgt.commit()
    assert (n_inv, n_esc) == (1, 1)

    from marshal_core.knowledge.models import InvariantRegistry, EscapeRegistry, GateRun
    assert tgt.get(InvariantRegistry, "econ.fee_conservation") is not None
    assert tgt.get(EscapeRegistry, "esc-1") is not None
    # 本地 gate_run 原样保留,且没把 source 的 gate_run 带进来。
    refs = {g.change_ref for g in tgt.query(GateRun).all()}
    assert refs == {"local-ref"}


def test_meta_get_set(tmp_path):
    s = _session(tmp_path / "v.db")
    st = Store(s)
    assert st.get_meta("snapshot_version") is None
    st.set_meta("snapshot_version", "0.0.1")
    s.commit()
    assert st.get_meta("snapshot_version") == "0.0.1"


def _cli(args, env):
    e = dict(os.environ)
    e.update(env)
    return subprocess.run([sys.executable, "-m", "marshal_core.cli", *args],
                          capture_output=True, text=True, env=e, cwd=ROOT)


def test_cli_seed_idempotent_and_version_gated(tmp_path):
    snap = tmp_path / "snap.db"
    _seed_source(snap).close()
    user = tmp_path / "user.db"
    env = {"MARSHAL_DB": f"sqlite:///{user}"}

    p1 = _cli(["seed", "--snapshot", str(snap), "--version", "0.0.1"], env)
    assert p1.returncode == 0, p1.stderr
    out1 = json.loads(p1.stdout)
    assert out1["seeded"] is True and out1["invariants"] == 1 and out1["escapes"] == 1

    # 同版本再 seed → no-op
    p2 = _cli(["seed", "--snapshot", str(snap), "--version", "0.0.1"], env)
    out2 = json.loads(p2.stdout)
    assert out2["seeded"] is False

    # 版本 bump → 重新 seed
    p3 = _cli(["seed", "--snapshot", str(snap), "--version", "0.0.2"], env)
    assert json.loads(p3.stdout)["seeded"] is True


def test_seed_from_snapshot_predating_introduced_at_ts(tmp_path):
    # Regression: a snapshot created before the introduced_at_ts column must still
    # seed cleanly. Without ensure_schema on the source engine, the ORM read of
    # EscapeRegistry raises OperationalError (no such column).
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from marshal_core.knowledge.models import Base, ensure_schema
    from marshal_core.knowledge.store import Store

    src_path = tmp_path / "old_snapshot.db"
    src_eng = create_engine(f"sqlite:///{src_path}")
    # hand-build an escape_registry WITHOUT introduced_at_ts (the pre-migration shape)
    with src_eng.begin() as c:
        c.execute(text(
            "CREATE TABLE escape_registry (id VARCHAR PRIMARY KEY, domain_pack VARCHAR, "
            "discovered_at DATETIME, introduced_at VARCHAR, root_cause_class VARCHAR, "
            "change_ref VARCHAR, description VARCHAR, postmortem_ref VARCHAR, "
            "spawned_check VARCHAR, status VARCHAR)"))
        c.execute(text("INSERT INTO escape_registry (id, domain_pack, status) "
                       "VALUES ('e-old', 'cowboy', 'closed')"))
        c.execute(text("CREATE TABLE invariant_registry (id VARCHAR PRIMARY KEY, "
                       "domain_pack VARCHAR, domain VARCHAR, spec_ref VARCHAR, "
                       "executor_kind VARCHAR, location_repo VARCHAR, location_path VARCHAR, "
                       "location_test VARCHAR, severity VARCHAR, status VARCHAR, "
                       "origin VARCHAR, escape_id VARCHAR)"))

    ensure_schema(src_eng)   # the fix: migrate the pre-column snapshot before ORM read

    dest_eng = create_engine(f"sqlite:///{tmp_path}/dest.db")
    ensure_schema(dest_eng)
    with sessionmaker(bind=dest_eng)() as dest_s, sessionmaker(bind=src_eng)() as src_s:
        n_inv, n_esc = Store(dest_s).seed_authoritative_tables(src_s)
    assert n_esc == 1   # the legacy escape transferred without an OperationalError
