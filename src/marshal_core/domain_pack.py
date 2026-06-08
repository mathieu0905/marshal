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
    @property
    def id(self) -> str: ...

    def list_invariants(self, scope: dict) -> list[InvariantDef]: ...

    def classify(self, scope: dict) -> str:
        """返回 high|mid|low。"""
        ...
