# Marshal 消费侧 Plugin 分发 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 marshal 消费侧打成一个 Claude Code plugin + 内部 marketplace,经 GitHub 单向分发给异机团队;安装/首次运行自动检测并补齐 uv/环境/快照(`doctor --fix`),队友零手动依赖即可跑 `/marshal`。

**Architecture:** 核心仅**新增**一个幂等 `cli seed` 命令(把快照里的不变量/逃逸两张权威表 seed 进用户可写 db,保留本地 `gate_run`/`audit_log`)+ 一个 `Meta` 版本标记表。其余全是 repo 内**新增的打包/分发资产**:`scripts/build_plugin.py`(同步包 + 导出快照)、`plugins/marshal/`(plugin 清单 + 消费侧 SKILL + `scripts/doctor.sh` 自体检自修复)、根 `.claude-plugin/marketplace.json`。现有 `src/` 命令、`.claude/skills/marshal` 软链、根 `marshal.db` 行为不变。

**Tech Stack:** Python 3.11+ / SQLAlchemy 2 / argparse(现有薄 CLI);pytest(现有测试);uv(消费端环境托管);bash(doctor.sh);Claude Code plugin/marketplace(`.claude-plugin/*.json` + `${CLAUDE_PLUGIN_ROOT}`)。

**Spec:** [`docs/superpowers/specs/2026-06-09-marshal-plugin-distribution-design.md`](../specs/2026-06-09-marshal-plugin-distribution-design.md)

---

## 文件结构

**核心改动(在 `src/`,会被打包脚本同步进 plugin):**
- Modify `src/marshal_core/knowledge/models.py` — 新增 `Meta(key,value)` 模型(版本标记)。
- Modify `src/marshal_core/knowledge/store.py` — 新增 `get_meta` / `set_meta` / `seed_authoritative_tables`。
- Modify `src/marshal_core/cli.py` — 新增 `cmd_seed` + `seed` 子命令。

**分发资产(repo 新增,不被同步):**
- Create `scripts/build_plugin.py` — `export_snapshot()` + `sync_packages()` + CLI 封装。
- Create `.claude-plugin/marketplace.json` — 内部 marketplace,列 1 个 plugin。
- Create `plugins/marshal/.claude-plugin/plugin.json` — plugin 清单 + version。
- Create `plugins/marshal/pyproject.toml` — 消费侧依赖(sqlalchemy+pydantic)。
- Create `plugins/marshal/skills/marshal/SKILL.md` — 消费侧 skill(预检走 doctor/uv,路径走 `${CLAUDE_PLUGIN_ROOT}`)。
- Create `plugins/marshal/scripts/doctor.sh` — 自体检 + 缺失自修复。
- Generated(由 build_plugin 产出,git 跟踪)`plugins/marshal/marshal_core/`、`plugins/marshal/marshal_pack_cowboy/`、`plugins/marshal/skills/marshal/references/`、`plugins/marshal/data/marshal.snapshot.db`。

**测试:**
- Create `tests/test_seed.py` — seed 幂等 + 保留本地表。
- Create `tests/test_build_plugin.py` — 导出快照只含两表 + 包同步。
- Create `tests/test_doctor.py` — doctor 检测/修复/硬阻断(stub installer,不连网)。

**约定:** 本机用现有 `.venv` 跑测试:`PY=.venv/bin/python`,`PYTEST="$PY -m pytest"`。提交前跑 `.venv/bin/ruff check src tests scripts`。

---

## Task 1: Meta 版本标记模型

**Files:**
- Modify: `src/marshal_core/knowledge/models.py`
- Test: `tests/test_seed.py`

- [ ] **Step 1: 写失败测试**(建新文件 `tests/test_seed.py`)

```python
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
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_seed.py::test_meta_model_roundtrips -v`
Expected: FAIL — `ImportError: cannot import name 'Meta'`

- [ ] **Step 3: 实现 Meta 模型**

在 `src/marshal_core/knowledge/models.py` 末尾追加:

```python
class Meta(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, default="")
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_seed.py::test_meta_model_roundtrips -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/marshal_core/knowledge/models.py tests/test_seed.py
git commit -m "feat(knowledge): add Meta key/value model for snapshot versioning"
```

---

## Task 2: Store seed/meta 方法

