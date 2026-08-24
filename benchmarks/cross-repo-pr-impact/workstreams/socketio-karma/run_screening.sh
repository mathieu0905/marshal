#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 6 ]]; then
  echo "用法：$0 <已安装依赖的 Riot v2.3.12 仓> <Karma Git 仓> <Socket.IO Git 仓> <Node 6 bin 目录> <PhantomJS 1.9.8> <结果目录>" >&2
  exit 2
fi

riot_seed=$(realpath "$1")
karma_git=$(realpath "$2")
socketio_git=$(realpath "$3")
node_bin=$(realpath "$4")
phantomjs_bin=$(realpath "$5")
output=$(realpath -m "$6")
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
task_root=${MARSHAL_TASK_TMP:-/home/zhihao/hdd/marshal-task-tmp/socketio-karma-formal}
cache_dir=$task_root/npm-cache

riot_commit=18fb94ee2448bcebb0906a7ce813162e76ba13cf
karma_base=a6d0ca5b44b8d018c7f62a963f5faf1a3e605300
karma_dependency_update=67828aa45e4686698e4b0f4a3f0771f3e3933e25
karma_repair=3ab78d63dbd2569abaf0d588230fa8c1afc1048a
karma_release=e8cf653f82d724eeec02c50210105599305b13f2
socketio_old=e2ebd4349bf27c3839fc9a2700b42cf8390ac3bd
socketio_break=b73d9bea4efb48277eee685763026ff2df5a79ab
socketio_new=ddb3445f3d9009554577bbd05b033031e20e23d8

mkdir -p "$task_root" "$cache_dir" "$output"
run_root=$(mktemp -d "$task_root/run.XXXXXX")

cleanup() {
  rm -rf -- "$run_root"
}
trap cleanup EXIT

export PATH="$node_bin:$PATH"
export PHANTOMJS_BIN="$phantomjs_bin"
export npm_config_cache="$cache_dir"
export npm_config_registry=https://registry.npmmirror.com

git -C "$socketio_git" diff "$socketio_break^" "$socketio_break" \
  -- lib/client.js lib/index.js lib/namespace.js lib/socket.js \
  >"$output/socketio-object-change.diff"
git -C "$karma_git" diff "$karma_repair^" "$karma_repair" \
  -- lib/server.js \
  >"$output/karma-maintainer-repair.diff"
git -C "$karma_git" diff "$karma_base" "$karma_release" \
  -- CHANGELOG.md lib/server.js package.json \
  >"$output/karma-0.13.19-release.diff"
git -C "$karma_git" diff "$karma_dependency_update^" "$karma_dependency_update" \
  -- package.json \
  >"$output/karma-dependency-declaration.diff"

cp -a --reflink=auto "$riot_seed" "$run_root/old-template"
git -C "$run_root/old-template" checkout --detach --force "$riot_commit" >/dev/null
git -C "$karma_git" show "$karma_base:lib/server.js" \
  >"$run_root/old-template/node_modules/karma/lib/server.js"
git -C "$karma_git" show "$karma_base:package.json" \
  >"$run_root/old-template/node_modules/karma/package.json"
(
  cd "$run_root/old-template"
  npm install --no-save --ignore-scripts socket.io@1.3.7
) >"$output/socketio-1.3.7-install.log" 2>&1

cp -a --reflink=auto "$run_root/old-template" "$run_root/new-template"
(
  cd "$run_root/new-template"
  npm install --no-save --ignore-scripts socket.io@1.4.0
) >"$output/socketio-1.4.0-install.log" 2>&1

for arm in a0 a1 a2 source-code-only transitive-deps-only release-0.13.19; do
  template=old-template
  case "$arm" in
    a1|a2|transitive-deps-only|release-0.13.19) template=new-template ;;
  esac
  cp -a --reflink=auto "$run_root/$template" "$run_root/$arm"
done

patch -d "$run_root/source-code-only/node_modules/socket.io" -p1 \
  <"$script_dir/socketio-object-change-on-1.3.7.patch" >/dev/null

patch -d "$run_root/a2/node_modules/karma" -p1 \
  <"$output/karma-maintainer-repair.diff" >/dev/null

rm -rf -- "$run_root/transitive-deps-only/node_modules/socket.io/lib"
cp -a "$run_root/old-template/node_modules/socket.io/lib" \
  "$run_root/transitive-deps-only/node_modules/socket.io/lib"
cp "$run_root/old-template/node_modules/socket.io/index.js" \
  "$run_root/transitive-deps-only/node_modules/socket.io/index.js"

patch -d "$run_root/release-0.13.19/node_modules/karma" -p1 \
  <"$output/karma-0.13.19-release.diff" >/dev/null

printf '[]\n' >"$output/observations.json"
printf 'arm\tkarma\tsocket_io\texit_code\ttests_completed\thistorical_error\tsource_internal_error\tcontract_result\n' \
  >"$output/run-results.tsv"

