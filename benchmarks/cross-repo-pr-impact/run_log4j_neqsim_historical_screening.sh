#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
work_parent=${MARSHAL_WORK_ROOT:-$repo_root/.work/cross-repo-pr-impact}
result_dir="$script_dir/results/log4j-neqsim-historical-screening-2026-08-24"
source_url=${LOG4J_NEQSIM_SOURCE:-https://github.com/equinor/neqsim.git}
export JAVA_HOME=${LOG4J_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
m2_seed=${LOG4J_NEQSIM_M2_SEED:-$HOME/.m2/repository}

declare -A commit=(
  [a0]=6cea014aecf9ca0956bb402bce2ed18e803b9b4b
  [a1]=e23721cb00132a55b32efcbd6fc6b382fb60e959
  [a2]=d622943718685b394364d36d5af61474cf881339
)
declare -A expected_api=([a0]=2.17.2 [a1]=2.17.2 [a2]=2.18.0)
declare -A expected_core=([a0]=2.17.2 [a1]=2.18.0 [a2]=2.18.0)
declare -A expected_result=([a0]=pass [a1]=fail [a2]=pass)

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有 Neqsim 历史筛选目录：$result_dir" >&2
  exit 3
fi
for path in "$JAVA_HOME" "$m2_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少筛选输入：$path" >&2
    exit 4
  fi
done

mkdir -p "$work_parent"
work_root=$(mktemp -d "$work_parent/marshal-log4j-neqsim-screening.XXXXXX")
mkdir -p "$result_dir/runs" "$work_root/mirror.git" "$work_root/m2" "$work_root/tmp" "$work_root/java-tmp"
export TMPDIR="$work_root/tmp"
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$work_root/java-tmp"
git clone --mirror --quiet "$source_url" "$work_root/mirror.git"
for config in a0 a1 a2; do
  git --git-dir="$work_root/mirror.git" cat-file -e "${commit[$config]}^{commit}"
done
cp -a --reflink=auto "$m2_seed/." "$work_root/m2/"

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'java_home=%s\n' "$JAVA_HOME"
  printf 'a0=parent before paired repository PRs 483 and 484\n'
  printf 'a1=repository merge of PR 484, Core only\n'
  printf 'a2=repository merge of PR 483 on top of PR 484, API and Core aligned\n'
  java -version 2>&1
  mvn -version
} >"$result_dir/environment.txt"

printf 'config\tcommit\texpected_api_version\texpected_core_version\tactual_api_version\tactual_core_version\texpected_result\texit_code\ttest_count\tfailure_signature_ok\tversion_ok\tdirection_ok\tduration_seconds\n' \
  >"$result_dir/run-results.tsv"

unexpected=0
for config in a0 a1 a2; do
  consumer="$work_root/consumers/$config"
  run_dir="$result_dir/runs/$config"
  mkdir -p "$run_dir"
  git clone --quiet "$work_root/mirror.git" "$consumer"
  git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "${commit[$config]}"
  git -C "$consumer" diff "${commit[a0]}" "${commit[$config]}" -- pom.xml >"$run_dir/input.diff"
  git -C "$consumer" show -s --format=fuller HEAD >"$run_dir/commit.txt"

  actual_api=$(xmllint --xpath \
    "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='log4j-api']/*[local-name()='version'])" \
    "$consumer/pom.xml")
  actual_core=$(xmllint --xpath \
    "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='log4j-core']/*[local-name()='version'])" \
    "$consumer/pom.xml")
  printf 'mvn -Dmaven.repo.local=%q -B -ntp clean test -DskipTests=false\n' \
    "$work_root/m2" >"$run_dir/command.txt"

  started_epoch=$(date +%s)
  set +e
  (
    cd "$consumer" || exit 125
    timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$work_root/m2" \
      -B -ntp clean test -DskipTests=false
  ) >"$run_dir/test.log" 2>&1
  exit_code=$?
  set -e
  duration_seconds=$(($(date +%s) - started_epoch))
  printf '%s\n' "$exit_code" >"$run_dir/exit-code.txt"

  test_count=0
  while IFS= read -r -d '' report; do
    count=$(xmllint --xpath 'string(/testsuite/@tests)' "$report" 2>/dev/null || printf '0')
    if [[ $count =~ ^[0-9]+$ ]]; then
      test_count=$((test_count + count))
    fi
  done < <(find "$consumer" -type f -path '*/surefire-reports/TEST-*.xml' -print0)

  failure_signature_ok=true
  if [[ ${expected_result[$config]} == fail ]]; then
    failure_signature_ok=false
    if rg -q 'NoClassDefFoundError: org/apache/logging/log4j/util/ServiceLoaderUtil' "$run_dir/test.log"; then
      failure_signature_ok=true
    fi
  fi
  version_ok=false
  if [[ $actual_api == "${expected_api[$config]}" && $actual_core == "${expected_core[$config]}" ]]; then
    version_ok=true
  fi
  direction_ok=false
  if [[ ${expected_result[$config]} == pass && $exit_code -eq 0 && $test_count -gt 0 ]]; then
    direction_ok=true
  elif [[ ${expected_result[$config]} == fail && $exit_code -ne 0 && $failure_signature_ok == true ]]; then
    direction_ok=true
  fi
  if [[ $version_ok != true || $direction_ok != true ]]; then
    unexpected=$((unexpected + 1))
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$config" "${commit[$config]}" "${expected_api[$config]}" "${expected_core[$config]}" \
    "$actual_api" "$actual_core" "${expected_result[$config]}" "$exit_code" "$test_count" \
    "$failure_signature_ok" "$version_ok" "$direction_ok" "$duration_seconds" \
    >>"$result_dir/run-results.tsv"
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$result_dir/environment.txt"

exit "$unexpected"
