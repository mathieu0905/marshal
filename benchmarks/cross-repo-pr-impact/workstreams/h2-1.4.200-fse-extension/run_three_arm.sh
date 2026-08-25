#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/../../../.." && pwd)
work_root=$repo_root/.work/h2-1.4.200-fse-replay
output_dir=${1:-$repo_root/benchmarks/cross-repo-pr-impact/results/h2-1.4.200-fse-extension-2026-08-25}
java_home=${JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export TMPDIR=$work_root/tmp
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$TMPDIR -Djansi.tmpdir=$TMPDIR"

mkdir -p "$work_root" "$work_root/repositories" "$work_root/runs" "$work_root/m2" "$output_dir" "$TMPDIR"
run_root=$(mktemp -d "$work_root/runs/run.XXXXXX")
run_mismatches=0

cleanup() {
  rm -rf -- "$run_root"
}
trap cleanup EXIT

ensure_mirror() {
  local destination=$1
  local url=$2
  if [[ ! -d $destination ]]; then
    git clone --mirror "$url" "$destination"
  fi
}

archive_ref() {
  local repository=$1
  local ref=$2
  local destination=$3
  mkdir -p "$destination"
  git --git-dir="$repository" archive "$ref" | tar -x -C "$destination"
}

record_run() {
  local name=$1
  local expected=$2
  local directory=$3
  local required_pattern=$4
  shift 4
  local status observed
  set +e
  (cd "$directory" && "$@") >"$output_dir/$name.log" 2>&1
  status=$?
  set -e
  if [[ $status -eq 0 ]]; then
    observed=pass
  else
    observed=fail
  fi
  printf '%s\t%s\t%s\t%s\n' "$name" "$expected" "$observed" "$status" >>"$output_dir/run-results.tsv"
  if [[ $observed != "$expected" ]] ||
    { [[ -n $required_pattern ]] && ! grep -Fq -- "$required_pattern" "$output_dir/$name.log"; }; then
    printf 'unexpected result for %s: expected=%s observed=%s required_pattern=%q\n' \
      "$name" "$expected" "$observed" "$required_pattern" >&2
    run_mismatches=$((run_mismatches + 1))
  fi
}

h2_repo=$work_root/repositories/h2database.git
target_repo=$work_root/repositories/spring-batch-toolkit.git
ensure_mirror "$h2_repo" https://github.com/h2database/h2database.git
ensure_mirror "$target_repo" https://github.com/arey/spring-batch-toolkit.git

printf 'run\texpected\tobserved\texit_status\n' >"$output_dir/run-results.tsv"
"$java_home/bin/java" -version >"$output_dir/java-version.txt" 2>&1
env JAVA_HOME="$java_home" mvn -version >"$output_dir/maven-version.txt" 2>&1

env JAVA_HOME="$java_home" mvn -q -Dmaven.repo.local="$work_root/m2" dependency:get \
  -Dartifact=com.h2database:h2:1.4.199
env JAVA_HOME="$java_home" mvn -q -Dmaven.repo.local="$work_root/m2" dependency:get \
  -Dartifact=com.h2database:h2:1.4.200
h2_199=$work_root/m2/com/h2database/h2/1.4.199/h2-1.4.199.jar
h2_200=$work_root/m2/com/h2database/h2/1.4.200/h2-1.4.200.jar

h2_source=$run_root/h2-source
archive_ref "$h2_repo" version-1.4.199 "$h2_source"
git apply --directory="$h2_source" "$script_dir/h2-source-trailing-comma-strictness.patch"
record_run source-change-build pass "$h2_source/h2" '' \
  env JAVA_HOME="$java_home" mvn -B -Dmaven.repo.local="$work_root/m2" -DskipTests package
h2_source_jar=$(find "$h2_source/h2/target" -maxdepth 1 -name 'h2-*-SNAPSHOT.jar' -print -quit)

"$java_home/bin/java" --class-path "$h2_199" "$script_dir/TrailingCommaProbe.java" trailing pass \
  >"$output_dir/probe-1.4.199-trailing.json"
"$java_home/bin/java" --class-path "$h2_200" "$script_dir/TrailingCommaProbe.java" trailing fail \
  >"$output_dir/probe-1.4.200-trailing.json"
"$java_home/bin/java" --class-path "$h2_200" "$script_dir/TrailingCommaProbe.java" fixed pass \
  >"$output_dir/probe-1.4.200-fixed.json"
"$java_home/bin/java" --class-path "$h2_source_jar" "$script_dir/TrailingCommaProbe.java" trailing fail \
  >"$output_dir/probe-1.4.199-source-change-trailing.json"

baseline=1605c3fc6a70a99386f6c0bb8487a81da54e28ae
maintainer_a2=4c467ad8d7dccb1d769c17847cc585530969603d
for arm in a0 a1 a2; do
  if [[ $arm == a2 ]]; then
    archive_ref "$target_repo" "$maintainer_a2" "$run_root/$arm"
  else
    archive_ref "$target_repo" "$baseline" "$run_root/$arm"
  fi
  git apply --directory="$run_root/$arm" "$script_dir/java11-environment.patch"
done
git --git-dir="$target_repo" diff "$baseline" "$maintainer_a2" -- pom.xml \
  | git apply --directory="$run_root/a1"

test_name='TestParallelAndPartitioning#launchJob'
record_run target-a0 pass "$run_root/a0" '' \
  env JAVA_HOME="$java_home" mvn -B -Dmaven.repo.local="$work_root/m2" -Dtest="$test_name" test
record_run target-a1 fail "$run_root/a1" '[42001-200]' \
  env JAVA_HOME="$java_home" mvn -B -Dmaven.repo.local="$work_root/m2" -Dtest="$test_name" test
record_run target-a2 pass "$run_root/a2" '' \
  env JAVA_HOME="$java_home" mvn -B -Dmaven.repo.local="$work_root/m2" -Dtest="$test_name" test

surefire_name=com.javaetmoi.core.batch.test.TestParallelAndPartitioning.txt
for arm in a0 a1 a2; do
  report=$run_root/$arm/target/surefire-reports/$surefire_name
  if [[ ! -f $report ]]; then
    printf 'missing Surefire report for target-%s: %s\n' "$arm" "$report" >&2
    run_mismatches=$((run_mismatches + 1))
    continue
  fi
  cp "$report" "$output_dir/target-$arm-surefire.txt"
done

git --git-dir="$target_repo" diff "$baseline" "$maintainer_a2" >"$output_dir/maintainer-a2.patch"

if [[ $run_mismatches -ne 0 ]]; then
  printf '%s replay result mismatch(es) detected\n' "$run_mismatches" >&2
  exit 1
fi
