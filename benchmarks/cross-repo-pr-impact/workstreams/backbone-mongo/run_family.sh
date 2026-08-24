#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/../../../.." && pwd)
work_root=${MARSHAL_TASK_TMP:-/home/zhihao/hdd/backbone-mongo-work}
output_dir=${1:-$repo_root/benchmarks/cross-repo-pr-impact/results/backbone-mongo-family-2026-08-24}
node_bin=${NODE_BIN:-/home/zhihao/.nvm/versions/node/v6.17.1/bin/node}
npm_bin=${NPM_BIN:-npm}

target_repo=$work_root/target
orm_repo=$work_root/backbone-orm
backbone_repo=$work_root/backbone
mongodb_repo=$work_root/mongodb
cache_dir=$work_root/npm-cache
runs_parent=$work_root/runs

mkdir -p "$work_root" "$cache_dir" "$runs_parent" "$output_dir/historical"
run_root=$(mktemp -d "$runs_parent/run.XXXXXX")

cleanup() {
  rm -rf -- "$run_root"
}
trap cleanup EXIT

ensure_repo() {
  local directory=$1
  local url=$2
  if [[ ! -d $directory/.git ]]; then
    git clone "$url" "$directory"
  fi
}

ensure_repo "$target_repo" https://github.com/vidigami/backbone-mongo.git
ensure_repo "$orm_repo" https://github.com/vidigami/backbone-orm.git
ensure_repo "$backbone_repo" https://github.com/jashkenas/backbone.git
ensure_repo "$mongodb_repo" https://github.com/mongodb/node-mongodb-native.git

archive_ref() {
  local repository=$1
  local ref=$2
  local destination=$3
  mkdir -p "$destination"
  git -C "$repository" archive "$ref" | tar -x -C "$destination"
}

write_package_stub() {
  local directory=$1
  printf '%s\n' '{"name":"backbone-mongo-causal-replay","private":true}' \
    >"$directory/package.json"
}

install_backbone_dependencies() {
  local arm_dir=$1
  local backbone_version=$2
  write_package_stub "$arm_dir"
  "$npm_bin" install \
    --prefix "$arm_dir" \
    --cache "$cache_dir" \
    --ignore-scripts \
    --no-audit \
    --no-fund \
    --legacy-peer-deps \
    --save-exact \
    "backbone@$backbone_version" \
    backbone-orm@0.5.7 \
    underscore@1.5.2 \
    moment@2.5.1 \
    inflection@1.2.7 \
    lru-cache@2.5.0 \
    mongodb@1.3.23 \
    >"$arm_dir/install.log" 2>&1

  rm -rf -- "$arm_dir/node_modules/backbone-orm"
  archive_ref "$orm_repo" 0.5.7 "$arm_dir/node_modules/backbone-orm"
}

prepare_backbone_arm() {
  local arm=$1
  local backbone_version=$2
  local target_repair=$3
  local orm_repair=$4
  local metadata_only=$5
  local arm_dir=$run_root/backbone/$arm

  mkdir -p "$arm_dir/target"
  archive_ref "$target_repo" 0.5.2 "$arm_dir/target"
  install_backbone_dependencies "$arm_dir" "$backbone_version"

  if [[ $target_repair == yes ]]; then
    git -C "$arm_dir/target" apply \
      "$script_dir/backbone-mongo-maintainer-behavior-repair.patch"
  fi
  if [[ $orm_repair == yes ]]; then
    git -C "$arm_dir/node_modules/backbone-orm" apply \
      "$script_dir/backbone-orm-maintainer-behavior-repair.patch"
  fi
  if [[ $metadata_only == yes ]]; then
    jq '.version = "0.5.4" | .dependencies.backbone = ">=1.0.0"' \
      "$arm_dir/target/package.json" >"$arm_dir/target/package.json.next"
    mv "$arm_dir/target/package.json.next" "$arm_dir/target/package.json"
    jq '.version = "0.5.9" | .dependencies.backbone = ">=1.0.0"' \
      "$arm_dir/node_modules/backbone-orm/package.json" \
      >"$arm_dir/node_modules/backbone-orm/package.json.next"
    mv "$arm_dir/node_modules/backbone-orm/package.json.next" \
      "$arm_dir/node_modules/backbone-orm/package.json"
  fi

  cp "$arm_dir/install.log" "$output_dir/backbone-$arm-install.log"
}

run_probe() {
  local name=$1
  local expected=$2
  shift 2
  local started ended status observed
  started=$(date +%s)
  set +e
  "$@" >"$output_dir/$name.json" 2>"$output_dir/$name.log"
  status=$?
  set -e
  ended=$(date +%s)
  if [[ $status -eq 0 ]]; then
    observed=pass
  else
    observed=fail
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$name" "$expected" "$observed" "$status" "$((ended - started))" \
    >>"$output_dir/run-results.tsv"
}