**Files:**
- Modify: `src/marshal_core/knowledge/store.py`
- Test: `tests/test_seed.py`

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_seed.py`)

```python
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
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_seed.py -k "seed_replaces or meta_get_set" -v`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'seed_authoritative_tables'`

- [ ] **Step 3: 实现 Store 方法**

在 `src/marshal_core/knowledge/store.py` 顶部 import 处补 `Meta`,并在 `Store` 类内追加:

```python
def get_meta(self, key: str, default: str | None = None) -> str | None:
    row = self.s.get(Meta, key)
    return row.value if row else default

def set_meta(self, key: str, value: str) -> None:
    row = self.s.get(Meta, key)
    if row:
        row.value = value
    else:
        self.s.add(Meta(key=key, value=value))

def seed_authoritative_tables(self, src_session) -> tuple[int, int]:
    """用 src_session(快照)里的两张权威表替换本会话的同名表;
    gate_run / audit_log 不动。返回 (写入不变量数, 写入逃逸数)。"""
    n_inv = self._replace_table(src_session, InvariantRegistry)
    n_esc = self._replace_table(src_session, EscapeRegistry)
    return n_inv, n_esc

def _replace_table(self, src_session, Model) -> int:
    self.s.query(Model).delete()
    rows = src_session.query(Model).all()
    for obj in rows:
        data = {c.name: getattr(obj, c.name) for c in Model.__table__.columns}
        self.s.add(Model(**data))
    return len(rows)
```

注意:`store.py` 现有以 `self.s = session` 持有会话(确认 `__init__` 里字段名;若是别的名,改 `self.s` 为实际名)。`import` 行需含 `InvariantRegistry, EscapeRegistry, Meta`。

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_seed.py -k "seed_replaces or meta_get_set" -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 提交**

```bash
git add src/marshal_core/knowledge/store.py tests/test_seed.py
git commit -m "feat(knowledge): seed_authoritative_tables + meta accessors"
```

---

## Task 3: `cli seed` 子命令

**Files:**
- Modify: `src/marshal_core/cli.py`
- Test: `tests/test_seed.py`

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_seed.py`)

```python
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
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_seed.py::test_cli_seed_idempotent_and_version_gated -v`
Expected: FAIL — `invalid choice: 'seed'`

- [ ] **Step 3: 实现 cmd_seed + 子命令**

在 `src/marshal_core/cli.py` 中,`cmd_metrics` 之后加:

```python
def cmd_seed(a) -> int:
    # doctor 末步:把快照两张权威表 seed 进用户可写 db(MARSHAL_DB),保留本地 gate_run。
    # 版本未变 → no-op。
    snap_path = Path(a.snapshot).resolve()
    if not snap_path.exists():
        return _fail(f"snapshot not found: {snap_path}")
    s = _session()
    try:
        store = Store(s)
        if store.get_meta("snapshot_version") == a.version:
            return _emit({"ok": True, "seeded": False, "version": a.version})
        src_engine = create_engine(f"sqlite:///{snap_path}")
        Base.metadata.create_all(src_engine)
        src = sessionmaker(bind=src_engine)()
        try:
            n_inv, n_esc = store.seed_authoritative_tables(src)
        finally:
            src.close()
        store.set_meta("snapshot_version", a.version)
        s.commit()
        return _emit({"ok": True, "seeded": True, "version": a.version,
                      "invariants": n_inv, "escapes": n_esc})
    finally:
        s.close()
```

在 `build_parser()` 内(`mt` 块之后、`st` 块之前)加:

```python
    sd = sub.add_parser("seed")
    sd.add_argument("--snapshot", required=True, help="path to marshal.snapshot.db")
    sd.add_argument("--version", required=True, help="snapshot version (= plugin version)")
    sd.set_defaults(func=cmd_seed)
```

(`create_engine` / `sessionmaker` / `Base` 已在文件顶部 import。)

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_seed.py -v`
Expected: PASS(全部 seed 测试通过)

- [ ] **Step 5: 回归 + 提交**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS(现有 CLI 测试不受影响)

```bash
git add src/marshal_core/cli.py tests/test_seed.py
git commit -m "feat(cli): add idempotent, version-gated 'seed' command"
```

---

## Task 4: 打包脚本 — 导出快照

**Files:**
- Create: `scripts/build_plugin.py`
- Test: `tests/test_build_plugin.py`

