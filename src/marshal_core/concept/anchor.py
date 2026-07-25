"""H1 守栏: 概念锚定必须"代码验证", 不能"文档派生"。

深审 run 750(H1-weak)修正: **不能只查符号"出现"** —— 符号出现在注释/字符串/单纯
提及里, 会把"没实现"和"挂羊头"误判成高置信锚定(实测:`// TODO GasReport` 与
`struct GasReport{pixel}` 都被判 verified=0.85)。故收紧为**定义位匹配**(struct/fn/
const/def/class 等定义关键字后紧跟符号), 排除**纯提及/调用**(无定义关键字前缀的出现)。
(启发式边界:一条恰好写成 `// fn Foo` 的注释仍会误配 —— 属已接受的 S0 正则局限,
未来接 rust-analyzer/LSP 精确化。)

**边界(必须写清):** 本模块只验"符号是否在此**定义**", **不判语义是否名副其实** ——
"挂羊头"(名 GasReport 实为 UI widget)的 struct 定义仍会通过。判语义错配是 S4 的
concept-consistency lens 的职责, 不是 H1。故 Task 9 Step 3 的锚定率门≠"无挂羊头"。
"""
import re
from dataclasses import dataclass
from pathlib import Path

from .model import ConceptPage

_DOC_ONLY_CONFIDENCE_CAP = 0.3
_VERIFIED_CONFIDENCE = 0.85
# 定义位关键字 (Rust + Python 覆盖本期两语言); 匹配 `<kw> <symbol>`, 排除注释/调用/提及
_DEF_KEYWORDS = r"struct|enum|fn|const|static|trait|type|impl|mod|def|class"


@dataclass
class AnchorReport:
    verified_count: int    # = 在定义位被找到的 anchor 数 (不是语义正确数)
    total: int
    doc_only: bool
    confidence: float
    verified_symbols: list[str]


def _symbol_defined(repo_root: str, rel_path: str, symbol: str) -> bool:
    """符号是否在此文件被**定义**(而非仅出现/被调用/注释提及)。"""
    f = Path(repo_root) / rel_path
    if not f.is_file():
        return False
    pattern = re.compile(rf"\b(?:{_DEF_KEYWORDS})\s+{re.escape(symbol)}\b")
    return bool(pattern.search(f.read_text(encoding="utf-8", errors="ignore")))


def verify_anchors(page: ConceptPage, repo_roots: dict[str, str]) -> AnchorReport:
    """repo_roots: {repo_name: absolute_path}。缺失的 repo 视为该 anchor 未验证。
    verified = 符号在锚点文件被定义; 无一通过 → doc_only + confidence 封顶(H1)。
    注意: anchor 应指向符号的**定义文件**, 非使用处。"""
    verified = [
        a.symbol for a in page.anchors
        if a.repo in repo_roots and _symbol_defined(repo_roots[a.repo], a.path, a.symbol)
    ]
    doc_only = len(verified) == 0
    confidence = _DOC_ONLY_CONFIDENCE_CAP if doc_only else _VERIFIED_CONFIDENCE
    return AnchorReport(
        verified_count=len(verified),
        total=len(page.anchors),
        doc_only=doc_only,
        confidence=confidence,
        verified_symbols=verified,
    )
