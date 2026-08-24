#!/usr/bin/env bash

set -uo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[123]$ ]]; then
  echo "用法：$0 <重复编号：1、2 或 3>" >&2
  exit 2
fi

repeat=$1
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
result_root=${TERSER_RESULT_ROOT:-$script_dir/results/terser-unified-430-repetitions-2026-08-24}
repeat_dir=$result_root/repeat-$repeat
input_dir=${TERSER_INPUT_DIR:-$script_dir/results/terser-formal-repetitions-2026-08-24/inputs}

assetgraph_seed=${TERSER_ASSETGRAPH_SEED:-/tmp/terser-assetgraph-run.LLFXqx}
ui5_seed=${TERSER_UI5_SEED:-/tmp/ui5-terser-screen.GtjUHb}
preconstruct_seed=${TERSER_PRECONSTRUCT_SEED:-/tmp/preconstruct-terser-screen.6oxvaO/a0}
preconstruct_packages=${TERSER_PRECONSTRUCT_PACKAGES:-/tmp/preconstruct-terser-screen.6oxvaO/terser-packages}
angular_seed=${TERSER_ANGULAR_SEED:-/tmp/terser-negative-screen.gdMiQu/angular-base}
angular_baseline=${TERSER_ANGULAR_BASELINE:-/tmp/angular-terser-formal-baseline}
angular_terser_421=${TERSER_ANGULAR_421_SOURCE:-/tmp/terser-negative-screen.gdMiQu/terser-4.2.1}
terser_430_source=${TERSER_430_SOURCE:-/tmp/ui5-terser-screen.GtjUHb/a1/node_modules/terser}
yarn_bin_dir=${TERSER_YARN_BIN_DIR:-/tmp/marshal-yarn-1.22.19/node_modules/.bin}

if [[ -e $repeat_dir ]]; then
  echo "拒绝覆盖已有正式重复目录：$repeat_dir" >&2
  exit 3
fi

required_paths=(
  "$assetgraph_seed/a0"
  "$assetgraph_seed/a1"
  "$assetgraph_seed/a3-before"
  "$ui5_seed/a0"
  "$ui5_seed/a1"
  "$ui5_seed/a3-before"
  "$preconstruct_seed/node_modules"
  "$preconstruct_packages/terser-4.2.0.tgz"
  "$preconstruct_packages/terser-4.2.1.tgz"
  "$angular_seed/node_modules"
  "$angular_baseline/packages/angular_devkit/architect/testing/test-project-host.ts"
  "$angular_baseline/packages/angular_devkit/build_angular/test/browser/differential_loading_spec_large.ts"
  "$angular_terser_421/package.json"
  "$terser_430_source/package.json"
  "$yarn_bin_dir/yarn"
)
for path in "${required_paths[@]}"; do
  if [[ ! -e $path ]]; then
    echo "缺少正式重复输入：$path" >&2
    exit 4
  fi
done

marshal_user_home=$(getent passwd "$(id -u)" | cut -d: -f6)
nvm_script=$marshal_user_home/.nvm/nvm.sh
if [[ ! -f $nvm_script ]]; then
  echo "找不到 nvm：$nvm_script" >&2
  exit 5
fi

work_root=$(mktemp -d "/tmp/marshal-terser-formal-r${repeat}.XXXXXX")
mkdir -p "$repeat_dir/runs" "$work_root/packages"
tar -xzf "$preconstruct_packages/terser-4.2.0.tgz" -C "$work_root/packages"
mv "$work_root/packages/package" "$work_root/packages/terser-4.2.0"
tar -xzf "$preconstruct_packages/terser-4.2.1.tgz" -C "$work_root/packages"
mv "$work_root/packages/package" "$work_root/packages/terser-4.2.1"
source "$nvm_script"

