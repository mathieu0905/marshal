"""Marshal 薄 CLI — skill 的确定性执行器。JSON 出入,错误非零退出。

db 路径解析为绝对 $MARSHAL_HOME/marshal.db,与 cwd 无关。
"""
import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.knowledge.models import Base
from marshal_core.knowledge.store import Store
from marshal_core.review import aggregate_review, verify_findings
from marshal_pack_cowboy.pack import CowboyPack

_PACK = CowboyPack()


def _marshal_home() -> Path:
    env = os.environ.get("MARSHAL_HOME")
    if env:
        return Path(env)
    # cli.py 在 <home>/src/marshal_core/cli.py
    return Path(__file__).resolve().parents[2]


def _db_url() -> str:
    if os.environ.get("MARSHAL_DB"):
        return os.environ["MARSHAL_DB"]
    return f"sqlite:///{_marshal_home() / 'marshal.db'}"


def _session():
    engine = create_engine(_db_url())
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _emit(obj) -> int:
    print(json.dumps(obj, ensure_ascii=False))
    return 0


def _fail(msg: str) -> int:
    print(json.dumps({"error": msg}, ensure_ascii=False))
    return 1


def cmd_classify(a) -> int:
    scope = {"repo": a.repo, "diff_paths": a.paths, "diff_text": a.diff_text or "",
             "labels": a.labels or []}
    # Whole-file content for .github/workflows/** so the CI threat model can reason over
    # constructs outside the 3-line diff window (P2). --workflow-file path=FILE repeated.
    wf = {}
    for spec in (a.workflow_files or []):
        if "=" not in spec:
            return _fail(f"--workflow-file expects path=localfile, got: {spec}")
        rel, local = spec.split("=", 1)
        try:
            wf[rel] = Path(local).read_text(encoding="utf-8")
        except OSError as e:
            return _fail(f"cannot read workflow file {local}: {e}")
    if wf:
        scope["workflow_files"] = wf
    return _emit(_PACK.classify_detailed(scope))


