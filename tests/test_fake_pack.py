"""Fake-pack contract test: core is domain-agnostic.

Demonstrates core marshalling logic works with any DomainPack, not just Cowboy.
This is a regression test to ensure core doesn't depend on cowboy-specific knowledge.
"""
from marshal_core.contracts import NormalizedEvent, StructuredResult
from marshal_core.domain_pack import DomainPack, InvariantDef, ReviewPack
from marshal_core.knowledge.store import Store
from marshal_core.modules.orchestrator import Orchestrator


class FakePack:
    """Minimal domain pack unrelated to Cowboy."""

    @property
    def id(self) -> str:
        return "fake"

    def list_invariants(self, scope: dict) -> list[InvariantDef]:
        return [
            InvariantDef(
                id="fake.always",
                domain="generic",
                spec_ref="RFC-1",
                executor_kind="proptest",
                location_repo="anyrepo",
                location_path="x",
                location_test="t",
                severity="low",
            )
        ]

    def classify(self, scope: dict) -> str:
        return "low"


def test_core_runs_with_arbitrary_pack(db_session):
    """Core orchestrator should work with any pack, not just Cowboy."""
    orch = Orchestrator(pack=FakePack(), store=Store(db_session))
    ev = NormalizedEvent(kind="pr", repo="anyrepo", change_ref="z9")
    job = orch.handle_event(ev)
    assert job.params["invariant_ids"] == ["fake.always"]
    res = StructuredResult(
        job_id=job.job_id,
        kind="invariant",
        status="ok",
        payload={
            "results": [
                {"invariant_id": "fake.always", "passed": True, "detail": ""}
            ]
        },
    )
    assert orch.handle_result(ev, res).verdict == "pass"


def test_minimal_pack_is_domainpack_but_not_reviewpack():
    """通用性护栏: 最小 pack 满足 core 的 DomainPack 面, 但**无需**实现 review 编排。

    若哪天有人把 review_plan/security_hazards 挪进 DomainPack, 这条会红 —— 提醒
    别把 Cowboy 形状的 review 编排焊进 core 契约。
    """
    fake = FakePack()
    assert isinstance(fake, DomainPack)          # core 编排器够用
    assert not isinstance(fake, ReviewPack)      # 未实现扩展面, 且不被强制


def test_cowboy_pack_implements_both_tiers():
    from marshal_pack_cowboy.pack import CowboyPack

    pack = CowboyPack()
    assert isinstance(pack, DomainPack)
    assert isinstance(pack, ReviewPack)