{
  printf 'repeat=%s\n' "$repeat"
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'assetgraph_seed=%s\n' "$assetgraph_seed"
  printf 'ui5_seed=%s\n' "$ui5_seed"
  printf 'preconstruct_seed=%s\n' "$preconstruct_seed"
  printf 'angular_seed=%s\n' "$angular_seed"
  printf 'angular_baseline=%s\n' "$angular_baseline"
  printf 'terser_430_source=%s\n' "$terser_430_source"
  printf 'yarn_bin=%s\n' "$yarn_bin_dir/yarn"
  printf 'platform=%s\n' "$(uname -a)"
} >"$repeat_dir/environment.txt"

printf 'repeat\trepository\tconfig\texpected_version\tactual_version\texpected_result\tstarted_at\tfinished_at\tduration_seconds\texit_code\tcontract_ok\tversion_ok\tdirection_ok\n' \
  >"$repeat_dir/run-results.tsv"

copy_seed() {
  local source_dir=$1
  local destination=$2
  mkdir -p "$destination"
  cp -r --reflink=auto --no-preserve=ownership "$source_dir/." "$destination/"
}

install_terser_source() {
  local source_dir=$1
  local target_dir=$2
  local preserved_dependencies=
  if [[ -d $target_dir/node_modules ]]; then
    preserved_dependencies=$(mktemp -d "$work_root/preserved-terser-dependencies.XXXXXX")
    mv "$target_dir/node_modules" "$preserved_dependencies/node_modules"
  fi
  find "$target_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  cp -r --no-preserve=ownership "$source_dir/." "$target_dir/"
  if [[ -n $preserved_dependencies ]]; then
    if [[ -d $target_dir/node_modules ]]; then
      find "$target_dir/node_modules" -mindepth 0 -maxdepth 0 -exec rm -rf -- {} +
    fi
    mv "$preserved_dependencies/node_modules" "$target_dir/node_modules"
    rmdir "$preserved_dependencies"
  fi
}

record_result() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$repeat" "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" \
    "${10}" "${11}" "${12}" >>"$repeat_dir/run-results.tsv"
}

unexpected=0

nvm use 10.24.1 >/dev/null
for config in a0 a1 a2 a3-before a3-after; do
  case $config in
    a0) seed=$assetgraph_seed/a0; expected_version=4.2.1; expected_result=pass ;;
    a1) seed=$assetgraph_seed/a1; expected_version=4.3.0; expected_result=fail_output_contract ;;
    a2) seed=$assetgraph_seed/a1; expected_version=4.3.0; expected_result=pass ;;
    a3-before) seed=$assetgraph_seed/a3-before; expected_version=4.2.0; expected_result=pass ;;
    a3-after) seed=$assetgraph_seed/a0; expected_version=4.2.1; expected_result=pass ;;
  esac
  consumer=$work_root/assetgraph/$config
  run_dir=$repeat_dir/runs/assetgraph/$config
  mkdir -p "$run_dir"
  copy_seed "$seed" "$consumer"
  if [[ $config == a1 || $config == a2 ]]; then
    install_terser_source "$terser_430_source" "$consumer/node_modules/terser"
  fi
  if [[ $config == a2 ]]; then
    git -C "$consumer" apply "$input_dir/assetgraph-repair.patch"
  fi
  printf '%s\n' "./node_modules/.bin/mocha test/transforms/buildProduction.js --grep='issue #69'" >"$run_dir/command.txt"
  started_at=$(date --iso-8601=seconds); started_epoch=$(date +%s)
  (cd "$consumer" && timeout --signal=TERM 10m ./node_modules/.bin/mocha \
    test/transforms/buildProduction.js --grep='issue #69') >"$run_dir/test.log" 2>&1
  exit_code=$?
  finished_epoch=$(date +%s); finished_at=$(date --iso-8601=seconds)
  actual_version=$(node -p "require('$consumer/node_modules/terser/package.json').version")
  printf 'terser=%s\nnode=%s\n' "$actual_version" "$(node --version)" >"$run_dir/versions.txt"
  version_ok=false; [[ $actual_version == "$expected_version" ]] && version_ok=true
  contract_ok=false
  if [[ $expected_result == pass ]] && rg -q '1 passing' "$run_dir/test.log"; then contract_ok=true; fi
  if [[ $expected_result == fail_output_contract ]] \
    && rg -q '0 passing' "$run_dir/test.log" \
    && rg -q 'define\\\("main",function' "$run_dir/test.log"; then contract_ok=true; fi
  direction_ok=false; [[ $version_ok == true && $contract_ok == true ]] && direction_ok=true
  [[ $direction_ok == true ]] || unexpected=$((unexpected + 1))
  record_result assetgraph/assetgraph-builder "$config" "$expected_version" "$actual_version" \
    "$expected_result" "$started_at" "$finished_at" "$((finished_epoch-started_epoch))" \
    "$exit_code" "$contract_ok" "$version_ok" "$direction_ok"
