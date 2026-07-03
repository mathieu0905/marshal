"""领域包契约 — 核心通过它取领域知识, 绝不硬编码项目专属内容。"""
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class InvariantDef:
    id: str
    domain: str
    spec_ref: str
    executor_kind: str
    location_repo: str
    location_path: str
    location_test: str
    severity: str = "mid"
    run_command: list[str] = field(default_factory=list)   # 可直接执行的 argv (由领域包提供)
    # 已注册但尚未强制执行 (如 #[ignore] 骨架, 等实现 body / 注入缝). pending 不进门禁
    # dispatch (避免每次 0-passed 假降级), 也不计入 conformance 覆盖 (不虚报); body 落地
    # 后翻 False 即一键激活. 来源: Marshal 棘轮 close 但检查体未实现的过渡态.
    pending: bool = False


@runtime_checkable
class DomainPack(Protocol):
    """core 编排器依赖的**最小**面 (分级 + 不变量)。

    Orchestrator / Classifier / InvariantGate 只调这 3 个方法; 一个只跑不变量
    门禁的最小 pack 实现到这里即可 (见 tests/test_fake_pack.py)。对抗 review 的
    视角选择 / 安全危险点属**可选扩展面**, 见下方 ReviewPack —— 不塞进这里, 是为
    了不逼每个领域包都实现 review 编排 (保持 core 通用)。
    """

    @property
    def id(self) -> str: ...

    def list_invariants(self, scope: dict) -> list[InvariantDef]: ...

    def classify(self, scope: dict) -> str:
        """返回 high|mid|low。"""
        ...


@runtime_checkable
class ReviewPack(DomainPack, Protocol):
    """可选扩展面: 门禁分级细节 + 对抗 review 视角选择 (由 gate/review CLI 与 skill
    大脑消费, **非** core 编排器依赖)。

    实现这层的 pack 额外提供: 分级理由/命中契约的细节 (classify_detailed)、按 scope
    选出的对抗 review 视角 (review_plan)、否定性安全危险点 (security_hazards)。核心
    编排逻辑对本层零依赖 —— 换个最小 pack 仍能跑不变量门禁; 只是没有 review 编排。
    """

    def classify_detailed(self, scope: dict) -> dict:
        """返回 {tier, reasons, contracts_hit, security_hazards, review_dimensions}。"""
        ...

    def review_plan(self, scope: dict) -> list[dict]:
        """按 scope 选对抗 review 视角, 返回 [{name, prompt}] (领域语义全在 pack 侧)。

        scope 可带已算好的 `tier` (省一次 classify); 缺则由 classify(scope) 推。
        签名吃整个 scope (含 diff_paths) 是为让视角能**按路径条件触发**, 与
        list_invariants / security_hazards 的 scope-gated 形状对齐。
        """
        ...

    def security_hazards(self, scope: dict) -> list[dict]:
        """否定性/对抗性安全危险点 (信任边), 返回 [{id, title, prompt, invariant_able}]。"""
        ...