- [ ] **Step 1: 写失败测试**(建 `tests/test_build_plugin.py`)

```python
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.knowledge.models import Base, InvariantRegistry, EscapeRegistry, GateRun, Meta
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
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_build_plugin.py::test_export_snapshot_only_authoritative_tables -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_plugin'`

- [ ] **Step 3: 实现 export_snapshot**(建 `scripts/build_plugin.py`)

```python
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_build_plugin.py::test_export_snapshot_only_authoritative_tables -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add scripts/build_plugin.py tests/test_build_plugin.py
git commit -m "feat(build): export read-only invariant/escape snapshot with version"
```

---

## Task 5: 打包脚本 — 同步消费侧包

**Files:**
- Modify: `scripts/build_plugin.py`
- Test: `tests/test_build_plugin.py`

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_build_plugin.py`)

```python
def test_sync_packages_copies_core_and_pack(tmp_path):
    plugin_dir = tmp_path / "plugins" / "marshal"
    plugin_dir.mkdir(parents=True)
    build_plugin.sync_packages(os.path.join(ROOT, "src"), str(plugin_dir))
    assert (plugin_dir / "marshal_core" / "cli.py").exists()
    assert (plugin_dir / "marshal_pack_cowboy" / "pack.py").exists()
    # 重跑应幂等(先清旧目录),不报错
    build_plugin.sync_packages(os.path.join(ROOT, "src"), str(plugin_dir))
    assert (plugin_dir / "marshal_core" / "cli.py").exists()
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_build_plugin.py::test_sync_packages_copies_core_and_pack -v`
Expected: FAIL — `AttributeError: module 'build_plugin' has no attribute 'sync_packages'`

- [ ] **Step 3: 实现 sync_packages**(加到 `scripts/build_plugin.py`,`export_snapshot` 之后)

```python
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
```

并在 `main()` 的 `export_snapshot(...)` 之后、`return 0` 之前补:

```python
    pkgs = sync_packages(os.path.join(repo, "src"),
                         os.path.join(repo, "plugins", "marshal"))
    print(f"synced packages: {', '.join(pkgs)}")
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_build_plugin.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 提交**

```bash
git add scripts/build_plugin.py tests/test_build_plugin.py
git commit -m "feat(build): sync marshal_core + cowboy pack into plugin dir"
```

---

## Task 6: doctor.sh — 检测逻辑(JSON 输出)

**Files:**
- Create: `plugins/marshal/scripts/doctor.sh`
- Test: `tests/test_doctor.py`

doctor.sh 设计为**可测试**:用环境变量覆盖外部副作用,默认值才是真行为。
- `MARSHAL_UV_INSTALLER` — 覆盖 uv 安装命令(测试注入 stub,不连网)。
- 输出单行 JSON:`{"ok":bool,"blocked":[...],"fixed":[...],"checks":{...}}`。

- [ ] **Step 1: 写失败测试**(建 `tests/test_doctor.py`)

```python
import json
import os
import stat
import subprocess

ROOT = os.path.dirname(os.path.dirname(__file__))
DOCTOR = os.path.join(ROOT, "plugins", "marshal", "scripts", "doctor.sh")


def _run(env_overrides, plugin_root=None):
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root or os.path.join(ROOT, "plugins", "marshal")
    env.update(env_overrides)
    p = subprocess.run(["bash", DOCTOR, "--fix"], capture_output=True, text=True, env=env)
    return p


def test_doctor_blocks_when_plugin_root_missing(tmp_path):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    p = subprocess.run(["bash", DOCTOR, "--fix"], capture_output=True, text=True, env=env)
    out = json.loads(p.stdout)
    assert out["ok"] is False
    assert "CLAUDE_PLUGIN_ROOT" in out["blocked"]
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_doctor.py::test_doctor_blocks_when_plugin_root_missing -v`
Expected: FAIL — doctor.sh 不存在(`No such file`)

- [ ] **Step 3: 实现 doctor.sh 骨架(检测,暂不自修复 uv)**

创建 `plugins/marshal/scripts/doctor.sh`(`chmod +x`):

