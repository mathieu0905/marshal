"""Onboard repo 探测 —— 确定性的"抽取简报"生成器。给 agent 一个起点:
语言分布 / 文档清单 / 模块图 / 候选概念种子(来自目录与模块名, 非概念定义)。
概念的真正综合与命名是 agent 的判断, 不在这里做。"""
from collections import Counter
from pathlib import Path

_LANG_BY_EXT = {".rs": "rust", ".py": "python", ".js": "js", ".ts": "ts",
                ".go": "go", ".java": "java", ".c": "c", ".cpp": "cpp"}
_DOC_EXT = {".md", ".rst", ".txt", ".mdx"}
# 与 estimate 共用同一套排除(vendored/build/deps), 否则真 repo 画像被依赖淹没
_IGNORE_DIRS = {".git", "target", "node_modules", ".venv", "__pycache__",
                "dist", "build", "vendor", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def detect_repo(repo_root: str) -> dict:
    root = Path(repo_root)
    langs: Counter = Counter()
    docs = []
    module_dirs: set[str] = set()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if _IGNORE_DIRS & set(rel_parts):          # 跳过 vendored/build/deps
            continue
        rel = p.relative_to(root).as_posix()
        ext = p.suffix.lower()
        if ext in _LANG_BY_EXT:
            langs[_LANG_BY_EXT[ext]] += 1
            if len(rel_parts) > 1:                  # 顶层模块 = 第一段路径
                module_dirs.add(rel_parts[0])
        elif ext in _DOC_EXT:
            docs.append({"path": rel, "bytes": p.stat().st_size})

    return {
        "repo_root": str(root),
        "languages": dict(langs),
        "doc_inventory": sorted(docs, key=lambda d: d["path"]),
        "module_map": sorted(module_dirs),
        "candidate_seeds": sorted(module_dirs),   # 目录名作候选概念种子起点
        "has_codeowners": (root / "CODEOWNERS").is_file(),
    }