done

for config in a0 a1 a2 a3-before a3-after; do
  case $config in
    a0) seed=$ui5_seed/a0; expected_version=4.2.1; expected_result=pass ;;
    a1) seed=$ui5_seed/a1; expected_version=4.3.0; expected_result=fail_output_contract ;;
    a2) seed=$ui5_seed/a1; expected_version=4.3.0; expected_result=pass ;;
    a3-before) seed=$ui5_seed/a3-before; expected_version=4.2.0; expected_result=pass ;;
    a3-after) seed=$ui5_seed/a0; expected_version=4.2.1; expected_result=pass ;;
  esac
  consumer=$work_root/ui5/$config
  run_dir=$repeat_dir/runs/ui5/$config
  mkdir -p "$run_dir"
  copy_seed "$seed" "$consumer"
  if [[ $config == a2 ]]; then
    git -C "$consumer" apply "$input_dir/ui5-repair.patch"
  fi
  "$consumer/node_modules/.bin/rimraf" "$consumer/test/tmp"
  printf '%s\n' "./node_modules/.bin/ava test/lib/builder/builder.js --serial" >"$run_dir/command.txt"
  started_at=$(date --iso-8601=seconds); started_epoch=$(date +%s)
  (cd "$consumer" && timeout --signal=TERM 10m ./node_modules/.bin/ava \
    test/lib/builder/builder.js --serial) >"$run_dir/test.log" 2>&1
  exit_code=$?
  finished_epoch=$(date +%s); finished_at=$(date --iso-8601=seconds)
  actual_version=$(node -p "require('$consumer/node_modules/terser/package.json').version")
  printf 'terser=%s\nnode=%s\n' "$actual_version" "$(node --version)" >"$run_dir/versions.txt"
  version_ok=false; [[ $actual_version == "$expected_version" ]] && version_ok=true
  contract_ok=false
  if [[ $expected_result == pass ]] && rg -q '17 tests passed' "$run_dir/test.log"; then contract_ok=true; fi
  if [[ $expected_result == fail_output_contract ]] \
    && rg -q '6 tests failed' "$run_dir/test.log"; then contract_ok=true; fi
  direction_ok=false; [[ $version_ok == true && $contract_ok == true ]] && direction_ok=true
  [[ $direction_ok == true ]] || unexpected=$((unexpected + 1))
  record_result SAP/ui5-builder "$config" "$expected_version" "$actual_version" \
    "$expected_result" "$started_at" "$finished_at" "$((finished_epoch-started_epoch))" \
    "$exit_code" "$contract_ok" "$version_ok" "$direction_ok"
done