```bash
#!/usr/bin/env bash
# Marshal doctor —— 自体检 + 缺失自修复。输出单行 JSON,与 cwd 无关。
set -u
BLOCKED=()
FIXED=()

json_arr() {  # json_arr a b c -> ["a","b","c"];  无参 -> []
  local out="" x
  for x in "$@"; do out="$out\"$x\","; done
  printf '[%s]' "${out%,}"
}

emit() {  # emit <ok>。用 ${ARR[@]+...} 守卫,空数组在 set -u 下不报错且不产空元素。
  printf '{"ok":%s,"blocked":%s,"fixed":%s}\n' "$1" \
    "$(json_arr ${BLOCKED[@]+"${BLOCKED[@]}"})" \
    "$(json_arr ${FIXED[@]+"${FIXED[@]}"})"
}

# 1) CLAUDE_PLUGIN_ROOT 注入?(硬阻断)
if [ -z "${CLAUDE_PLUGIN_ROOT:-}" ] || [ ! -d "${CLAUDE_PLUGIN_ROOT:-/nonexistent}" ]; then
  BLOCKED+=("CLAUDE_PLUGIN_ROOT")
  emit false
  exit 0
fi
ROOT="$CLAUDE_PLUGIN_ROOT"

# 2) python3 >= 3.11?(硬阻断,不静默装系统 python)
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)' 2>/dev/null; then
  BLOCKED+=("python3>=3.11")
  emit false
  exit 0
fi

emit true
exit 0
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_doctor.py::test_doctor_blocks_when_plugin_root_missing -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
chmod +x plugins/marshal/scripts/doctor.sh
git add plugins/marshal/scripts/doctor.sh tests/test_doctor.py
git commit -m "feat(plugin): doctor.sh skeleton with hard-block detection"
```

---

## Task 7: doctor.sh — uv 自动安装

**Files:**
- Modify: `plugins/marshal/scripts/doctor.sh`
- Test: `tests/test_doctor.py`

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_doctor.py`)

```python
def test_doctor_auto_installs_uv_via_stub(tmp_path):
    # 假 PATH:无 uv;stub installer 往 fakebin 放一个 uv,再确认 doctor 标记 fixed。
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    # 只保留 python3/bash/env 等必要工具:用真实 /usr/bin + 一个无 uv 的目录
    installer = tmp_path / "install_uv.sh"
    installer.write_text(
        "#!/usr/bin/env bash\n"
        f"cat > {fakebin}/uv <<'EOF'\n#!/usr/bin/env bash\necho 'uv 0.0-stub'\nEOF\n"
        f"chmod +x {fakebin}/uv\n")
    installer.chmod(0o755)

    env = {
        # 把 fakebin 放最前;真实系统目录在后(供 python3/bash)
        "PATH": f"{fakebin}:/usr/bin:/bin",
        "MARSHAL_UV_INSTALLER": f"bash {installer}",
        # 跳过 env/seed 两步(本测试只验 uv 这一步)
        "MARSHAL_DOCTOR_SKIP_ENV": "1",
        "MARSHAL_DOCTOR_SKIP_SEED": "1",
    }
    p = _run(env)
    out = json.loads(p.stdout)
    assert out["ok"] is True, p.stdout + p.stderr
    assert "uv" in out["fixed"]
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_doctor.py::test_doctor_auto_installs_uv_via_stub -v`
Expected: FAIL — 当前 doctor 不检测 uv,`fixed` 为空

- [ ] **Step 3: 实现 uv 检测 + 自动安装**

在 doctor.sh 的 `emit true` 之前(python 检查之后)插入:

```bash
# 3) uv 已装?缺则自动安装(可被 MARSHAL_UV_INSTALLER 覆盖以便测试)
if ! command -v uv >/dev/null 2>&1; then
  INSTALLER="${MARSHAL_UV_INSTALLER:-curl -LsSf https://astral.sh/uv/install.sh | sh}"
  if eval "$INSTALLER" >/dev/null 2>&1; then
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv >/dev/null 2>&1; then
      FIXED+=("uv")
    else
      BLOCKED+=("uv-install-failed"); emit false; exit 0
    fi
  else
    BLOCKED+=("uv-install-failed"); emit false; exit 0
  fi
fi
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_doctor.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 提交**

```bash
git add plugins/marshal/scripts/doctor.sh tests/test_doctor.py
git commit -m "feat(plugin): doctor auto-installs uv when missing"
```

---

## Task 8: doctor.sh — 环境构建 + seed

