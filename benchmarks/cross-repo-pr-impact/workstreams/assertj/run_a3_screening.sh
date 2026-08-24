#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "用法：$0 <guava 克隆> <vavr 克隆> <db 克隆> <examples 克隆> <结果目录>" >&2
  exit 2
fi

guava_repo=$1
vavr_repo=$2
db_repo=$3
examples_repo=$4
output=$(realpath -m "$5")
mkdir -p "$output"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
agent=$HOME/.m2/repository/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar
cli=$HOME/.m2/repository/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar
old_version=${ASSERTJ_A3_OLD_VERSION:-3.24.1}
new_version=${ASSERTJ_A3_NEW_VERSION:-3.24.2}
guava_commit=${ASSERTJ_A3_GUAVA_COMMIT:-4c6055d37cb727865c800a829521f6efe1286ce1}
vavr_commit=${ASSERTJ_A3_VAVR_COMMIT:-d330a1528031a8e68795d3f9158a5527e0e9d535}
core_jar=$HOME/.m2/repository/org/assertj/assertj-core/$new_version/assertj-core-$new_version.jar
coverage_source=${ASSERTJ_A3_COVERAGE_SOURCE:-org/assertj/core/internal/Iterables.java}
coverage_line=${ASSERTJ_A3_COVERAGE_LINE:-354}

append_line_coverage() {
  local repository=$1
  local xml=$2
  local source=$3
  local line=$4
  local package=${source%/*}
  local file=${source##*/}
  local node

  node=$(xmllint --xpath \
    "//package[@name='$package']/sourcefile[@name='$file']/line[@nr='$line']" \
    "$xml")
  printf '%s\t%s\t%s\t%s\n' "$repository" "$source" "$line" "$node" \
    >>"$output/changed-line-coverage.tsv"
}

set_assertj_version() {
  local repo_dir=$1
  local version=$2
  (
    cd "$repo_dir"
    mvn -B versions:use-dep-version \
      -Dincludes=org.assertj:assertj-core \
      -DdepVersion="$version" \
      -DforceVersion=true \
      -DgenerateBackupPoms=false
  )
}

run_standard_repo() {
  local name=$1
  local repo_dir=$2
  local commit=$3
  local test_selector=${4:-}
  local version

  for version in "$old_version" "$new_version"; do
    git -C "$repo_dir" checkout --detach --force "$commit" >"$output/${name}-${version}-checkout.log" 2>&1
    set_assertj_version "$repo_dir" "$version" >"$output/${name}-${version}-version-edit.log" 2>&1
    local exec_file="$output/${name}-${version}.exec"
    local test_args=()
    if [[ -n "$test_selector" ]]; then
      test_args+=("-Dtest=$test_selector")
    fi
    set +e
    (
      cd "$repo_dir"
      JAVA_TOOL_OPTIONS="-javaagent:$agent=destfile=$exec_file,append=true" \
      mvn -B clean test -Djacoco.skip=true "${test_args[@]}"
    ) >"$output/${name}-${version}.log" 2>&1
    local status=$?
    set -e
    printf '%s\n' "$status" >"$output/${name}-${version}.exit"
  done

  java -jar "$cli" report "$output/${name}-${new_version}.exec" \
    --classfiles "$core_jar" \
    --xml "$output/${name}-assertj-core-${new_version}.xml" >"$output/${name}-report.log" 2>&1
}

run_examples() {
  local version
  for version in "$old_version" "$new_version"; do
    git -C "$examples_repo" checkout --detach --force 0868b5d724374ca0eb3f6c2456b27acd5ac740e0 >"$output/assertj-examples-${version}-checkout.log" 2>&1
    local exec_file="$output/assertj-examples-${version}.exec"
    set +e
    (
      cd "$examples_repo"
      JAVA_TOOL_OPTIONS="-javaagent:$agent=destfile=$exec_file,append=true" \
      mvn -B -f assertions-examples/pom.xml clean test \
        -Dassertj-core.version="$version" \
        -Dtest=org.assertj.examples.SoftAssertionsExamples#host_dinner_party_where_nobody_dies
    ) >"$output/assertj-examples-${version}.log" 2>&1
    local status=$?
    set -e
    printf '%s\n' "$status" >"$output/assertj-examples-${version}.exit"
  done

  java -jar "$cli" report "$output/assertj-examples-${new_version}.exec" \
    --classfiles "$core_jar" \
    --xml "$output/assertj-examples-assertj-core-${new_version}.xml" >"$output/assertj-examples-report.log" 2>&1
}

run_standard_repo assertj-guava "$guava_repo" "$guava_commit" &
pid_guava=$!
run_standard_repo assertj-vavr "$vavr_repo" "$vavr_commit" &
pid_vavr=$!
run_standard_repo assertj-db "$db_repo" 8aefa0f0417aa5cf01a9990ff554a119a6ddf557 org.assertj.db.api.SoftAssertions_Test &
pid_db=$!
run_examples &
pid_examples=$!

wait "$pid_guava"
wait "$pid_vavr"
wait "$pid_db"
wait "$pid_examples"

printf 'repository\tsource_file\tline\tjacoco_line_node\n' >"$output/changed-line-coverage.tsv"
for repository in assertj-guava assertj-vavr assertj-db assertj-examples; do
  xml="$output/${repository}-assertj-core-${new_version}.xml"
  append_line_coverage "$repository" "$xml" "$coverage_source" "$coverage_line"
  rm "$xml"
done

printf 'repository\tversion\texit_code\n' >"$output/run-results.tsv"
for repository in assertj-guava assertj-vavr assertj-db assertj-examples; do
  for version in "$old_version" "$new_version"; do
    printf '%s\t%s\t%s\n' "$repository" "$version" "$(<"$output/${repository}-${version}.exit")" >>"$output/run-results.tsv"
  done
done
