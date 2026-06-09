# 发版 Marshal 消费侧 plugin(维护侧)

`plugins/marshal/` 下的 `marshal_core/` 与 `marshal_pack_cowboy/` 是**生成物**(由 `scripts/build_plugin.py` 从 `src/` 同步),**不要手改**;改逻辑改 `src/`,再重跑打包脚本。

1. 改不变量 / 跑棘轮(照旧落根 `marshal.db`)。
2. bump `plugins/marshal/.claude-plugin/plugin.json` 的 `version`。
3. 跑 `.venv/bin/python scripts/build_plugin.py`(从 manifest 取版本,导出快照 + 同步包/references)。
4. `.venv/bin/python -m pytest -q && .venv/bin/ruff check src tests scripts`。
5. `git add plugins/ docs/ && git commit && git push`(必要时 `git tag vX.Y.Z`)。

队友 `/plugin update` 即获新不变量;其本地 `gate_run` 不受影响。