**Files:**
- Modify: `plugins/marshal/scripts/doctor.sh`
- Test: `tests/test_doctor.py`

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_doctor.py`)

```python
def test_doctor_runs_seed_step(tmp_path):
    # 用 stub uv:`uv run --project <root> -m marshal_core.cli seed ...` 必须被调到。
    # stub uv 把它收到的参数写进 marker 文件,doctor 据 seed 退出码标记 ok。
    fakebin = tmp_path / "fakebin"; fakebin.mkdir()
    marker = tmp_path / "uv_args.txt"
    (fakebin / "uv").write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> {marker}\n'
        'exit 0\n')
    (fakebin / "uv").chmod(0o755)

    root = tmp_path / "proot"; (root / "data").mkdir(parents=True)
    (root / "data" / "marshal.snapshot.db").write_text("")  # 仅需存在
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "plugin.json").write_text('{"version":"0.0.1"}')

    env = {"PATH": f"{fakebin}:/usr/bin:/bin", "MARSHAL_DOCTOR_SKIP_ENV": "1"}
    p = _run(env, plugin_root=str(root))
    out = json.loads(p.stdout)
    assert out["ok"] is True, p.stdout + p.stderr
    args = marker.read_text()
    assert "seed" in args and "0.0.1" in args  # 用 plugin.json 的 version 调 seed
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_doctor.py::test_doctor_runs_seed_step -v`
Expected: FAIL — doctor 没调 uv/seed,marker 不存在

- [ ] **Step 3: 实现 env 构建 + seed 步骤**

在 doctor.sh 的 `emit true` 之前(uv 步骤之后)插入:

```bash
# 4) 消费侧环境就绪?(uv 懒构建;测试可 MARSHAL_DOCTOR_SKIP_ENV=1 跳过)
if [ "${MARSHAL_DOCTOR_SKIP_ENV:-0}" != "1" ]; then
  if ! uv run --project "$ROOT" python -c "import marshal_core" >/dev/null 2>&1; then
    uv sync --project "$ROOT" >/dev/null 2>&1 || { BLOCKED+=("uv-sync-failed"); emit false; exit 0; }
    FIXED+=("env")
  fi
fi

# 5) seed 快照进用户可写 db(测试可 MARSHAL_DOCTOR_SKIP_SEED=1 跳过)
if [ "${MARSHAL_DOCTOR_SKIP_SEED:-0}" != "1" ]; then
  VER=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" \
        "$ROOT/.claude-plugin/plugin.json" 2>/dev/null || echo "0")
  DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/marshal"
  mkdir -p "$DATA_DIR"
  export MARSHAL_DB="sqlite:///$DATA_DIR/marshal.db"
  if uv run --project "$ROOT" -m marshal_core.cli seed \
        --snapshot "$ROOT/data/marshal.snapshot.db" --version "$VER" >/dev/null 2>&1; then
    FIXED+=("seed")
  else
    BLOCKED+=("seed-failed"); emit false; exit 0
  fi
fi
```

> 注:doctor 把 `MARSHAL_DB` export 给 SKILL.md 用 —— SKILL.md 预检会从 doctor 输出之外**自己再算一遍同样的 `MARSHAL_DB`** 并用于后续所有 `cli` 调用(见 Task 11)。doctor 只负责把 seed 落到那个路径。

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_doctor.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
git add plugins/marshal/scripts/doctor.sh tests/test_doctor.py
git commit -m "feat(plugin): doctor builds env (uv sync) and seeds snapshot"
```

---

## Task 9: plugin 清单 + marketplace + pyproject

**Files:**
- Create: `plugins/marshal/.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `plugins/marshal/pyproject.toml`
- Test: `tests/test_build_plugin.py`

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_build_plugin.py`)

```python
import json as _json


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
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_build_plugin.py::test_manifests_are_valid_and_consistent -v`
Expected: FAIL — `FileNotFoundError: .claude-plugin/marketplace.json`

- [ ] **Step 3: 创建三个清单**

