#!/usr/bin/env bash
# Marshal doctor —— 自体检 + 缺失自修复。输出单行 JSON,与 cwd 无关。
set -u
BLOCKED=()
FIXED=()

json_arr() {  # json_arr a b c -> ["a","b","c"];  无参 -> []
  local out="" x
  for x in "$@"; do out="$out\"$x\","; done
  printf '[%s]' "${out%,}"
}

emit() {  # emit <ok>。用 ${ARR[@]+...} 守卫,空数组在 set -u 下不报错且不产空元素。
  printf '{"ok":%s,"blocked":%s,"fixed":%s}\n' "$1" \
    "$(json_arr ${BLOCKED[@]+"${BLOCKED[@]}"})" \
    "$(json_arr ${FIXED[@]+"${FIXED[@]}"})"
}

# 1) CLAUDE_PLUGIN_ROOT 注入?(硬阻断)
if [ -z "${CLAUDE_PLUGIN_ROOT:-}" ] || [ ! -d "${CLAUDE_PLUGIN_ROOT:-/nonexistent}" ]; then
  BLOCKED+=("CLAUDE_PLUGIN_ROOT")
  emit false
  exit 0
fi
ROOT="$CLAUDE_PLUGIN_ROOT"

# 2) python3 >= 3.11?(硬阻断,不静默装系统 python)
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)' 2>/dev/null; then
  BLOCKED+=("python3>=3.11")
  emit false
  exit 0
fi

# 3) uv 已装?缺则自动安装(可被 MARSHAL_UV_INSTALLER 覆盖以便测试)
if ! command -v uv >/dev/null 2>&1; then
  INSTALLER="${MARSHAL_UV_INSTALLER:-curl -LsSf https://astral.sh/uv/install.sh | sh}"
  if eval "$INSTALLER" >/dev/null 2>&1; then
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv >/dev/null 2>&1; then
      FIXED+=("uv")
    else
      BLOCKED+=("uv-install-failed"); emit false; exit 0
    fi
  else
    BLOCKED+=("uv-install-failed"); emit false; exit 0
  fi
fi

emit true
exit 0
