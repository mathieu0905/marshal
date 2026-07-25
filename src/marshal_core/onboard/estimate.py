"""Onboard dry-run 成本估算 —— 确定性、显式披露方法、不谎报精度(§6.3)。

启发式,不是承诺值:按文档+采样代码字节估输入 token、按模块数估 agent fan-out 次数、
按候选概念数估输出 token,乘以披露的单价区间。目的是"动手前把量摆出来", 让人决定是否值得跑。
"""
from pathlib import Path

_CHARS_PER_TOKEN = 4              # 粗略英文/代码 char→token 比
_CODE_SAMPLE_FRACTION = 0.3       # 抽取只采样部分代码, 非全读
_CONCEPTS_PER_MODULE = 3          # 每模块估产出的概念数
_TOKENS_PER_CONCEPT_PAGE = 400    # 每页概念 markdown 估输出 token
_FANOUT_MODULES_PER_CALL = 4      # 每次 agent 调用覆盖的模块数
# 披露的单价区间 (USD / 1K token, input+output 合计的粗估), 显式写进 method
_USD_PER_1K_LOW = 0.003
_USD_PER_1K_HIGH = 0.015

_DOC_EXT = {".md", ".rst", ".txt", ".mdx"}
_CODE_EXT = {".rs", ".py", ".js", ".ts", ".go", ".java", ".c", ".cpp", ".h"}
# 排除 vendored/build/deps —— 否则真 repo 上估价虚高一个数量级(node/ 冒烟实测:
# 不排除时 17.4M input tok / $55-275, 排除后 4.5M / $13-67)。
_IGNORE_DIRS = {".git", "target", "node_modules", ".venv", "__pycache__",
                "dist", "build", "vendor", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def _scan(repo_root: str) -> dict:
    root = Path(repo_root)
    doc_bytes = code_bytes = 0
    top_modules = set()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if _IGNORE_DIRS & set(rel_parts):          # 跳过 vendored/build/deps
            continue
        ext = p.suffix.lower()
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if ext in _DOC_EXT:
            doc_bytes += size
        elif ext in _CODE_EXT:
            code_bytes += size
            if len(rel_parts) > 1:                 # 顶层模块(与 detect 一致), 非每个叶目录
                top_modules.add(rel_parts[0])
    return {"doc_bytes": doc_bytes, "code_bytes": code_bytes, "n_modules": len(top_modules)}


def estimate_cost(repo_root: str) -> dict:
    s = _scan(repo_root)
    input_chars = s["doc_bytes"] + s["code_bytes"] * _CODE_SAMPLE_FRACTION
    est_input = int(input_chars / _CHARS_PER_TOKEN)
    est_concepts = max(1, s["n_modules"] * _CONCEPTS_PER_MODULE)
    est_output = est_concepts * _TOKENS_PER_CONCEPT_PAGE
    est_calls = max(1, -(-s["n_modules"] // _FANOUT_MODULES_PER_CALL))  # ceil
    total_k = (est_input + est_output) / 1000
    return {
        "est_input_tokens": est_input,
        "est_output_tokens": est_output,
        "est_agent_calls": est_calls,
        "est_concepts": est_concepts,
        "est_usd_low": round(total_k * _USD_PER_1K_LOW, 2),
        "est_usd_high": round(total_k * _USD_PER_1K_HIGH, 2),
        "is_estimate": True,
        "method": (
            f"heuristic (vendored/build dirs excluded): "
            f"input≈(doc_bytes+{_CODE_SAMPLE_FRACTION}*code_bytes)/{_CHARS_PER_TOKEN}; "
            f"output≈{_CONCEPTS_PER_MODULE} concepts/top-module * {_TOKENS_PER_CONCEPT_PAGE} tok "
            f"(est_concepts is a rough UPPER bound; 宁少勿多 curation lands lower, target 20-40); "
            f"usd @ {_USD_PER_1K_LOW}-{_USD_PER_1K_HIGH}/1K tok. ±50% — verify against real run."
        ),
        "scanned": s,
    }