`.claude-plugin/marketplace.json`:

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "marshal",
  "description": "Marshal quality-gate platform — internal distribution",
  "owner": { "name": "shawhanken" },
  "plugins": [
    {
      "name": "marshal",
      "description": "Marshal consumer quality-gate skill (risk-tiering + invariant gate + adversarial review). Read-only invariant snapshot; auto-bootstraps uv on first run.",
      "author": { "name": "shawhanken" },
      "category": "quality",
      "source": { "source": "git-subdir", "url": "https://github.com/shawhanken/marshal.git", "path": "plugins/marshal", "ref": "main" }
    }
  ]
}
```

`plugins/marshal/.claude-plugin/plugin.json`:

```json
{
  "name": "marshal",
  "description": "Marshal consumer quality-gate skill — risk-tiering + invariant gate + adversarial review over a read-only invariant snapshot.",
  "author": { "name": "shawhanken" },
  "version": "0.0.1"
}
```

`plugins/marshal/pyproject.toml`(消费侧精简依赖):

```toml
[project]
name = "marshal-consumer"
version = "0.0.1"
description = "Marshal consumer-side CLI (read-only quality gate)"
requires-python = ">=3.11"
dependencies = [
  "sqlalchemy>=2.0",
  "pydantic>=2.6",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["marshal_core*", "marshal_pack_cowboy*"]
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_build_plugin.py::test_manifests_are_valid_and_consistent -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .claude-plugin/marketplace.json plugins/marshal/.claude-plugin/plugin.json plugins/marshal/pyproject.toml tests/test_build_plugin.py
git commit -m "feat(plugin): add marketplace + plugin manifests + consumer pyproject"
```

---

## Task 10: build_plugin 主流程串联 + version 一致性

**Files:**
- Modify: `scripts/build_plugin.py`
- Test: `tests/test_build_plugin.py`

让 `main()` 默认从 `plugin.json` 读 version(发版唯一入口,杜绝快照/plugin 版本漂移),并把 references 一并同步。

- [ ] **Step 1: 写失败测试**(追加到 `tests/test_build_plugin.py`)

```python
def test_build_plugin_default_version_from_manifest(tmp_path, monkeypatch):
    # main() 不传 --version 时,应从 plugins/marshal/.claude-plugin/plugin.json 取。
    # 用一个临时 source-db 验证退出码 0 且快照 meta 版本 == manifest 版本。
    src = _session(tmp_path / "root.db")
    Store(src).register_invariant(
        id="econ.fee_conservation", domain_pack="cowboy", domain="econ",
        spec_ref="CIP-3", executor_kind="proptest", location_repo="node",
        location_path="x.rs", location_test="prop_fee", severity="high")
    src.commit(); src.close()
    out = tmp_path / "snap.db"
    rc = build_plugin.main([
        "--source-db", str(tmp_path / "root.db"), "--out", str(out)])
    assert rc == 0
    pj = _json.load(open(os.path.join(
        ROOT, "plugins", "marshal", ".claude-plugin", "plugin.json")))
    assert Store(_session(out)).get_meta("snapshot_version") == pj["version"]
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/bin/python -m pytest tests/test_build_plugin.py::test_build_plugin_default_version_from_manifest -v`
Expected: FAIL — `main()` 当前 `--version` required,缺省报错

- [ ] **Step 3: 让 version 缺省读 manifest + 同步 references**

修改 `scripts/build_plugin.py` 的 `main()`:

```python
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
```

并把 `main()` 改成:

```python
def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="build_plugin")
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    p.add_argument("--source-db", default=os.path.join(repo, "marshal.db"))
    p.add_argument("--version", default=None)
    p.add_argument("--out",
                   default=os.path.join(repo, "plugins", "marshal", "data",
                                        "marshal.snapshot.db"))
    a = p.parse_args(argv)
    version = a.version or _manifest_version(repo)
    n_inv, n_esc = export_snapshot(a.source_db, a.out, version)
    print(f"snapshot v{version}: {n_inv} invariants, {n_esc} escapes -> {a.out}")
    pkgs = sync_packages(os.path.join(repo, "src"),
                         os.path.join(repo, "plugins", "marshal"))
    print(f"synced packages: {', '.join(pkgs)}")
    sync_references(repo)
    print("synced references")
    return 0
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/bin/python -m pytest tests/test_build_plugin.py -v`
Expected: PASS(全部 build 测试通过)

- [ ] **Step 5: 提交**

```bash
git add scripts/build_plugin.py tests/test_build_plugin.py
git commit -m "feat(build): default version from manifest + sync references"
```

---

## Task 11: 消费侧 SKILL.md

**Files:**
- Create: `plugins/marshal/skills/marshal/SKILL.md`
- (参考)Read: `.claude/skills/marshal/SKILL.md`(维护侧原版)

消费侧 SKILL.md = 维护侧版的改装:把「前置自检」从写死 venv 改为 doctor + uv;路由/流 A/B/C 段**整体复用**维护侧文本,仅按下述差异改。

- [ ] **Step 1: 读维护侧原版,作为基线**

Run: `cat .claude/skills/marshal/SKILL.md`
记下 frontmatter、路由、流 A/B/C/⑤/⑦ 各段。

- [ ] **Step 2: 写消费侧 SKILL.md**

创建 `plugins/marshal/skills/marshal/SKILL.md`,frontmatter 与维护侧一致(name/description/triggers),把「前置自检」段替换为:

```markdown
## 前置自检(每次先做)