def cmd_ci_scan(a) -> int:
    """P0: deterministic CI-security backstop via zizmor (GitHub Actions auditor).

    Runs `zizmor --format json` over the given workflow files and normalizes findings.
    If zizmor is absent/errors, emits a degraded record (non-zero) so the gate records
    degraded → needs_human rather than a false pass (降级不谎报)."""
    import subprocess

    binary = _resolve_zizmor(a.zizmor_bin)
    if binary is None:
        print(json.dumps({"error": "zizmor not installed", "degraded": True,
                          "tool": a.zizmor_bin or "zizmor",
                          "hint": "install zizmor into the marshal venv: "
                                  "`<venv>/bin/pip install zizmor` (or pipx/uv/cargo); "
                                  "then ci-scan finds it automatically"},
                         ensure_ascii=False))
        return 1
    if not a.paths:
        return _fail("ci-scan needs --paths <workflow files>")
    try:
        proc = subprocess.run([binary, "--format", "json", *a.paths],
                              capture_output=True, text=True, timeout=a.timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(json.dumps({"error": f"zizmor invocation failed: {e}", "degraded": True},
                         ensure_ascii=False))
        return 1
    findings = _normalize_zizmor(proc.stdout)
    if findings is None:
        print(json.dumps({"error": "could not parse zizmor output", "degraded": True,
                          "raw_stderr": proc.stderr[:2000]}, ensure_ascii=False))
        return 1
    sev_rank = {"high": 3, "medium": 2, "low": 1, "informational": 0, "unknown": 0}
    by_sev = {}
    for f in findings:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    worst = max((sev_rank.get(f["severity"], 0) for f in findings), default=0)
    return _emit({"tool": "zizmor", "scanned": a.paths, "count": len(findings),
                  "by_severity": by_sev,
                  "worst_severity": next((s for s, r in sev_rank.items() if r == worst),
                                         "none") if findings else "none",
                  "findings": findings})


def _resolve_zizmor(explicit):
    """Find the zizmor binary. Explicit path wins; otherwise prefer the one installed
    next to the running interpreter (the marshal venv's bin, where `pip install zizmor`
    puts it) so the gate works without PATH fiddling, then fall back to PATH."""
    import shutil

    if explicit:
        return explicit if (Path(explicit).exists() or shutil.which(explicit)) else None
    venv_bin = Path(sys.executable).parent / "zizmor"
    if venv_bin.exists():
        return str(venv_bin)
    return shutil.which("zizmor")


def _normalize_zizmor(stdout: str):
    """zizmor JSON (array of findings) → [{id, severity, path, location, message}].
    Returns None on parse failure. Matches the zizmor 1.x schema: severity under
    `.determinations.severity`; path under `.locations[0].symbolic.key.{Local|Remote}`;
    line under `.locations[0].concrete.location.start_point.row`. Falls back gracefully."""
    try:
        data = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = data.get("findings") or data.get("results") or []
    if not isinstance(data, list):
        return None
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        sev = (item.get("determinations") or {}).get("severity") \
            or item.get("severity") or item.get("level") or "unknown"
        path, location = "", ""
        locs = item.get("locations") or []
        if locs and isinstance(locs[0], dict):
            sym = locs[0].get("symbolic") or {}
            key = sym.get("key") or {}
            if isinstance(key, dict):
                loc = key.get("Local") or key.get("Remote") or {}
                path = loc.get("given_path") or loc.get("path") or ""
            conc = (locs[0].get("concrete") or {}).get("location") or {}
            row = (conc.get("start_point") or {}).get("row")
            if row is not None:
                location = f"line {row}"
        out.append({"id": item.get("ident") or item.get("rule") or item.get("id") or "?",
                    "severity": str(sev).lower(),
                    "path": path or item.get("path", ""),
                    "location": location,
                    "message": item.get("desc") or item.get("message") or item.get("title", "")})
    return out


def cmd_review_quorum(a) -> int:
    # ③ 把多视角 review 发现聚合成 quorum 结论 (去重/计票/高危升 needs_human)。
    return _emit(aggregate_review(json.loads(a.findings_json), quorum=a.quorum))


def cmd_review_verify(a) -> int:
    # ③ 对抗式验证二段: 按 skeptic 投票裁决每条发现 (default-to-refute)。
    return _emit(verify_findings(json.loads(a.votes_json)))


def cmd_spec_source(a) -> int:
    # 把 spec_ref 标签 (如 CIP-3 / WP) 解析到正文源 (repo + path_glob),供 skill JIT 读取。
    return _emit({"ref": a.ref, "source": _PACK.resolve_spec_ref(a.ref)})


def cmd_spec_requirements(a) -> int:
    # ⑤: 解析一个 spec_ref 的正文,抽 RFC2119 候选 requirement (要求级 conformance 分母侧)。
    import glob
    src = _PACK.resolve_spec_ref(a.ref)
    if src is None:
        return _fail(f"unresolvable spec_ref: {a.ref}")
    hits = sorted(glob.glob(os.path.join(a.spec_root, src["path_glob"])))
    if not hits:
        return _fail(f"spec source not found: {os.path.join(a.spec_root, src['path_glob'])}")
    with open(hits[0], encoding="utf-8") as fh:
        reqs = _PACK.parse_spec_requirements(fh.read())
    levels = {"must": 0, "should": 0, "may": 0}
    for r in reqs:
        levels[r["level"]] += 1
    return _emit({"ref": a.ref, "source": os.path.relpath(hits[0], a.spec_root),
                  "counts": levels, "total": len(reqs), "requirements": reqs})


def cmd_conformance(a) -> int:
    # ⑤ conformance 矩阵: spec → 覆盖它的不变量。可选 --spec-root 枚举全 CIP 集,
    # 算出未被任何不变量覆盖的 CIP (gap),即 §7 conformance% 的分母侧。
    matrix = _PACK.conformance_matrix()
    out = {"covered": matrix, "specs_covered": sorted(matrix)}
    if a.spec_root:
        import glob
        import re as _re
        cip_dir = os.path.join(a.spec_root, "docs", "cips")
        per_cip = []
        for f in glob.glob(os.path.join(cip_dir, "cip-*.md")):
            m = _re.match(r"cip-(\d+)-", os.path.basename(f))
            if not m:
                continue
            ref = f"CIP-{int(m.group(1))}"
            with open(f, encoding="utf-8") as fh:
                musts = sum(1 for r in _PACK.parse_spec_requirements(fh.read())
                            if r["level"] == "must")
            per_cip.append({"cip": ref, "must_requirements": musts,
                            "invariants": len(matrix.get(ref, [])),
                            "covered": ref in matrix})
        all_cips = {c["cip"] for c in per_cip}
        covered_cips = {c["cip"] for c in per_cip if c["covered"]}
        uncovered = sorted(all_cips - covered_cips, key=lambda s: int(s.split("-")[1]))
        pct = round(100 * len(covered_cips) / len(all_cips), 1) if all_cips else 0.0
        # 排序: 欠覆盖优先 (无不变量在前, 然后 MUST 越多越靠前) —— 即最该补的网眼。
        per_cip.sort(key=lambda c: (c["invariants"] > 0, -c["must_requirements"]))
        out["cip_total"] = len(all_cips)
        out["cip_covered"] = len(covered_cips)
        out["cip_uncovered"] = uncovered
        out["cip_conformance_pct"] = pct
        out["per_cip"] = per_cip
    return _emit(out)


def cmd_invariants(a) -> int:
    scope = {"repo": a.repo, "diff_paths": a.paths}
    invs = _PACK.list_invariants(scope)
    return _emit([
        {"id": i.id, "severity": i.severity, "executor_kind": i.executor_kind,
         "location_repo": i.location_repo, "location_path": i.location_path,
         "location_test": i.location_test, "run_command": i.run_command}
        for i in invs
    ])


def cmd_ratchet_open(a) -> int:
    s = _session()
    try:
        esc = Store(s).open_escape(
            id=a.escape_id, description=a.desc, root_cause_class=a.root_cause,
            change_ref=a.change_ref)
        return _emit({"escape_id": esc.id})
    finally:
        s.close()


def cmd_ratchet_close(a) -> int:
    if not a.spawned_check:
        return _fail("spawned_check is required to close an escape (棘轮纪律)")
    inv = json.loads(a.inv_json)
    inv.setdefault("domain_pack", "cowboy")  # InvariantRegistry.domain_pack 非空
    # 知识核只存引用(repo+path+test-name),不存可执行命令(spec §3.4);
    # 丢弃 InvariantDef 上有、但 InvariantRegistry 表没有的字段(如 run_command)。
    _REGISTRY_FIELDS = {"id", "domain_pack", "domain", "spec_ref", "executor_kind",
                        "location_repo", "location_path", "location_test", "severity",
                        "status"}
    inv = {k: v for k, v in inv.items() if k in _REGISTRY_FIELDS}
    s = _session()
    try:
        store = Store(s)
        store.register_invariant(**inv, origin="ratchet", escape_id=a.escape_id)
        store.close_escape(a.escape_id, spawned_check=a.spawned_check)
        return _emit({"ok": True, "escape_id": a.escape_id,
                      "spawned_check": a.spawned_check})
    finally:
        s.close()


def cmd_gate_record(a) -> int:
    gates = json.loads(a.evidence_json)
    s = _session()
    try:
        store = Store(s)
        run = store.record_gate_run(change_ref=a.change_ref, job_id=a.change_ref,
                                    verdict=a.verdict, evidence={"gates": gates})
        store.audit(event="gate_decision", actor="marshal-skill",
                    decision=a.verdict, refs={"change_ref": a.change_ref})
        return _emit({"run_id": run.id})
    finally:
        s.close()


def cmd_metrics(a) -> int:
    # ⑦ 从知识核聚合方法论指标 (按需报告)。
    s = _session()
    try:
        return _emit(Store(s).metrics())
    finally:
        s.close()


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


def cmd_setup(a) -> int:
    home = _marshal_home()
    skill_src = home / ".claude" / "skills" / "marshal"
    link_dir = Path(os.path.expanduser("~")) / ".claude" / "skills"
    link_dir.mkdir(parents=True, exist_ok=True)
    link = link_dir / "marshal"
    if link.is_symlink() or link.exists():
        if link.is_symlink():
            link.unlink()
        else:
            return _fail(f"{link} exists and is not a symlink; remove it manually")
    link.symlink_to(skill_src, target_is_directory=True)

    try:
        import marshal_pack_cowboy.pack  # noqa: F401
        import_ok = True
    except Exception:
        import_ok = False

    zizmor = _resolve_zizmor(None)
    hints = []
    if not import_ok:
        hints.append("run: pip install -e . in marshal venv")
    if zizmor is None:
        hints.append("CI gate degraded: install zizmor — `pip install -e .[ci]` "
                     "(or pip install zizmor) in the marshal venv")
    return _emit({"ok": True, "symlink": str(link), "target": str(skill_src),
                  "import_ok": import_ok, "zizmor": zizmor or "MISSING",
                  "hint": "; ".join(hints) or None})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="marshal")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify")
    c.add_argument("--repo", required=True)
    c.add_argument("--paths", nargs="*", default=[])
    c.add_argument("--diff-text", dest="diff_text", default="")
    c.add_argument("--labels", nargs="*", default=[])
    c.add_argument("--workflow-file", dest="workflow_files", action="append", default=[],
                   help="repeatable repo_path=localfile; whole .github/workflows content "
                        "for the CI threat model (P2 — sees constructs outside the diff)")
    c.set_defaults(func=cmd_classify)

    cs = sub.add_parser("ci-scan")
    cs.add_argument("--paths", nargs="*", default=[],
                    help="workflow files to audit with zizmor")
    cs.add_argument("--zizmor-bin", dest="zizmor_bin", default=None,
                    help="zizmor binary (default: zizmor on PATH)")
    cs.add_argument("--timeout", type=int, default=120)
    cs.set_defaults(func=cmd_ci_scan)

    iv = sub.add_parser("invariants")
    iv.add_argument("--repo", required=True)
    iv.add_argument("--paths", nargs="*", default=[])
    iv.set_defaults(func=cmd_invariants)

    rq = sub.add_parser("review-quorum")
    rq.add_argument("--findings-json", dest="findings_json", required=True)
    rq.add_argument("--quorum", type=int, default=2)
    rq.set_defaults(func=cmd_review_quorum)

    rv = sub.add_parser("review-verify")
    rv.add_argument("--votes-json", dest="votes_json", required=True)
    rv.set_defaults(func=cmd_review_verify)

    ss = sub.add_parser("spec-source")
    ss.add_argument("--ref", required=True)
    ss.set_defaults(func=cmd_spec_source)

    sr = sub.add_parser("spec-requirements")
    sr.add_argument("--ref", required=True)
    sr.add_argument("--spec-root", dest="spec_root", required=True,
                    help="path to the cowboy repo root containing docs/{cips,whitepaper}")
    sr.set_defaults(func=cmd_spec_requirements)

    cf = sub.add_parser("conformance")
    cf.add_argument("--spec-root", dest="spec_root", default=None,
                    help="path to the cowboy repo root; enables CIP gap/percent reporting")
    cf.set_defaults(func=cmd_conformance)

    ro = sub.add_parser("ratchet-open")
    ro.add_argument("--escape-id", dest="escape_id", required=True)
    ro.add_argument("--desc", required=True)
    ro.add_argument("--root-cause", dest="root_cause", default="")
    ro.add_argument("--change-ref", dest="change_ref", default=None)
    ro.set_defaults(func=cmd_ratchet_open)

    rc = sub.add_parser("ratchet-close")
    rc.add_argument("--escape-id", dest="escape_id", required=True)
    rc.add_argument("--spawned-check", dest="spawned_check", default="")
    rc.add_argument("--inv-json", dest="inv_json", required=True)
    rc.set_defaults(func=cmd_ratchet_close)

    gr = sub.add_parser("gate-record")
    gr.add_argument("--change-ref", dest="change_ref", required=True)
    gr.add_argument("--verdict", required=True,
                    choices=["pass", "block", "needs_human"])
    gr.add_argument("--evidence-json", dest="evidence_json", default="[]")
    gr.set_defaults(func=cmd_gate_record)

    mt = sub.add_parser("metrics")
    mt.set_defaults(func=cmd_metrics)

    sd = sub.add_parser("seed")
    sd.add_argument("--snapshot", required=True, help="path to marshal.snapshot.db")
    sd.add_argument("--version", required=True, help="snapshot version (= plugin version)")
    sd.set_defaults(func=cmd_seed)

    st = sub.add_parser("setup")
    st.set_defaults(func=cmd_setup)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:  # 边界:把任何确定性失败转成 degraded 信号给 skill
        return _fail(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())