prepare_backbone_arm A0 1.1.0 no no no
prepare_backbone_arm A1 1.1.1 no no no
prepare_backbone_arm A2 1.1.1 yes yes no
prepare_backbone_arm SOURCE_PR_ONLY 1.1.0 no no no
git apply --unsafe-paths \
  --directory="$run_root/backbone/SOURCE_PR_ONLY/node_modules/backbone" \
  "$script_dir/backbone-source-pr-only.patch"
prepare_backbone_arm BACKBONE_MONGO_ONLY 1.1.1 yes no no
prepare_backbone_arm BACKBONE_ORM_ONLY 1.1.1 no yes no
prepare_backbone_arm METADATA_ONLY 1.1.1 no no yes

printf 'run\texpected\tobserved\texit_status\tduration_seconds\n' \
  >"$output_dir/run-results.tsv"
"$node_bin" --version >"$output_dir/node-version.txt"
"$npm_bin" --version >"$output_dir/npm-version.txt"

for arm in A0 A1 A2 SOURCE_PR_ONLY BACKBONE_MONGO_ONLY BACKBONE_ORM_ONLY METADATA_ONLY; do
  if [[ $arm == A0 || $arm == A2 ]]; then
    expected=pass
  else
    expected=fail
  fi
  run_probe "backbone-$arm" "$expected" \
    env NODE_PATH="$run_root/backbone/$arm/node_modules" \
    "$node_bin" "$script_dir/probe_backbone.js" \
    "$run_root/backbone/$arm/target"
done

install_mongodb_dependencies() {
  local arm_dir=$1
  local bson_version=$2
  write_package_stub "$arm_dir"
  "$npm_bin" install \
    --prefix "$arm_dir" \
    --cache "$cache_dir" \
    --ignore-scripts \
    --no-audit \
    --no-fund \
    --legacy-peer-deps \
    --save-exact \
    backbone@1.1.0 \
    backbone-orm@0.5.7 \
    underscore@1.5.2 \
    moment@2.5.1 \
    inflection@1.2.7 \
    lru-cache@2.5.0 \
    "bson@$bson_version" \
    >"$arm_dir/install.log" 2>&1
  rm -rf -- "$arm_dir/node_modules/backbone-orm"
  archive_ref "$orm_repo" 0.5.7 "$arm_dir/node_modules/backbone-orm"
}

prepare_mongodb_arm() {
  local arm=$1
  local source_ref=$2
  local bson_version=$3
  local target_ref=$4
  local arm_dir=$run_root/mongodb/$arm

  mkdir -p "$arm_dir/target" "$arm_dir/node_modules/mongodb"
  archive_ref "$target_repo" "$target_ref" "$arm_dir/target"
  install_mongodb_dependencies "$arm_dir" "$bson_version"
  archive_ref "$mongodb_repo" "$source_ref" "$arm_dir/node_modules/mongodb"
  cp "$arm_dir/install.log" "$output_dir/mongodb-$arm-install.log"
}

prepare_mongodb_arm M0 V1.3.12 0.2.1 0.5.2
prepare_mongodb_arm M1 V1.3.13 0.2.2 0.5.2
prepare_mongodb_arm M2 V1.3.13 0.2.2 0.5.9

run_probe mongodb-source-1.3.12 pass \
  env NODE_PATH="$run_root/mongodb/M0/node_modules" \
  "$node_bin" "$script_dir/probe_mongodb_source.js" \
  "$run_root/mongodb/M0/node_modules/mongodb" callback-throw
run_probe mongodb-source-1.3.13 pass \
  env NODE_PATH="$run_root/mongodb/M1/node_modules" \
  "$node_bin" "$script_dir/probe_mongodb_source.js" \
  "$run_root/mongodb/M1/node_modules/mongodb" db-error-event

for arm in M0 M1 M2; do
  run_probe "mongodb-target-$arm" pass \
    env NODE_PATH="$run_root/mongodb/$arm/node_modules" \
    "$node_bin" "$script_dir/probe_mongodb_target.js" \
    "$run_root/mongodb/$arm/target"
done

git -C "$backbone_repo" diff 1.1.0..1.1.1 -- backbone.js \
  >"$output_dir/historical/backbone-1.1.0-to-1.1.1.patch"
git -C "$target_repo" show --format=fuller --stat \
  247633a3936f5771f791bedfd0d9c220232e4b58 \
  >"$output_dir/historical/backbone-mongo-repair.txt"
git -C "$orm_repo" show --format=fuller --stat \
  48174b2235bf15b1a57373aed3aa2780451533a7 \
  >"$output_dir/historical/backbone-orm-repair.txt"