本 skill 由 plugin 分发,确定性工作外包给捎带的 marshal CLI(经 uv 运行,数据来自只读快照 seed 的本地 db)。

    ROOT="${CLAUDE_PLUGIN_ROOT}"
    # 1) 体检 + 缺失自修复(装 uv / 建环境 / seed 快照),输出 JSON
    DOCTOR_JSON="$(bash "$ROOT/scripts/doctor.sh" --fix)"
    # 2) 解析:若 ok=false,把 blocked 项原样告诉用户并停止
    #    - CLAUDE_PLUGIN_ROOT/python3>=3.11 缺失 → 指引用户处理(唯一硬阻断)
    #    - uv-install-failed/uv-sync-failed/seed-failed → 贴出 doctor stderr 让用户排查
    # 3) 体检通过后,后续所有 cli 调用走:
    DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/marshal"
    export MARSHAL_DB="sqlite:///$DATA_DIR/marshal.db"
    PY=(uv run --project "$ROOT" -m marshal_core.cli)
    # 例:"${PY[@]}" classify --repo node --paths README.md

若 doctor 首次在自动安装 uv,向用户明示「正在为你安装 uv(astral.sh,单用户、无需 root)…」。
```

并在「路由」的 ratchet 行后补一句消费侧边界提示:

```markdown
- `/marshal ratchet "<bug>"` → 流 C。**注意(消费侧)**:本地棘轮只落你自己的 db,不回流团队真相源;团队级不变量由维护侧统一发版,经 `/plugin update` 下发。
```

其余路由/流 A/B/C/⑤/⑦ 段从维护侧原文照搬,仅把所有 `"$PY"`/`$PY` 调用替换为 `"${PY[@]}"`(uv 数组形式)。

- [ ] **Step 3: 校验 frontmatter 可被解析**

Run:
```bash
.venv/bin/python -c "import re,sys; t=open('plugins/marshal/skills/marshal/SKILL.md').read(); m=re.match(r'^---\n(.*?)\n---', t, re.S); assert m and 'name: marshal' in m.group(1) and 'description:' in m.group(1); print('frontmatter ok')"
```
Expected: `frontmatter ok`

- [ ] **Step 4: 提交**

```bash
git add plugins/marshal/skills/marshal/SKILL.md
git commit -m "feat(plugin): consumer-side SKILL.md (doctor/uv preflight, local-only ratchet)"
```

---

## Task 12: 首次产出 plugin 工件 + 干净房间验收

**Files:**
- Generated: `plugins/marshal/{marshal_core,marshal_pack_cowboy,skills/marshal/references}/`, `plugins/marshal/data/marshal.snapshot.db`
- Create: `docs/plugin-install.md`(队友安装说明)

- [ ] **Step 1: 跑 build_plugin 产出工件**

Run: `.venv/bin/python scripts/build_plugin.py`
Expected: 打印 `snapshot vX ... / synced packages ... / synced references`;`plugins/marshal/` 下出现 `marshal_core/`、`marshal_pack_cowboy/`、`data/marshal.snapshot.db`、`skills/marshal/references/`。

- [ ] **Step 2: 干净房间验收(异机模拟,手动)**

在临时 HOME、PATH 不含 uv 的环境里直接驱动 doctor + 一次门禁(模拟队友机器;若本机已装 uv 可跳过 PATH 处理):

```bash
TMP=$(mktemp -d)
env -i HOME="$TMP" PATH="/usr/bin:/bin" \
  CLAUDE_PLUGIN_ROOT="$PWD/plugins/marshal" \
  bash plugins/marshal/scripts/doctor.sh --fix