nvm use 12.22.12 >/dev/null
export PATH="$yarn_bin_dir:$PATH"
for config in a0 a1 a2 a3-before a3-after; do
  case $config in
    a0) expected_version=4.2.1; expected_result=pass ;;
    a1) expected_version=4.3.0; expected_result=fail_snapshot_contract ;;
    a2) expected_version=4.3.0; expected_result=pass ;;
    a3-before) expected_version=4.2.0; expected_result=pass ;;
    a3-after) expected_version=4.2.1; expected_result=pass ;;
  esac
  consumer=$work_root/preconstruct/$config
  run_dir=$repeat_dir/runs/preconstruct/$config
  mkdir -p "$run_dir"
  copy_seed "$preconstruct_seed" "$consumer"
  if [[ $config == a1 || $config == a2 ]]; then
    install_terser_source "$terser_430_source" \
      "$consumer/packages/preconstruct/node_modules/terser"
  else
    install_terser_source "$work_root/packages/terser-$expected_version" \
      "$consumer/packages/preconstruct/node_modules/terser"
  fi
  (cd "$consumer/build" && yarn preconstruct dev) >"$run_dir/preconstruct-dev.log" 2>&1
  if [[ $config == a2 ]]; then
    git -C "$consumer" apply --unidiff-zero "$input_dir/preconstruct-repair.patch"
  fi
  git -C "$consumer" diff >"$run_dir/applied.diff"
  printf '%s\n' "jest basic.ts and build.ts --runInBand, selecting three historical output cases" \
    >"$run_dir/command.txt"
  started_at=$(date --iso-8601=seconds); started_epoch=$(date +%s)
  (cd "$consumer" && timeout --signal=TERM 15m ./node_modules/.bin/jest \
    packages/preconstruct/src/build/__tests__/basic.ts \
    packages/preconstruct/src/build/__tests__/build.ts --runInBand --no-cache \
    -t='^(basic|umd with dep on other module|monorepo umd with dep on other module)$') \
    >"$run_dir/test.log" 2>&1
  exit_code=$?
  finished_epoch=$(date +%s); finished_at=$(date --iso-8601=seconds)
  actual_version=$(node -p "require('$consumer/packages/preconstruct/node_modules/terser/package.json').version")
  printf 'terser=%s\nnode=%s\nyarn=%s\n' "$actual_version" "$(node --version)" "$(yarn --version)" \
    >"$run_dir/versions.txt"
  version_ok=false; [[ $actual_version == "$expected_version" ]] && version_ok=true
  contract_ok=false
  if [[ $expected_result == pass ]] \
    && rg -q 'Tests:.*3 passed' "$run_dir/test.log" \
    && rg -q 'Snapshots:.*35 passed' "$run_dir/test.log"; then contract_ok=true; fi
  if [[ $expected_result == fail_snapshot_contract ]] \
    && rg -q 'Tests:.*3 failed' "$run_dir/test.log" \
    && rg -q 'Snapshots:.*11 failed' "$run_dir/test.log"; then contract_ok=true; fi
  direction_ok=false; [[ $version_ok == true && $contract_ok == true ]] && direction_ok=true
  [[ $direction_ok == true ]] || unexpected=$((unexpected + 1))
  record_result preconstruct/preconstruct "$config" "$expected_version" "$actual_version" \
    "$expected_result" "$started_at" "$finished_at" "$((finished_epoch-started_epoch))" \
    "$exit_code" "$contract_ok" "$version_ok" "$direction_ok"
done

