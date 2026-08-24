#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <结果目录>" >&2
  exit 2
fi

output_dir=$(realpath -m "$1")
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
task_root=${MARSHAL_TASK_TMP:-$repo_root/.work/react-redux-provide-replay}
cache_dir=$task_root/npm-cache

mkdir -p "$output_dir" "$task_root" "$cache_dir" "$task_root/tmp"
export TMPDIR="$task_root/tmp"
run_root=$(mktemp -d "$task_root/run.XXXXXX")

cleanup() {
  rm -rf -- "$run_root"
}
trap cleanup EXIT

package_name=$(npm pack \
  react-redux-provide@5.1.0 \
  --pack-destination "$run_root" \
  --cache "$cache_dir" \
  --silent)
mkdir -p "$run_root/seed"
tar -xzf "$run_root/$package_name" -C "$run_root/seed" --strip-components=1

run_arm() {
  local arm=$1
  local source_version=$2
  local apply_repair=$3
  local arm_dir=$run_root/$arm
  local install_log=$output_dir/$arm-install.log
  local test_log=$output_dir/$arm-test.log
  local status_file=$output_dir/$arm-exit-status.txt
  local versions_file=$output_dir/$arm-versions.json

  mkdir -p "$arm_dir"
  cp -a "$run_root/seed/." "$arm_dir/"

  # 发布物把自身列作开发依赖。删除该项可避免 npm 安装无关的第二份目标包；
  # 每个臂都执行相同的环境处理。
  npm pkg delete devDependencies.react-redux-provide --prefix "$arm_dir"

  if [[ $apply_repair == yes ]]; then
    git -C "$arm_dir" apply "$script_dir/maintenance-production-repair.patch"
    npm install \
      --prefix "$arm_dir" \
      --cache "$cache_dir" \
      --ignore-scripts \
      --omit=optional \
      --no-audit \
      --no-fund \
      --legacy-peer-deps \
      --save-exact \
      "react-redux@$source_version" \
      is-plain-object@2.0.1 \
      >"$install_log" 2>&1
  else
    npm install \
      --prefix "$arm_dir" \
      --cache "$cache_dir" \
      --ignore-scripts \
      --omit=optional \
      --no-audit \
      --no-fund \
      --legacy-peer-deps \
      --save-exact \
      "react-redux@$source_version" \
      >"$install_log" 2>&1
  fi

  (
    cd "$arm_dir"
    node -e '
      const target = require("./package.json");
      const source = require("./node_modules/react-redux/package.json");
      console.log(JSON.stringify({
        node: process.version,
        target: target.version,
        source: source.version,
        declared_repair_dependency: target.dependencies["is-plain-object"] || null
      }));
    '
  ) >"$versions_file"

  set +e
  npm test --prefix "$arm_dir" -- --reporter dot >"$test_log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$status_file"

  if [[ $arm == a3-before || $arm == a3-after ]]; then
    (
      cd "$arm_dir"
      node -e '
        const value = require("react-redux/lib/utils/isPlainObject");
        const normalized = value && value.default ? value.default : value;
        console.log(JSON.stringify({
          raw_export_type: typeof value,
          enumerable_keys: Object.keys(value),
          normalized_export_type: typeof normalized,
          plain_object_result: normalized({ value: 1 }),
          array_result: normalized([])
        }));
      '
    ) >"$output_dir/$arm-export-probe.json"
  fi
}

run_arm a0 4.1.2 no
run_arm a1 4.2.0 no
run_arm a2 4.2.0 yes
run_arm a3-before 4.0.5 no
run_arm a3-after 4.0.6 no

