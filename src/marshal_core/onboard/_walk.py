"""Onboard 目录遍历共享常量 —— estimate 与 detect 逐字共用这两组, 抽此避免漂移。"""

# 排除 vendored/build/deps —— 否则真 repo 的估价/画像被依赖代码淹没
_IGNORE_DIRS = {".git", "target", "node_modules", ".venv", "__pycache__",
                "dist", "build", "vendor", ".mypy_cache", ".pytest_cache", ".ruff_cache"}

_DOC_EXT = {".md", ".rst", ".txt", ".mdx"}