for config in a0 a1; do
  case $config in
    a0) expected_version=4.2.1; package_source=$angular_terser_421 ;;
    a1) expected_version=4.3.0; package_source=$terser_430_source ;;
  esac
  consumer=$work_root/angular/$config
  run_dir=$repeat_dir/runs/angular/$config
  mkdir -p "$run_dir"
  copy_seed "$angular_seed" "$consumer"
  cp --no-preserve=ownership \
    "$angular_baseline/packages/angular_devkit/architect/testing/test-project-host.ts" \
    "$consumer/packages/angular_devkit/architect/testing/test-project-host.ts"
  cp --no-preserve=ownership \
    "$angular_baseline/packages/angular_devkit/build_angular/test/browser/differential_loading_spec_large.ts" \
    "$consumer/packages/angular_devkit/build_angular/test/browser/differential_loading_spec_large.ts"
  git -C "$consumer" apply "$input_dir/angular-measurement.patch"
  controlled_terser=$consumer/packages/angular_devkit/build_angular/node_modules/terser
  install_terser_source "$package_source" "$controlled_terser"
  find "$consumer/node_modules" -maxdepth 1 -type d -name '.cache*' -exec find {} -depth -delete \;
  output_json=$run_dir/generated-javascript.json
  printf '%s\n' "NG_BUILD_FULL_DIFFERENTIAL=1 node ./bin/devkit-admin test --large --full --glob=packages/angular_devkit/build_angular/test/browser/differential_loading_spec_large.ts --filter='emits the right ES formats'" \
    >"$run_dir/command.txt"
  started_at=$(date --iso-8601=seconds); started_epoch=$(date +%s)
  (cd "$consumer" && NG_BUILD_FULL_DIFFERENTIAL=1 TERSER_PROBE_OUTPUT="$output_json" \
    timeout --signal=TERM 20m node ./bin/devkit-admin test --large --full \
    --glob=packages/angular_devkit/build_angular/test/browser/differential_loading_spec_large.ts \
    --filter='emits the right ES formats') >"$run_dir/test.log" 2>&1
  exit_code=$?
  finished_epoch=$(date +%s); finished_at=$(date --iso-8601=seconds)
  actual_version=$(node -p "require('$controlled_terser/package.json').version")
  nested_source_map=$(node -p "require('$controlled_terser/node_modules/source-map/package.json').version")
  printf 'terser=%s\nsource_map=%s\nnode=%s\n' "$actual_version" "$nested_source_map" "$(node --version)" \
    >"$run_dir/versions.txt"
  node - "$output_json" >"$run_dir/output-metrics.json" <<'NODE'
const fs = require('fs');
const file = process.argv[2];
const outputs = JSON.parse(fs.readFileSync(file, 'utf8'));
const values = Object.values(outputs);
const joined = values.join('\n');
process.stdout.write(JSON.stringify({
  generated_javascript_files: values.length,
  generated_bytes: values.reduce((total, value) => total + Buffer.byteLength(value), 0),
  double_parenthesized_function_arguments: (joined.match(/\(\(function\b/g) || []).length,
}, null, 2) + '\n');
NODE
  version_ok=false; [[ $actual_version == "$expected_version" && $nested_source_map == 0.6.1 ]] && version_ok=true
  contract_ok=false
  if [[ $exit_code -eq 0 ]] && rg -q '1 spec, 0 failures' "$run_dir/test.log"; then contract_ok=true; fi
  metric=$(jq -r .double_parenthesized_function_arguments "$run_dir/output-metrics.json")
  metric_ok=false
  if [[ $config == a0 && $metric -eq 0 ]]; then metric_ok=true; fi
  if [[ $config == a1 && $metric -eq 531 ]]; then metric_ok=true; fi
  direction_ok=false
  [[ $version_ok == true && $contract_ok == true && $metric_ok == true ]] && direction_ok=true
  [[ $direction_ok == true ]] || unexpected=$((unexpected + 1))
  record_result angular/angular-cli "$config" "$expected_version" "$actual_version" \
    pass_bounded_contract "$started_at" "$finished_at" "$((finished_epoch-started_epoch))" \
    "$exit_code" "$contract_ok" "$version_ok" "$direction_ok"
done

node - "$repeat_dir/runs/angular/a0/generated-javascript.json" \
  "$repeat_dir/runs/angular/a1/generated-javascript.json" \
  >"$repeat_dir/angular-output-comparison.json" <<'NODE'
const fs = require('fs');
const before = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const after = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const names = [...new Set([...Object.keys(before), ...Object.keys(after)])].sort();
const changed = names.filter(name => before[name] !== after[name]);
const unchanged = names.filter(name => before[name] === after[name]);
process.stdout.write(JSON.stringify({ changed_files: changed, unchanged_files: unchanged }, null, 2) + '\n');
NODE

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$repeat_dir/environment.txt"

printf '正式重复 %s 完成：unexpected=%s，结果=%s\n' "$repeat" "$unexpected" "$repeat_dir"
printf '临时运行根目录：%s\n' "$work_root"
exit "$unexpected"
