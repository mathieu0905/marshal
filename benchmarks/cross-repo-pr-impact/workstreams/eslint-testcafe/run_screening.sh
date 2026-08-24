#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <结果目录>" >&2
  exit 2
fi

output_dir=$(realpath -m "$1")
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
task_root=${MARSHAL_TASK_TMP:-/home/zhihao/hdd/marshal-task-tmp/eslint-testcafe-replay}
cache_dir=$task_root/npm-cache
repo_dir=$task_root/testcafe-repository
target_commit=72e3c05af334c5a38e45e68e29df8cdaa7856bfc

mkdir -p "$output_dir" "$task_root" "$cache_dir"

if [[ ! -d $repo_dir/.git ]]; then
  git clone --filter=blob:none --no-checkout \
    https://github.com/DevExpress/testcafe.git "$repo_dir"
fi

if ! git -C "$repo_dir" cat-file -e "$target_commit^{commit}" 2>/dev/null; then
  git -C "$repo_dir" fetch origin "$target_commit"
fi

run_root=$(mktemp -d "$task_root/run.XXXXXX")

cleanup() {
  rm -rf -- "$run_root"
}
trap cleanup EXIT

mkdir -p "$run_root/runner" "$run_root/seed"
npm install \
  --prefix "$run_root/runner" \
  --cache "$cache_dir" \
  --no-audit \
  --no-fund \
  node@8.17.0 \
  >"$output_dir/node-runtime-install.log" 2>&1
node8=$run_root/runner/node_modules/node/bin/node
"$node8" --version >"$output_dir/node-runtime-version.txt"

git -C "$repo_dir" archive "$target_commit" | tar -x -C "$run_root/seed"

# 0.18.6 的宽版本范围现在会取得 2021 年之后的 QUnit 工具链和仅支持
# Node 20 的 Markdownlint，导致 Gulpfile 在进入 lint 任务前就无法加载。
# 这里固定到目标发布时已经存在的版本，三个因果臂共用同一环境恢复。
npm pkg set \
  'devDependencies.gulp-qunit-harness=1.0.2' \
  'devDependencies.qunit-harness=1.3.2' \
  'devDependencies.markdownlint=0.6.3' \
  'devDependencies.eslint=4.18.2' \
  --prefix "$run_root/seed"
npm install \
  --prefix "$run_root/seed" \
  --cache "$cache_dir" \
  --ignore-scripts \
  --omit=optional \
  --no-audit \
  --no-fund \
  --legacy-peer-deps \
  >"$output_dir/seed-install.log" 2>&1

run_arm() {
  local arm=$1
  local eslint_version=$2
  local apply_repair=$3
  local arm_dir=$run_root/$arm
  local install_log=$output_dir/$arm-source-install.log
  local lint_log=$output_dir/$arm-lint.log

  mkdir -p "$arm_dir"
  cp -a "$run_root/seed/." "$arm_dir/"

  if [[ $eslint_version != 4.18.2 ]]; then
    npm install \
      --prefix "$arm_dir" \
      --cache "$cache_dir" \
      --ignore-scripts \
      --omit=optional \
      --no-audit \
      --no-fund \
      --legacy-peer-deps \
      --save-exact \
      "eslint@$eslint_version" \
      >"$install_log" 2>&1
  else
    printf '种子环境已固定 ESLint %s。\n' "$eslint_version" >"$install_log"
  fi

  if [[ $apply_repair == yes ]]; then
    git -C "$arm_dir" apply "$script_dir/maintainer-lint-repair.patch"
  fi

  (
    cd "$arm_dir"
    node -e '
      const read = name => require(`./node_modules/${name}/package.json`).version;
      console.log(JSON.stringify({
        target_commit: process.env.TARGET_COMMIT,
        target_version: require("./package.json").version,
        eslint: read("eslint"),
        gulp_eslint: read("gulp-eslint"),
        gulp: read("gulp"),
        markdownlint: read("markdownlint"),
        gulp_qunit_harness: read("gulp-qunit-harness"),
        qunit_harness: read("qunit-harness")
      }));
    '
  ) >"$output_dir/$arm-versions.json"

  set +e
  (
    cd "$arm_dir"
    TARGET_COMMIT=$target_commit "$node8" ./node_modules/gulp/bin/gulp.js lint
  ) >"$lint_log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$output_dir/$arm-exit-status.txt"
}

export TARGET_COMMIT=$target_commit
run_arm a0 4.18.2 no
run_arm a1 4.19.0 no
run_arm a2 4.19.0 yes

jq -n \
  --slurpfile a0v "$output_dir/a0-versions.json" \
  --slurpfile a1v "$output_dir/a1-versions.json" \
  --slurpfile a2v "$output_dir/a2-versions.json" \
  --argjson a0s "$(<"$output_dir/a0-exit-status.txt")" \
  --argjson a1s "$(<"$output_dir/a1-exit-status.txt")" \
  --argjson a2s "$(<"$output_dir/a2-exit-status.txt")" \
  '{
    screened_at: "2026-08-24",
    native_command: "node 8.17.0 ./node_modules/gulp/bin/gulp.js lint",
    source_change: {
      package: "eslint",
      before: "4.18.2",
      after: "4.19.0",
      relevant_commit: "8d3814e4ae823e58f40539047bb35bcaf5c76660"
    },
    target: {
      repository: "DevExpress/testcafe",
      baseline_version: "0.18.6",
      baseline_commit: "72e3c05af334c5a38e45e68e29df8cdaa7856bfc",
      repair_commit: "de11b259db998c147f4d839607c88d257ea7b88a",
      repair_release: "0.19.2-dev20180316"
    },
    arms: [
      {arm: "A0", versions: $a0v[0], exit_status: $a0s, result: "lint_passed"},
      {
        arm: "A1",
        versions: $a1v[0],
        exit_status: $a1s,
        result: "lint_failed",
        failure: "selector-test.js:178:9 Unexpected control character(s) in regular expression: \\x00 (no-control-regex)"
      },
      {arm: "A2", versions: $a2v[0], exit_status: $a2s, result: "lint_passed"}
    ],
    decision: "accepted_single_positive_three_arm_screening",
    repair_scope: "one maintainer-authored test-fixture regular-expression change",
    actual_repair_repository: "DevExpress/testcafe",
    intermediary_repository_changed: false,
    bounded_negative_labels: 0,
    a3_cases: 0,
    accepted_causal_cases: 1
  }' >"$output_dir/summary.json"

jq -e '
  .arms[0] |
  .versions.target_version == "0.18.6" and
  .versions.eslint == "4.18.2" and
  .versions.gulp_eslint == "4.0.2" and
  .exit_status == 0
' "$output_dir/summary.json" >/dev/null
jq -e '
  .arms[1] |
  .versions.target_version == "0.18.6" and
  .versions.eslint == "4.19.0" and
  .versions.gulp_eslint == "4.0.2" and
  .exit_status == 1
' "$output_dir/summary.json" >/dev/null
grep -F '178:9  error  Unexpected control character(s) in regular expression: \x00  no-control-regex' \
  "$output_dir/a1-lint.log" >/dev/null
grep -F '1 problem (1 error, 0 warnings)' "$output_dir/a1-lint.log" >/dev/null
jq -e '
  .arms[2] |
  .versions.target_version == "0.18.6" and
  .versions.eslint == "4.19.0" and
  .versions.gulp_eslint == "4.0.2" and
  .exit_status == 0
' "$output_dir/summary.json" >/dev/null

echo "筛选完成：TestCafe 的单正例三臂成立；gulp-eslint 未修改；限定负例与 A3 均为零。"