jq -n \
  --slurpfile a0v "$output_dir/a0-versions.json" \
  --slurpfile a1v "$output_dir/a1-versions.json" \
  --slurpfile a2v "$output_dir/a2-versions.json" \
  --slurpfile a3bv "$output_dir/a3-before-versions.json" \
  --slurpfile a3av "$output_dir/a3-after-versions.json" \
  --slurpfile a3bp "$output_dir/a3-before-export-probe.json" \
  --slurpfile a3ap "$output_dir/a3-after-export-probe.json" \
  --argjson a0s "$(<"$output_dir/a0-exit-status.txt")" \
  --argjson a1s "$(<"$output_dir/a1-exit-status.txt")" \
  --argjson a2s "$(<"$output_dir/a2-exit-status.txt")" \
  --argjson a3bs "$(<"$output_dir/a3-before-exit-status.txt")" \
  --argjson a3as "$(<"$output_dir/a3-after-exit-status.txt")" \
  --arg a0_tests "$(sed -n 's/.*\([0-9][0-9]*\) passing.*/\1/p' "$output_dir/a0-test.log" | tail -1)" \
  --arg a2_tests "$(sed -n 's/.*\([0-9][0-9]*\) passing.*/\1/p' "$output_dir/a2-test.log" | tail -1)" \
  --arg a3b_tests "$(sed -n 's/.*\([0-9][0-9]*\) passing.*/\1/p' "$output_dir/a3-before-test.log" | tail -1)" \
  --arg a3a_tests "$(sed -n 's/.*\([0-9][0-9]*\) passing.*/\1/p' "$output_dir/a3-after-test.log" | tail -1)" \
  '{
    screened_at: "2026-08-24",
    native_command: "npm test -- --reporter dot",
    causal_case: {
      source_change: "react-redux 4.1.2 -> 4.2.0",
      target_baseline: "react-redux-provide 5.1.0",
      maintainer_repair_release: "react-redux-provide 5.2.0",
      arms: [
        {arm: "A0", versions: $a0v[0], exit_status: $a0s, passing_tests: ($a0_tests | tonumber)},
        {arm: "A1", versions: $a1v[0], exit_status: $a1s, failure: "Cannot find module react-redux/lib/utils/isPlainObject"},
        {arm: "A2", versions: $a2v[0], exit_status: $a2s, passing_tests: ($a2_tests | tonumber)}
      ],
      decision: "accepted_single_positive_three_arm_case"
    },
    package_enhancements: {
      bounded_negatives: 0,
      a3: {
        source_change: "react-redux 4.0.5 -> 4.0.6",
        before: {versions: $a3bv[0], exit_status: $a3bs, passing_tests: ($a3b_tests | tonumber), export_probe: $a3bp[0]},
        after: {versions: $a3av[0], exit_status: $a3as, passing_tests: ($a3a_tests | tonumber), export_probe: $a3ap[0]},
        decision: "accepted_export_contract_compatibility_case"
      }
    },
    accepted_causal_cases: 1,
    bounded_negative_labels: 0,
    accepted_a3_cases: 1
  }' >"$output_dir/summary.json"

jq -e '
  .causal_case.arms[0] |
  .versions.target == "5.1.0" and .versions.source == "4.1.2" and
  .exit_status == 0 and .passing_tests == 6
' "$output_dir/summary.json" >/dev/null
jq -e '
  .causal_case.arms[1] |
  .versions.target == "5.1.0" and .versions.source == "4.2.0" and
  .exit_status == 1
' "$output_dir/summary.json" >/dev/null
grep -F "Cannot find module 'react-redux/lib/utils/isPlainObject'" \
  "$output_dir/a1-test.log" >/dev/null
jq -e '
  .causal_case.arms[2] |
  .versions.target == "5.1.0" and .versions.source == "4.2.0" and
  .versions.declared_repair_dependency == "2.0.1" and
  .exit_status == 0 and .passing_tests == 6
' "$output_dir/summary.json" >/dev/null
jq -e '
  .package_enhancements.a3 |
  .before.versions.source == "4.0.5" and .before.exit_status == 0 and .before.passing_tests == 6 and
  .before.export_probe.raw_export_type == "object" and
  .before.export_probe.normalized_export_type == "function" and
  .after.versions.source == "4.0.6" and .after.exit_status == 0 and .after.passing_tests == 6 and
  .after.export_probe.raw_export_type == "function" and
  .after.export_probe.normalized_export_type == "function"
' "$output_dir/summary.json" >/dev/null

echo "筛选完成：一个链独立三臂正例成立，限定负例为零，兼容变化增强臂成立。"