git -C "$mongodb_repo" show --format=fuller \
  7fca46c532b6390e2e6c8680395d0641a9b26f5b -- \
  lib/mongodb/connection/base.js \
  >"$output_dir/historical/mongodb-error-emission-change.patch"
git -C "$target_repo" diff --stat 0.5.2..0.5.9 \
  >"$output_dir/historical/backbone-mongo-0.5.2-to-0.5.9-stat.txt"

jq -n \
  --slurpfile a0 "$output_dir/backbone-A0.json" \
  --slurpfile a1 "$output_dir/backbone-A1.json" \
  --slurpfile a2 "$output_dir/backbone-A2.json" \
  --slurpfile source_pr_only "$output_dir/backbone-SOURCE_PR_ONLY.json" \
  --slurpfile mongo_only "$output_dir/backbone-BACKBONE_MONGO_ONLY.json" \
  --slurpfile orm_only "$output_dir/backbone-BACKBONE_ORM_ONLY.json" \
  --slurpfile metadata_only "$output_dir/backbone-METADATA_ONLY.json" \
  --slurpfile source12 "$output_dir/mongodb-source-1.3.12.json" \
  --slurpfile source13 "$output_dir/mongodb-source-1.3.13.json" \
  --slurpfile m0 "$output_dir/mongodb-target-M0.json" \
  --slurpfile m1 "$output_dir/mongodb-target-M1.json" \
  --slurpfile m2 "$output_dir/mongodb-target-M2.json" \
  '{
    evaluated_at: "2026-08-24",
    backbone_relation: {
      source_change: "backbone 1.1.0 -> 1.1.1",
      source_pr: "jashkenas/backbone#2878",
      source_commit: "6dcec298314b785a16ccc15bc44db1b91f01c367",
      public_target_boundary: "backbone-mongo 0.5.2 -> 0.5.4",
      corrected_positive_repositories: [
        "vidigami/backbone-mongo",
        "vidigami/backbone-orm"
      ],
      arms: {
        A0: $a0[0],
        A1: $a1[0],
        A2: $a2[0],
        source_pr_only: $source_pr_only[0],
        backbone_mongo_only: $mongo_only[0],
        backbone_orm_only: $orm_only[0],
        metadata_only: $metadata_only[0]
      },
      decision: "accepted_two-target-causal-anchor"
    },
    mongodb_relation: {
      source_change: "mongodb 1.3.12 -> 1.3.13",
      public_target_boundary: "backbone-mongo 0.5.2 -> 0.5.9",
      source_surface: {
        before: $source12[0],
        after: $source13[0]
      },
      target_screening: {
        M0: $m0[0],
        M1: $m1[0],
        M2: $m2[0]
      },
      decision: "rejected-no-a1-failure-no-maintainer-recovery-and-source-predates-target"
    },
    accepted_chain_independent_positive_cases: 1,
    positive_target_repositories: 2,
    rejected_public_labels: 1,
    bounded_negative_labels: 0,
    accepted_a3_cases: 0,
    package_status: "causal-anchor-not-complete-flagship-package"
  }' >"$output_dir/summary.json"

jq -e '
  .backbone_relation.arms.A0.result == "pass" and
  .backbone_relation.arms.A1.result == "fail" and
  (.backbone_relation.arms.A1.error_message | test("attributes.*id|id.*undefined")) and
  .backbone_relation.arms.source_pr_only.result == "fail" and
  (.backbone_relation.arms.source_pr_only.error_message | test("attributes.*id|id.*undefined")) and
  .backbone_relation.arms.A2.result == "pass" and
  .backbone_relation.arms.A2.target_backbone_mongo == "0.5.2" and
  .backbone_relation.arms.A2.target_backbone_orm == "0.5.7" and
  .backbone_relation.arms.backbone_mongo_only.result == "fail" and
  .backbone_relation.arms.backbone_orm_only.result == "fail" and
  .backbone_relation.arms.metadata_only.result == "fail"
' "$output_dir/summary.json" >/dev/null

jq -e '
  .mongodb_relation.source_surface.before.observed_behavior == "callback-throw" and
  .mongodb_relation.source_surface.after.observed_behavior == "db-error-event" and
  .mongodb_relation.target_screening.M0.result == "pass" and
  .mongodb_relation.target_screening.M1.result == "pass" and
  .mongodb_relation.target_screening.M2.result == "pass" and
  .mongodb_relation.target_screening.M0.db_error_listener_count == 0 and
  .mongodb_relation.target_screening.M1.db_error_listener_count == 0 and
  .mongodb_relation.target_screening.M2.db_error_listener_count == 0
' "$output_dir/summary.json" >/dev/null

echo "关系族审计完成：Backbone 线接受一条两目标因果锚点；MongoDB 线拒绝。"
