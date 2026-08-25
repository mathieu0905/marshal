#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: $0 <assertj-core clone> <brave clone> <harness template> <work directory> <result directory>" >&2
  exit 2
fi

assertj_repo=$(realpath "$1")
brave_repo=$(realpath "$2")
template=$(realpath "$3")
work=$(realpath -m "$4")
output=$(realpath -m "$5")
base=5e15c20e7d79a0d032f5606c1b3684277bd11d7d
repair=eac0ffa658c7c708ce26e306f171a4fc04bef9ca
release=5.16.0
source_change=66e784987234e9c649e043f631ef984036ee9b30
test_path=brave-tests/src/test/java/brave/test/IntegrationTestSpanHandlerTest.java
main_path=brave-tests/src/main/java/brave/test/IntegrationTestSpanHandler.java
selector=brave.test.IntegrationTestSpanHandlerTest#goodMessageForOrphanedSpan

mkdir -p "$work/src/test/java/brave/test" "$output"
cp "$template/pom.xml" "$work/pom.xml"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
local_repo="$work/m2"

{
  java -version
  mvn -version
} >"$output/environment.txt" 2>&1

git -C "$brave_repo" checkout --detach --force "$base" >"$output/brave-checkout.log" 2>&1
git -C "$brave_repo" rev-parse HEAD >"$output/client-base-commit.txt"
git -C "$brave_repo" show -s --format=fuller "$repair" >"$output/maintainer-repair-commit.txt"
git -C "$brave_repo" diff "$release" "$base" -- "$main_path" "$test_path" >"$output/release-to-base-relevant.diff"
git -C "$brave_repo" diff "$base" "$repair" -- "$test_path" >"$output/maintainer-repair.diff"
git -C "$assertj_repo" show -s --format=fuller "$source_change" >"$output/assertj-source-change-commit.txt"
git -C "$assertj_repo" show --format=fuller "$source_change" -- \
  src/main/java/org/assertj/core/api/AbstractAssert.java \
  src/main/java/org/assertj/core/error/AssertionErrorCreator.java \
  src/main/java/org/assertj/core/internal/Failures.java \
  >"$output/assertj-source-change.diff"

run_arm() {
  local arm=$1
  local version=$2
  local revision=$3
  local temp_dir="$work/tmp/$arm"
  mkdir -p "$temp_dir"
  git -C "$brave_repo" show "$revision:$test_path" >"$work/src/test/java/brave/test/IntegrationTestSpanHandlerTest.java"
  set +e
  (
    cd "$work"
    mvn -B -Dmaven.repo.local="$local_repo" \
      -Djava.io.tmpdir="$temp_dir" \
      -Dassertj.version="$version" \
      -Dtest="$selector" clean test
  ) >"$output/$arm.log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$output/$arm.exit"
  cp "$work/target/surefire-reports/TEST-brave.test.IntegrationTestSpanHandlerTest.xml" \
    "$output/$arm-surefire.xml"
  (
    cd "$work"
    mvn -B -Dmaven.repo.local="$local_repo" \
      -Djava.io.tmpdir="$temp_dir" \
      -Dassertj.version="$version" \
      dependency:tree -Dincludes=io.zipkin.brave:brave-tests,org.assertj:assertj-core
  ) >"$output/$arm-dependency-tree.log" 2>&1
}

run_arm A0 3.18.1 "$base"
run_arm A1 3.19.0 "$base"
run_arm A2 3.19.0 "$repair"

printf 'arm\tassertj_version\tclient_revision\texit_code\n' >"$output/run-results.tsv"
printf 'A0\t3.18.1\t%s\t%s\n' "$base" "$(<"$output/A0.exit")" >>"$output/run-results.tsv"
printf 'A1\t3.19.0\t%s\t%s\n' "$base" "$(<"$output/A1.exit")" >>"$output/run-results.tsv"
printf 'A2\t3.19.0\t%s\t%s\n' "$repair" "$(<"$output/A2.exit")" >>"$output/run-results.tsv"
