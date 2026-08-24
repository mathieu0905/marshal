#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "用法：$0 <Gauge Java 克隆> <WSS4J 克隆> <结果目录>" >&2
  exit 2
fi

gauge_repo=$1
wss_repo=$2
output=$(realpath -m "$3")
mkdir -p "$output"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"

run_arm() {
  local repository=$1
  local repo_dir=$2
  local arm=$3
  local commit=$4
  shift 4

  git -C "$repo_dir" checkout --detach --force "$commit" >"$output/${repository}-${arm}-checkout.log" 2>&1
  set +e
  (cd "$repo_dir" && "$@") >"$output/${repository}-${arm}.log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$output/${repository}-${arm}.exit"
}

run_arm gauge-java "$gauge_repo" a0 3363a7f279d92a7c9c9de0d4828077058192c925 \
  mvn -B clean test
run_arm gauge-java "$gauge_repo" a1 d8031ba94b60982bec9dc8bfedaeee700731be7a \
  mvn -B clean test
run_arm gauge-java "$gauge_repo" a2 db1a09cc0db2b8045a5c2da34617136cd4290fc7 \
  mvn -B clean test

run_arm ws-wss4j "$wss_repo" a0 a8eb885cfe82d2e69f582bec3ada6af34c1388a1 \
  mvn -B -pl ws-security-stax clean checkstyle:check
run_arm ws-wss4j "$wss_repo" a1 a61b52b3627b4a635ae6712081e55cd83e55397d \
  mvn -B -pl ws-security-stax clean checkstyle:check
run_arm ws-wss4j "$wss_repo" a2 d1347cb288174bb6442913fce2919945b05da136 \
  mvn -B -pl ws-security-stax clean checkstyle:check

printf 'repository\tarm\tcommit\texit_code\n' >"$output/run-results.tsv"
for repository in gauge-java ws-wss4j; do
  for arm in a0 a1 a2; do
    case "$repository-$arm" in
      gauge-java-a0) commit=3363a7f279d92a7c9c9de0d4828077058192c925 ;;
      gauge-java-a1) commit=d8031ba94b60982bec9dc8bfedaeee700731be7a ;;
      gauge-java-a2) commit=db1a09cc0db2b8045a5c2da34617136cd4290fc7 ;;
      ws-wss4j-a0) commit=a8eb885cfe82d2e69f582bec3ada6af34c1388a1 ;;
      ws-wss4j-a1) commit=a61b52b3627b4a635ae6712081e55cd83e55397d ;;
      ws-wss4j-a2) commit=d1347cb288174bb6442913fce2919945b05da136 ;;
    esac
    printf '%s\t%s\t%s\t%s\n' "$repository" "$arm" "$commit" \
      "$(<"$output/${repository}-${arm}.exit")" >>"$output/run-results.tsv"
  done
done