# 期望:JSON ok=true,fixed 含 uv(如本机无 uv)/env/seed
env -i HOME="$TMP" PATH="$TMP/.local/bin:/usr/bin:/bin" \
  uv run --project "$PWD/plugins/marshal" -m marshal_core.cli classify \
  --repo node --paths execution/src/execution/engine.rs
# 期望:JSON tier=high
```
Expected: doctor `ok:true`;classify 返回 `tier:high`。
（若环境无网导致真装 uv 失败,记录为已知限制,改用本机已装 uv 重跑后半段。）

- [ ] **Step 3: 写队友安装说明 `docs/plugin-install.md`**

```markdown
# 用上 Marshal(团队成员 · 异机只读)

    /plugin marketplace add shawhanken/marshal
    /plugin install marshal
    /marshal                 # 首次运行自动装 uv、建环境、seed 不变量快照

随后照常:`/marshal`、`/marshal <repo> <PR#>`、`/marshal <PR-URL>`。
更新不变量:`/plugin update`(维护侧发版后)。

硬前提(doctor 无法自动修复时会提示):python3 ≥ 3.11、Claude Code 版本需注入 `${CLAUDE_PLUGIN_ROOT}`。
边界:本地 `/marshal ratchet` 只进你自己的 db,不回流团队;新不变量由维护侧统一发版。
```

- [ ] **Step 4: 提交工件 + 说明**

```bash
git add plugins/marshal/marshal_core plugins/marshal/marshal_pack_cowboy \
        plugins/marshal/skills/marshal/references plugins/marshal/data/marshal.snapshot.db \
        docs/plugin-install.md
git commit -m "build: generate marshal plugin artifacts + install guide"
```

---

## Task 13: 全量回归 + lint + 发版流程文档

**Files:**
- Modify: `docs/superpowers/specs/2026-06-09-marshal-plugin-distribution-design.md`(若发现实现与 spec 漂移,回填)
- Create: `docs/release-plugin.md`(维护侧发版 checklist)

- [ ] **Step 1: 全量测试**

Run: `.venv/bin/python -m pytest -q`
Expected: 现有 48 测试 + 新增 seed/build/doctor 测试全 PASS。

- [ ] **Step 2: lint**

Run: `.venv/bin/ruff check src tests scripts`
Expected: `All checks passed!`(若有告警就地修)。

- [ ] **Step 3: 写维护侧发版 checklist `docs/release-plugin.md`**

```markdown
# 发版 Marshal 消费侧 plugin(维护侧)

1. 改不变量 / 跑棘轮(照旧落根 marshal.db)。
2. bump `plugins/marshal/.claude-plugin/plugin.json` 的 `version`。
3. 跑 `.venv/bin/python scripts/build_plugin.py`(从 manifest 取版本,导出快照 + 同步包/references)。
4. `.venv/bin/python -m pytest -q && .venv/bin/ruff check src tests scripts`。
5. `git add plugins/ && git commit && git push`(必要时 `git tag vX.Y.Z`)。
队友 `/plugin update` 即获新不变量;其本地 gate_run 不受影响。
```

- [ ] **Step 4: 提交**

```bash
git add docs/release-plugin.md docs/superpowers/specs/2026-06-09-marshal-plugin-distribution-design.md
git commit -m "docs: plugin release checklist; reconcile spec with implementation"
```

---

## 完成定义

- `cli seed` 幂等、版本门控,只换权威两表、保留本地 `gate_run`/`audit_log`。
- `scripts/build_plugin.py` 一条命令产出 plugin 工件(快照只含两表、含版本标记;包 + references 同步)。
- `plugins/marshal/scripts/doctor.sh` 自体检并自动补齐 uv/环境/seed;仅 `CLAUDE_PLUGIN_ROOT` 缺、python<3.11 为硬阻断。
- 三个清单(marketplace/plugin/pyproject)有效且一致(消费侧 pyproject 不含服务端依赖)。
- 消费侧 SKILL.md 预检走 doctor/uv、显式声明本地棘轮不回流。
- 干净房间(无 uv 临时 HOME)`doctor --fix` 后能跑通一次 classify。
- 全量 pytest + ruff 绿。
```
