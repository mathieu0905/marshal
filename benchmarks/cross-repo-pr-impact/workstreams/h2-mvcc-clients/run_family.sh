#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/../../../.." && pwd)
work_root=${MARSHAL_TASK_TMP:-/home/zhihao/hdd/h2-mvcc-clients-replay}
output_dir=${1:-$repo_root/benchmarks/cross-repo-pr-impact/results/h2-mvcc-clients-family-2026-08-24}
java_home=${JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}

h2_repo=$work_root/h2
rider_repo=$work_root/database-rider
score_repo=$work_root/cloudslang-score
runs_parent=$work_root/runs
mkdir -p "$work_root" "$runs_parent" "$output_dir/historical"
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

ensure_repo "$h2_repo" https://github.com/h2database/h2database.git
ensure_repo "$rider_repo" https://github.com/database-rider/database-rider.git
ensure_repo "$score_repo" https://github.com/CloudSlang/score.git

archive_ref() {
  local repository=$1
  local ref=$2
  local destination=$3
  mkdir -p "$destination"
  git -C "$repository" archive "$ref" | tar -x -C "$destination"
}

record_run() {
  local name=$1
  local expected=$2
  local directory=$3
  shift 3
  local started ended status observed
  started=$(date +%s)
  set +e
  (cd "$directory" && "$@") >"$output_dir/$name.log" 2>&1
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

printf 'run\texpected\tobserved\texit_status\tduration_seconds\n' \
  >"$output_dir/run-results.tsv"
"$java_home/bin/java" -version >"$output_dir/java-version.txt" 2>&1
mvn -version >"$output_dir/maven-version.txt" 2>&1

mvn -q dependency:get -Dartifact=com.h2database:h2:1.4.199
mvn -q dependency:get -Dartifact=com.h2database:h2:1.4.200
mvn -q dependency:get -Dartifact=javax.annotation:javax.annotation-api:1.3.2
h2_199=$HOME/.m2/repository/com/h2database/h2/1.4.199/h2-1.4.199.jar
h2_200=$HOME/.m2/repository/com/h2database/h2/1.4.200/h2-1.4.200.jar
annotation_api=$HOME/.m2/repository/javax/annotation/javax.annotation-api/1.3.2/javax.annotation-api-1.3.2.jar

archive_ref "$h2_repo" version-1.4.199 "$run_root/h2-source-pr-only"
git apply --unsafe-paths --directory="$run_root/h2-source-pr-only" \
  "$script_dir/h2-source-mvcc-rejection.patch"
record_run h2-source-pr-only-build pass "$run_root/h2-source-pr-only" \
  env JAVA_HOME="$java_home" mvn -DskipTests package
h2_pr_only=$(find "$run_root/h2-source-pr-only/target" -maxdepth 1 \
  -name 'h2-*-SNAPSHOT.jar' -print -quit)

old_url='jdbc:h2:mem:probe;MVCC=TRUE'
fixed_url='jdbc:h2:mem:probe;LOCK_TIMEOUT=5000'
"$java_home/bin/java" --class-path "$h2_199" "$script_dir/H2UrlProbe.java" \
  "$old_url" pass >"$output_dir/probe-1.4.199-old-url.json"
"$java_home/bin/java" --class-path "$h2_200" "$script_dir/H2UrlProbe.java" \
  "$old_url" fail >"$output_dir/probe-1.4.200-old-url.json"
"$java_home/bin/java" --class-path "$h2_200" "$script_dir/H2UrlProbe.java" \
  "$fixed_url" pass >"$output_dir/probe-1.4.200-fixed-url.json"
"$java_home/bin/java" --class-path "$h2_pr_only" "$script_dir/H2UrlProbe.java" \
  "$old_url" fail >"$output_dir/probe-source-pr-only-old-url.json"

for arm in A0 A1 A2; do
  arm_dir=$run_root/rider/$arm
  archive_ref "$rider_repo" c78ffe0add11caf4f2af07d30b56432f242c2646 "$arm_dir"
  if [[ $arm != A0 ]]; then
    perl -0pi -e \
      's/<version>1\.4\.199<\/version>/<version>1.4.200<\/version>/' \
      "$arm_dir/rider-examples/rider-micronaut/pom.xml"
  fi
  if [[ $arm == A2 ]]; then
    git apply --unsafe-paths --directory="$arm_dir" \
      "$script_dir/database-rider-maintainer-repair.patch"
  fi
  expected=pass
  [[ $arm == A1 ]] && expected=fail
  record_run "database-rider-$arm" "$expected" "$arm_dir" \
    env JAVA_HOME="$java_home" mvn \
      -pl rider-examples/rider-micronaut -am \
      -Dtest=OwnerControllerTest \
      -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false test
done

for arm in A0 A1 A2; do
  arm_dir=$run_root/score/$arm
  archive_ref "$score_repo" f72e1adaf5dca565a91c6ab89d9df7ba6fdf8f89 "$arm_dir"
  git apply --unsafe-paths --directory="$arm_dir" \
    "$script_dir/cloudslang-java11-environment.patch"
  if [[ $arm != A0 ]]; then
    perl -0pi -e \
      's/<h2\.version>1\.4\.199<\/h2\.version>/<h2.version>1.4.200<\/h2.version>/' \
      "$arm_dir/pom.xml"
  fi
  if [[ $arm == A2 ]]; then
    git apply --unsafe-paths --directory="$arm_dir" \
      "$script_dir/cloudslang-score-maintainer-repair.patch"
  fi
  expected=pass
  [[ $arm == A1 ]] && expected=fail
  record_run "cloudslang-score-orchestrator-$arm" "$expected" "$arm_dir" \
    env JAVA_HOME="$java_home" \
      MAVEN_OPTS="-Xbootclasspath/a:$annotation_api" mvn \
      -pl engine/orchestrator/score-orchestrator-impl -am \
      -Dtest=SuspendedExecutionsRepositoryTest#simpleCreateAndReadTest \
      -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false test
  record_run "cloudslang-score-node-$arm" "$expected" "$arm_dir" \
    env JAVA_HOME="$java_home" \
      MAVEN_OPTS="-Xbootclasspath/a:$annotation_api" mvn \
      -pl engine/node/score-node-impl -am \
      -Dtest=WorkerLockRepositoryTest#deleteByUuidTest \
      -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false test
done

git -C "$h2_repo" show --format=fuller \
  92692e63df10c3f73dd799f122949c705769e7b1 \
  >"$output_dir/historical/h2-source-pr-only.patch"
git -C "$rider_repo" show --format=fuller \
  2e38b6e513521f5956a116bff80feb322045c9a3 \
  >"$output_dir/historical/database-rider-maintainer-response.patch"
git -C "$score_repo" show --format=fuller \
  ab4fa3d87e26393a0f80f6ae2ce11a64817262d3 \
  >"$output_dir/historical/cloudslang-score-maintainer-response.patch"

jq -n \
  --slurpfile p199 "$output_dir/probe-1.4.199-old-url.json" \
  --slurpfile p200 "$output_dir/probe-1.4.200-old-url.json" \
  --slurpfile fixed "$output_dir/probe-1.4.200-fixed-url.json" \
  --slurpfile source_pr "$output_dir/probe-source-pr-only-old-url.json" \
  '{
    evaluated_at: "2026-08-24",
    source: {
      repository: "h2database/h2database",
      pr: 2143,
      commit: "92692e63df10c3f73dd799f122949c705769e7b1",
      change: "reject the MVCC connection setting"
    },
    public_records: 5,
    independent_target_repositories: [
      "database-rider/database-rider",
      "CloudSlang/score"
    ],
    alias_note: "openscore/score redirects to CloudSlang/score and has the same GitHub node_id",
    direct_probes: {
      h2_1_4_199_old_url: $p199[0],
      h2_1_4_200_old_url: $p200[0],
      h2_1_4_200_fixed_url: $fixed[0],
      source_pr_only_old_url: $source_pr[0]
    },
    chain_independent_positive_relations: 2,
    positive_target_repositories: 2,
    qualified_negatives: 0,
    A3: 0,
    decision: "accepted-two-repository-causal-family"
  }' >"$output_dir/summary.json"