run_arm() {
  local arm=$1
  local source_code=$2
  local target_code=$3
  local repo=$run_root/$arm
  local log=$output/$arm.log
  local versions=$output/$arm-versions.json

  (
    cd "$repo"
    node "$script_dir/record-versions.js"
  ) >"$versions"

  set +e
  (
    cd "$repo"
    timeout --signal=TERM --kill-after=5s 15s \
      node node_modules/karma/bin/karma start test/karma.conf.js --single-run
  ) >"$log" 2>&1
  local status=$?
  set -e

  local completed=false
  local historical_error=false
  local source_internal_error=false
  local contract_result=fail
  if grep -E 'Executed 91 of 91.*SUCCESS' "$log" >/dev/null; then
    completed=true
  fi
  if grep -F 'TypeError: sockets.forEach is not a function' "$log" >/dev/null; then
    historical_error=true
  fi
  if grep -F "Cannot find module 'has-binary-data'" "$log" >/dev/null; then
    source_internal_error=true
  fi
  if [[ "$completed" == true && "$historical_error" == false && "$status" -eq 0 ]]; then
    contract_result=pass
  elif [[ "$source_internal_error" == true ]]; then
    contract_result=not_reached
  fi

  local karma_version socket_version
  karma_version=$(jq -r .karma_version "$versions")
  socket_version=$(jq -r .socket_io_version "$versions")
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$arm" "$karma_version" "$socket_version" "$status" "$completed" \
    "$historical_error" "$source_internal_error" "$contract_result" >>"$output/run-results.tsv"

  jq \
    --arg arm "$arm" \
    --arg source_code "$source_code" \
    --arg target_code "$target_code" \
    --argjson versions "$(<"$versions")" \
    --argjson exit_code "$status" \
    --argjson tests_completed "$completed" \
    --argjson historical_error "$historical_error" \
    --argjson source_internal_error "$source_internal_error" \
    --arg contract_result "$contract_result" \
    '. + [{
      arm: $arm,
      source_code: $source_code,
      target_code: $target_code,
      versions: $versions,
      exit_code: $exit_code,
      tests_completed: $tests_completed,
      historical_error: $historical_error,
      source_internal_error: $source_internal_error,
      contract_result: $contract_result
    }]' "$output/observations.json" >"$output/observations.next.json"
  mv "$output/observations.next.json" "$output/observations.json"
}

run_arm a0 "$socketio_old" "$karma_base"
run_arm a1 "$socketio_new" "$karma_base"
run_arm a2 "$socketio_new" "$karma_repair"
run_arm source-code-only "$socketio_break on the 1.3.7 package and dependency tree" "$karma_base"
run_arm transitive-deps-only "$socketio_old code with the 1.4.0 dependency tree" "$karma_base"
run_arm release-0.13.19 "$socketio_new" "$karma_release"

jq -n \
  --arg riot_commit "$riot_commit" \
  --arg karma_base "$karma_base" \
  --arg karma_dependency_update "$karma_dependency_update" \
  --arg karma_repair "$karma_repair" \
  --arg karma_release "$karma_release" \
  --arg socketio_old "$socketio_old" \
  --arg socketio_break "$socketio_break" \
  --arg socketio_new "$socketio_new" \
  --slurpfile observations "$output/observations.json" '
  {
    screened_at: "2026-08-25",
    native_contract: "Riot v2.3.12 PhantomJS browser suite through Karma",
    native_command: "node node_modules/karma/bin/karma start test/karma.conf.js --single-run",
    expected_test_count: 91,
    commits: {
      riot: $riot_commit,
      karma_base: $karma_base,
      karma_dependency_update: $karma_dependency_update,
      karma_repair: $karma_repair,
      karma_release: $karma_release,
      socket_io_old: $socketio_old,
      socket_io_object_change: $socketio_break,
      socket_io_new: $socketio_new
    },
    observations: $observations[0],
    decision: "accept_one_chain_independent_causal_case",
    causal_label: "socket_io_object_shape_change_requires_karma_production_adaptation",
    dependency_declaration_contribution: "exposes_the_break_only",
    release_version_contribution: "none_beyond_shipping_the_production_adaptation",
    transitive_dependency_ablation: "not_interpretable_because_socket_io_1.3.7_code_requires_the_removed_has_binary_data_module",
    bounded_negative_labels: 0,
    accepted_a3_cases: 0
  }' >"$output/summary.json"

jq -e '
  def arm($name): .observations[] | select(.arm == $name);
  (arm("a0") | .contract_result == "pass" and .tests_completed and (.historical_error | not)) and
  (arm("a1") | .contract_result == "fail" and .tests_completed and .historical_error) and
  (arm("a2") | .contract_result == "pass" and .tests_completed and (.historical_error | not)) and
  (arm("source-code-only") | .contract_result == "fail" and .tests_completed and .historical_error) and
  (arm("transitive-deps-only") | .contract_result == "not_reached" and (.tests_completed | not) and (.historical_error | not) and .source_internal_error) and
  (arm("release-0.13.19") | .contract_result == "pass" and .tests_completed and (.historical_error | not))
' "$output/summary.json" >/dev/null

echo "筛选完成：因果三臂、源代码充分性消融和完整发布验证成立；传递依赖消融未到达目标合同。"
