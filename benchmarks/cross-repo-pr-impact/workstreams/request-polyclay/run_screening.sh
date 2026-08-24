#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <结果目录>" >&2
  exit 2
fi

output_dir=$(realpath -m "$1")
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
task_root=${MARSHAL_TASK_TMP:-/home/zhihao/hdd/marshal-task-tmp/request-polyclay}
cache_dir=$task_root/npm-cache

mkdir -p "$output_dir" "$task_root" "$cache_dir"
run_root=$(mktemp -d "$task_root/replay.XXXXXX")

cleanup() {
  rm -rf -- "$run_root"
}
trap cleanup EXIT

run_arm() {
  local arm=$1
  local polyclay_version=$2
  local request_version=$3
  local arm_dir=$run_root/$arm
  local install_log=$output_dir/$arm-install.log
  local probe_log=$output_dir/$arm-probe.json
  local status_file=$output_dir/$arm-exit-status.txt
  local versions_file=$output_dir/$arm-versions.json

  mkdir -p "$arm_dir"
  npm install \
    --prefix "$arm_dir" \
    --cache "$cache_dir" \
    --ignore-scripts \
    --omit=optional \
    --no-audit \
    --no-fund \
    --save-exact \
    "polyclay@$polyclay_version" \
    cradle@0.6.5 \
    "request@$request_version" \
    >"$install_log" 2>&1

  (
    cd "$arm_dir"
    node -e '
      const req = require("module").createRequire(process.cwd() + "/entry.js");
      console.log(JSON.stringify({
        polyclay: req("polyclay/package.json").version,
        cradle: req("cradle/package.json").version,
        request: req("request/package.json").version
      }));
    '
  ) >"$versions_file"

  set +e
  (cd "$arm_dir" && node "$script_dir/probe.js") >"$probe_log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$status_file"
}

run_arm a0 1.3.0 2.16.6
run_arm a1 1.3.0 2.18.0
run_arm a2 1.4.0 2.18.0

jq -n \
  --slurpfile a0 "$output_dir/a0-probe.json" \
  --slurpfile a1 "$output_dir/a1-probe.json" \
  --slurpfile a2 "$output_dir/a2-probe.json" \
  --slurpfile a0v "$output_dir/a0-versions.json" \
  --slurpfile a1v "$output_dir/a1-versions.json" \
  --slurpfile a2v "$output_dir/a2-versions.json" \
  --argjson a0s "$(<"$output_dir/a0-exit-status.txt")" \
  --argjson a1s "$(<"$output_dir/a1-exit-status.txt")" \
  --argjson a2s "$(<"$output_dir/a2-exit-status.txt")" \
  '{
    screened_at: "2026-08-24",
    contract: "PolyClay CouchAdapter.remove -> Cradle Database.remove -> request callback on an empty HTTP response",
    arms: [
      {arm: "A0", versions: $a0v[0], exit_status: $a0s, observation: $a0[0]},
      {arm: "A1", versions: $a1v[0], exit_status: $a1s, observation: $a1[0]},
      {arm: "A2", versions: $a2v[0], exit_status: $a2s, observation: $a2[0]}
    ],
    decision: "rejected",
    accepted_cases: 0,
    bounded_negatives: 0,
    a3_cases: 0
  }' >"$output_dir/summary.json"

jq -e '
  .arms[0] |
  .exit_status == 1 and
  .observation.adapter == "present" and
  .observation.callback == false and
  (.observation.error | contains("Cannot read properties of undefined"))
' "$output_dir/summary.json" >/dev/null
jq -e '
  .arms[1] |
  .exit_status == 0 and
  .observation.adapter == "present" and
  .observation.callback == true and
  .observation.error == null and
  .observation.responseJson == ""
' "$output_dir/summary.json" >/dev/null
jq -e '
  .arms[2] |
  .exit_status == 3 and
  .observation.adapter == "missing" and
  .observation.callback == false
' "$output_dir/summary.json" >/dev/null

echo "筛选完成：公开标签的因果方向被真实调用链推翻，正式接纳零条。"
