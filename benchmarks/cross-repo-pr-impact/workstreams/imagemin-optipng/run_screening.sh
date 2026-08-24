#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "用法：$0 <恢复的目标仓克隆> <工作目录> <npm 缓存> <npm 2 CLI> <结果目录>" >&2
  exit 2
fi

target_repo=$(realpath "$1")
work_root=$(realpath -m "$2")
npm_cache=$(realpath -m "$3")
npm2=$(realpath "$4")
output=$(realpath -m "$5")
base_commit=94da609777c4af78dc06bd9a0f773531ec0635e6
repair_commit=b3f8796d8f78e09a4632277bea0bc709c7879b96

mkdir -p "$work_root" "$npm_cache" "$output"
export npm_config_cache="$npm_cache"
export npm_config_registry=https://registry.npmmirror.com

if [[ "$(node --version)" != "v6.17.1" ]]; then
  echo "需要 Node.js v6.17.1，当前为 $(node --version)" >&2
  exit 2
fi

for arm in a0 a1 a2 a3-before a3-after; do
  repo="$work_root/$arm"
  if [[ ! -d "$repo/.git" ]]; then
    git clone --shared "$target_repo" "$repo" >/dev/null
  fi
  git -C "$repo" checkout --detach --force "$base_commit" >/dev/null
  git -C "$repo" clean -fdx >/dev/null
done

git -C "$work_root/a2" diff "${repair_commit}^" "$repair_commit" \
  -- test/createVariablesSpec.js \
  | git -C "$work_root/a2" apply -

if [[ -n "${PREPARED_ARMS_ROOT:-}" ]]; then
  prepared=$(realpath "$PREPARED_ARMS_ROOT")
  for arm in a0 a1 a2 a3-before a3-after; do
    prepared_arm=$arm
    if [[ "$arm" == a3-after && ! -d "$prepared/a3-after/node_modules" ]]; then
      prepared_arm=a0
    fi
    cp -a "$prepared/$prepared_arm/node_modules" "$work_root/$arm/"
  done
  dependency_setup=prepared_cache_reuse
else
  (
    cd "$work_root/a1"
    node "$npm2" install --no-shrinkwrap
    node "$npm2" install --no-save imagemin@3.1.0 imagemin-optipng@4.2.0
  ) >"$output/dependency-install.log" 2>&1
  for arm in a0 a2 a3-before a3-after; do
    cp -a "$work_root/a1/node_modules" "$work_root/$arm/"
  done
  (
    cd "$work_root/a0"
    node "$npm2" install --no-save imagemin-optipng@4.1.0
  ) >"$output/a0-dependency-install.log" 2>&1
  cp -a "$work_root/a0/node_modules/." "$work_root/a3-after/node_modules/"
  (
    cd "$work_root/a3-before"
    node "$npm2" install --no-save imagemin-optipng@4.0.0
  ) >"$output/a3-before-dependency-install.log" 2>&1
  dependency_setup=fresh_install
fi

printf 'arm\toptipng_version\texit_code\tspecs\tfailures\tcontract_result\n' >"$output/run-results.tsv"
printf '[]\n' >"$output/observations.json"
for arm in a0 a1 a2 a3-before a3-after; do
  repo="$work_root/$arm"
  (
    cd "$repo"
    node "$npm2" ls imagemin imagemin-optipng
  ) >"$output/${arm}-versions.log" 2>&1
  version=$(cd "$repo" && node -p "require('imagemin-optipng/package.json').version")
  git -C "$repo" diff -- test/createVariablesSpec.js >"$output/${arm}-target.diff"
  set +e
  (cd "$repo" && node "$npm2" test) >"$output/${arm}.log" 2>&1
  status=$?
  set -e
  summary=$(sed -n 's/.*\([0-9][0-9]* specs, [0-9][0-9]* failures\).*/\1/p' "$output/${arm}.log" | tail -1)
  specs=$(printf '%s' "$summary" | sed -n 's/\([0-9][0-9]*\) specs.*/\1/p')
  failures=$(printf '%s' "$summary" | sed -n 's/.*specs, \([0-9][0-9]*\) failures.*/\1/p')
  if [[ "$failures" -eq 0 ]]; then
    contract_result=pass
  else
    contract_result=fail
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$arm" "$version" "$status" "$specs" "$failures" "$contract_result" \
    >>"$output/run-results.tsv"
  jq \
    --arg name "$arm" \
    --arg source_version "$version" \
    --argjson exit_code "$status" \
    --argjson specs "$specs" \
    --argjson failures "$failures" \
    --arg contract_result "$contract_result" \
    '. + [{
      name: $name,
      source_version: $source_version,
      exit_code: $exit_code,
      specs: $specs,
      failures: $failures,
      contract_result: $contract_result
    }]' "$output/observations.json" >"$output/observations.next.json"
  mv "$output/observations.next.json" "$output/observations.json"
done

jq -n \
  --arg dependency_setup "$dependency_setup" \
  --arg target_repository "Brightspace/images-to-variables (restored from omsmith fork)" \
  --arg target_commit "$base_commit" \
  --arg target_repair_commit "$repair_commit" \
  --slurpfile observations "$output/observations.json" '
    {
      date: "2026-08-24",
      dependency_setup: $dependency_setup,
      target_repository: $target_repository,
      target_commit: $target_commit,
      target_repair_commit: $target_repair_commit,
      decision: "retain_as_one_causal_three_arm_anchor",
      runner_note: "The historical gulp-jasmine task exits zero even when Jasmine reports failures; contract_result is derived from the reported failure count.",
      bounded_negative_status: "unavailable_in_source_frame",
      compatible_control_status: "single_target_only",
      observations: $observations[0],
      expected_direction: {
        a0: "pass",
        a1: "fail",
        a2: "pass",
        "a3-before": "pass",
        "a3-after": "pass"
      }
    }
  ' >"$output/summary.json"
