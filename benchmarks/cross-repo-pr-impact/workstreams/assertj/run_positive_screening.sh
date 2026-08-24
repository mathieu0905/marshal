#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "用法：$0 <assertj-guava 克隆目录> <assertj-vavr 克隆目录> <结果目录>" >&2
  exit 2
fi

guava_repo=$1
vavr_repo=$2
output=$3

mkdir -p "$output"
printf 'repository\tarm\tcommit\texit_code\n' >"$output/run-results.tsv"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
{
  java -version
  mvn -version
} >"$output/environment.txt" 2>&1

run_arm() {
  local repository=$1
  local repo_dir=$2
  local arm=$3
  local commit=$4
  local lifecycle=$5
  local log="$output/${repository}-${arm}.log"

  git -C "$repo_dir" checkout --detach --force "$commit" >"$output/${repository}-${arm}-checkout.log" 2>&1
  set +e
  (
    cd "$repo_dir"
    mvn -B clean "$lifecycle"
  ) >"$log" 2>&1
  local status=$?
  set -e
  (
    cd "$repo_dir"
    mvn -B dependency:tree -Dincludes=org.assertj:assertj-core,net.bytebuddy:byte-buddy
  ) >"$output/${repository}-${arm}-dependency-tree.log" 2>&1 || true
  printf '%s\t%s\t%s\t%s\n' "$repository" "$arm" "$commit" "$status" >>"$output/run-results.tsv"
}

run_arm assertj-guava "$guava_repo" a0 5705970602ede90f3dc8c001d0d749461c20d56f verify
run_arm assertj-guava "$guava_repo" a1 0968864d08e0fce1e5e1caaf89afddd2cc1b2569 verify
run_arm assertj-guava "$guava_repo" a2 4c6055d37cb727865c800a829521f6efe1286ce1 verify

run_arm assertj-vavr "$vavr_repo" a0 edced3fc51e16f17586c5ebc181705b0d5fc1934 test
run_arm assertj-vavr "$vavr_repo" a1 1cc7071371953a7880c2c2c3a5a32c36af7f88f9 test
run_arm assertj-vavr "$vavr_repo" a2 d330a1528031a8e68795d3f9158a5527e0e9d535 test
