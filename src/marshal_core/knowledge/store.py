"""知识核读写薄封装。"""
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session
from .models import InvariantRegistry, GateRun, AuditLog, EscapeRegistry, Meta, ReviewJob, _now


class Store:
    def __init__(self, session: Session):
        self.s = session

    def register_invariant(self, **kw) -> InvariantRegistry:
        inv = InvariantRegistry(**kw)
        self.s.merge(inv)
        self.s.commit()
        return inv

    def list_invariants(self, domain_pack: str, repo: str) -> list[InvariantRegistry]:
        stmt = select(InvariantRegistry).where(
            InvariantRegistry.domain_pack == domain_pack,
            InvariantRegistry.location_repo == repo,
            InvariantRegistry.status == "active",
        )
        return list(self.s.scalars(stmt))

    def invariant_breakdown(self) -> dict:
        by_status: dict[str, int] = {}
        for status, n in self.s.execute(
                select(InvariantRegistry.status, func.count())
                .group_by(InvariantRegistry.status)):
            by_status[status] = n
        by_severity: dict[str, int] = {}
        for sev, n in self.s.execute(
                select(InvariantRegistry.severity, func.count())
                .group_by(InvariantRegistry.severity)):
            by_severity[sev] = n
        candidate_red_ids = list(self.s.scalars(
            select(InvariantRegistry.id)
            .where(InvariantRegistry.status == "candidate-red")
            .order_by(InvariantRegistry.id)))
        return {"by_status": by_status, "by_severity": by_severity,
                "candidate_red_ids": candidate_red_ids}

    def record_gate_run(self, change_ref: str, job_id: str, verdict: str,
                        evidence: dict) -> GateRun:
        run = GateRun(change_ref=change_ref, job_id=job_id, verdict=verdict,
                      evidence=evidence)
        self.s.add(run)
        self.s.commit()
        return run

    def get_gate_run(self, run_id: int) -> GateRun | None:
        return self.s.get(GateRun, run_id)

    @staticmethod
    def inbox_summary(evidence: dict | None) -> dict:
        """Project a gate_run's free-form evidence into a STABLE inbox card schema.

        gate_run.evidence has no fixed shape: production rows nest everything under
        `evidence.gates` with per-review keys, while flat fixtures put fields at the
        top level. This normalizer reads either shape and always returns the same keys
        (null where unknown), so the SPA never has to guess. Best-effort by design —
        fields the source doesn't carry come back null, not fabricated.
        """
        ev = evidence or {}
        g = ev.get("gates") if isinstance(ev.get("gates"), dict) else ev
        if not isinstance(g, dict):
            g = {}

        def _first_str(*keys):
            for k in keys:
                v = g.get(k)
                if isinstance(v, str) and v.strip():
                    return v
            return None

        def _count(*keys):
            for k in keys:
                v = g.get(k)
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    return v
                if isinstance(v, (list, dict)):
                    return len(v)
            return None

        inv_pass = inv_total = None
        if isinstance(g.get("invariants_run"), int) and not isinstance(g.get("invariants_run"), bool):
            inv_total = g["invariants_run"]
            inv_pass = g.get("invariants_pass") if isinstance(g.get("invariants_pass"), int) else None
        elif isinstance(g.get("invariants"), dict):
            vals = list(g["invariants"].values())
            inv_total = len(vals)
            inv_pass = sum(1 for x in vals if str(x).lower() == "pass")

        return {
            "tier": _first_str("tier"),
            "cip": _first_str("cip"),
            "repo": _first_str("repo"),
            "invariants_pass": inv_pass,
            "invariants_total": inv_total,
            "findings": _count("high_sev_findings", "findings"),
            "advisory": _count("advisory_findings", "advisory"),
            "headline": _first_str("summary", "headline", "change", "reason", "remedy"),
        }

    def list_needs_human(self, limit: int = 50) -> list[dict]:
        stmt = (select(GateRun)
                .where(GateRun.verdict == "needs_human")
                .order_by(GateRun.created_at.desc(), GateRun.id.desc())
                .limit(limit))
        return [
            {"id": r.id, "change_ref": r.change_ref, "job_id": r.job_id,
             "verdict": r.verdict, "evidence": r.evidence,
             "summary": self.inbox_summary(r.evidence),
             "created_at": r.created_at.isoformat()}
            for r in self.s.scalars(stmt)
        ]

    def audit(self, event: str, actor: str = "system", decision: str = "",
              refs: dict | None = None) -> None:
        self.s.add(AuditLog(event=event, actor=actor, decision=decision,
                            refs=refs or {}))
        self.s.commit()

    def open_escape(self, **kw) -> EscapeRegistry:
        esc = EscapeRegistry(**kw)
        self.s.add(esc)
        self.s.commit()
        return esc

    def get_escape(self, escape_id: str) -> EscapeRegistry | None:
        return self.s.get(EscapeRegistry, escape_id)

    def list_open_escapes(self) -> list[EscapeRegistry]:
        stmt = select(EscapeRegistry).where(EscapeRegistry.status == "open")
        return list(self.s.scalars(stmt))

    def escape_breakdown(self) -> list[dict]:
        stmt = (select(EscapeRegistry.root_cause_class, EscapeRegistry.status,
                       func.count())
                .group_by(EscapeRegistry.root_cause_class, EscapeRegistry.status))
        agg: dict[str, dict] = {}
        for root_cause, status, n in self.s.execute(stmt):
            slot = agg.setdefault(
                root_cause, {"root_cause_class": root_cause, "count": 0,
                             "open": 0, "closed": 0})
            slot["count"] += n
            if status in ("open", "closed"):
                slot[status] += n
        return sorted(agg.values(), key=lambda r: r["count"], reverse=True)

    def metrics(self) -> dict:
        """⑦ 度量: 从知识核聚合方法论指标。诚实标注当前数据模型不支持的指标
        (escape_rate 缺总-bug 分母;time_to_detection 缺 introduced_at 时间戳;
        tiered_review_coverage 缺 Classifications 表),给 null + reason,不瞎编。
        """
        def _count(model, *where):
            stmt = select(func.count()).select_from(model)
            for w in where:
                stmt = stmt.where(w)
            return self.s.scalar(stmt)

        inv_active = _count(InvariantRegistry, InvariantRegistry.status == "active")
        inv_ratchet = _count(InvariantRegistry, InvariantRegistry.status == "active",
                             InvariantRegistry.origin == "ratchet")
        esc_open = _count(EscapeRegistry, EscapeRegistry.status == "open")
        esc_closed = _count(EscapeRegistry, EscapeRegistry.status == "closed")
        gate_total = _count(GateRun)
        gate_by_verdict = {
            v: _count(GateRun, GateRun.verdict == v)
            for v in ("pass", "block", "needs_human")
        }
        return {
            "invariant_gate_count": inv_active,
            "ratchet_invariants": inv_ratchet,
            "escapes_open": esc_open,
            "escapes_closed": esc_closed,
            "ratchet_increment": esc_closed,   # 每个 closed escape 至少织出一条检查
            "gate_runs_total": gate_total,
            "gate_runs_by_verdict": gate_by_verdict,
            "mean_time_to_detection": self.mttd(),
            "unavailable": {
                "escape_rate": "needs a total-bug denominator (not tracked)",
                "tiered_review_coverage": "needs a Classifications table (not modeled in this slice)",
                "cip_conformance_pct": "use `conformance --spec-root <cowboy>`",
            },
        }

    def mttd(self) -> dict:
        # Mean time-to-detection over escapes that have both an introduced_at_ts and a
        # discovered_at. Escapes lacking the timestamp are excluded and counted honestly
        # (no fabricated interval), matching the metrics() honesty policy.
        rows = self.s.execute(
            select(EscapeRegistry.discovered_at, EscapeRegistry.introduced_at_ts)).all()
        deltas, excluded = [], 0
        for discovered_at, introduced_at_ts in rows:
            if discovered_at is not None and introduced_at_ts is not None:
                deltas.append((discovered_at - introduced_at_ts).total_seconds())
            else:
                excluded += 1
        if not deltas:
            return {"mean_days": None, "count": 0, "excluded": excluded}
        return {"mean_days": round(sum(deltas) / len(deltas) / 86400, 2),
                "count": len(deltas), "excluded": excluded}

    def verdict_timeseries(self) -> list[dict]:
        # Bucket gate runs by calendar day (UTC) and verdict. Done in Python so it
        # stays engine-agnostic (SQLite date() vs Postgres date_trunc differ).
        buckets: dict[str, dict] = {}
        for r in self.s.scalars(select(GateRun).order_by(GateRun.created_at)):
            day = r.created_at.date().isoformat()
            slot = buckets.setdefault(
                day, {"date": day, "pass": 0, "needs_human": 0, "block": 0})
            if r.verdict in slot:
                slot[r.verdict] += 1
        return [buckets[d] for d in sorted(buckets)]

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

    def close_escape(self, escape_id: str, spawned_check: str) -> EscapeRegistry:
        if not spawned_check:
            raise ValueError("cannot close escape without a spawned_check (棘轮纪律)")
        esc = self.s.get(EscapeRegistry, escape_id)
        if esc is None:
            raise ValueError(f"escape not found: {escape_id}")
        esc.spawned_check = spawned_check
        esc.status = "closed"
        self.s.commit()
        return esc

    @staticmethod
    def _job_dict(j: ReviewJob) -> dict:
        return {"id": j.id, "change_ref": j.change_ref, "repo": j.repo,
                "kind": j.kind, "status": j.status, "requested_by": j.requested_by,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                "result": j.result, "error": j.error}

    def enqueue_job(self, change_ref: str, repo: str = "node",
                    kind: str = "mechanical", requested_by: str = "dashboard") -> dict:
        job = ReviewJob(change_ref=change_ref, repo=repo, kind=kind,
                        requested_by=requested_by)
        self.s.add(job)
        self.s.commit()
        return self._job_dict(job)

    def get_job(self, job_id: int) -> dict | None:
        j = self.s.get(ReviewJob, job_id)
        return self._job_dict(j) if j else None

    def claim_next_job(self) -> dict | None:
        # Compare-and-swap claim: read the oldest pending job, then atomically flip
        # it to running guarded by status=='pending'. If another worker won the race
        # (rowcount 0), retry with the next pending row. This is safe on SQLite and
        # guarantees no two workers claim the same job.
        while True:
            job = self.s.scalars(
                select(ReviewJob).where(ReviewJob.status == "pending")
                .order_by(ReviewJob.created_at, ReviewJob.id).limit(1)).first()
            if job is None:
                return None
            res = self.s.execute(
                update(ReviewJob)
                .where(ReviewJob.id == job.id, ReviewJob.status == "pending")
                .values(status="running", started_at=_now()))
            self.s.commit()
            if res.rowcount == 1:
                self.s.refresh(job)
                return self._job_dict(job)
            # lost the race; expire the stale row and try the next pending one
            self.s.expire(job)

    def finish_job(self, job_id: int, result: dict) -> dict:
        j = self.s.get(ReviewJob, job_id)
        if j is None:
            raise ValueError(f"job not found: {job_id}")
        j.status = "done"
        j.result = result
        j.finished_at = _now()
        self.s.commit()
        return self._job_dict(j)

    def fail_job(self, job_id: int, error: str) -> dict:
        j = self.s.get(ReviewJob, job_id)
        if j is None:
            raise ValueError(f"job not found: {job_id}")
        j.status = "failed"
        j.error = error
        j.finished_at = _now()
        self.s.commit()
        return self._job_dict(j)
