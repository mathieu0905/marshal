#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "用法：$0 <db-a0 克隆> <db-a1 克隆> <examples-a0 克隆> <examples-a1 克隆> <结果目录>" >&2
  exit 2
fi

db_a0=$1
db_a1=$2
examples_a0=$3
examples_a1=$4
output=$5
mkdir -p "$output"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"

run_db() {
  local repo_dir=$1
  local arm=$2
  local version=$3
  git -C "$repo_dir" checkout --detach --force 8aefa0f0417aa5cf01a9990ff554a119a6ddf557 >"$output/assertj-db-${arm}-checkout.log" 2>&1
  (
    cd "$repo_dir"
    mvn -B versions:use-dep-version \
      -Dincludes=org.assertj:assertj-core \
      -DdepVersion="$version" \
      -DforceVersion=true \
      -DgenerateBackupPoms=false
  ) >"$output/assertj-db-${arm}-version-edit.log" 2>&1
  set +e
  (
    cd "$repo_dir"
    mvn -B clean test -Dtest=org.assertj.db.api.SoftAssertions_Test
  ) >"$output/assertj-db-${arm}.log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$output/assertj-db-${arm}.exit"
  (
    cd "$repo_dir"
    mvn -B dependency:tree -Dincludes=org.assertj:assertj-core,net.bytebuddy:byte-buddy
  ) >"$output/assertj-db-${arm}-dependency-tree.log" 2>&1 || true
}

run_examples() {
  local repo_dir=$1
  local arm=$2
  local version=$3
  git -C "$repo_dir" checkout --detach --force 0868b5d724374ca0eb3f6c2456b27acd5ac740e0 >"$output/assertj-examples-${arm}-checkout.log" 2>&1
  set +e
  (
    cd "$repo_dir"
    mvn -B -f assertions-examples/pom.xml clean test \
      -Dassertj-core.version="$version" \
      -Dtest=org.assertj.examples.SoftAssertionsExamples#host_dinner_party_where_nobody_dies
  ) >"$output/assertj-examples-${arm}.log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$output/assertj-examples-${arm}.exit"
  (
    cd "$repo_dir"
    mvn -B -f assertions-examples/pom.xml dependency:tree \
      -Dassertj-core.version="$version" \
      -Dincludes=org.assertj:assertj-core,net.bytebuddy:byte-buddy
  ) >"$output/assertj-examples-${arm}-dependency-tree.log" 2>&1 || true
}

run_db "$db_a0" a0 3.22.0 &
pid_db_a0=$!
run_db "$db_a1" a1 3.23.0 &
pid_db_a1=$!
run_examples "$examples_a0" a0 3.22.0 &
pid_examples_a0=$!
run_examples "$examples_a1" a1 3.23.0 &
pid_examples_a1=$!

wait "$pid_db_a0"
wait "$pid_db_a1"
wait "$pid_examples_a0"
wait "$pid_examples_a1"

printf 'repository\tarm\tversion\texit_code\n' >"$output/run-results.tsv"
printf 'assertj-db\ta0\t3.22.0\t%s\n' "$(<"$output/assertj-db-a0.exit")" >>"$output/run-results.tsv"
printf 'assertj-db\ta1\t3.23.0\t%s\n' "$(<"$output/assertj-db-a1.exit")" >>"$output/run-results.tsv"
printf 'assertj-examples\ta0\t3.22.0\t%s\n' "$(<"$output/assertj-examples-a0.exit")" >>"$output/run-results.tsv"
printf 'assertj-examples\ta1\t3.23.0\t%s\n' "$(<"$output/assertj-examples-a1.exit")" >>"$output/run-results.tsv"
