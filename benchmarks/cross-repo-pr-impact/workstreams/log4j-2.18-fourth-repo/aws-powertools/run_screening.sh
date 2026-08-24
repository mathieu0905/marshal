#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
benchmark_root=$(cd "$script_dir/../../.." && pwd)
result_dir="$benchmark_root/results/log4j-2.18-aws-powertools-screening-2026-08-25"
repository=${LOG4J_POWERTOOLS_SOURCE:-https://github.com/aws-powertools/powertools-lambda-java.git}
base=0184106b997ba587a33a5ac09a669ad33c3aa6b5
head=76d6c35e99f936e3548df040eec5b2a9a35927e7
test_class=org.apache.logging.log4j.core.layout.LambdaJsonLayoutTest
export JAVA_HOME=${LOG4J_POWERTOOLS_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
m2_seed=${LOG4J_POWERTOOLS_M2_SEED:-$HOME/.m2/repository}

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有 aws-powertools 筛选目录：$result_dir" >&2
  exit 3
fi
for path in "$JAVA_HOME" "$m2_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少筛选输入：$path" >&2
    exit 4
  fi
done

work_root=$(mktemp -d /tmp/marshal-log4j-powertools.XXXXXX)
mkdir -p "$result_dir/runs" "$work_root/m2"
git clone --mirror --quiet "$repository" "$work_root/repository.git"
git --git-dir="$work_root/repository.git" cat-file -e "$base^{commit}"
git --git-dir="$work_root/repository.git" cat-file -e "$head^{commit}"
git --git-dir="$work_root/repository.git" merge-base --is-ancestor "$base" "$head"
cp -a --reflink=auto "$m2_seed/." "$work_root/m2/"

git --git-dir="$work_root/repository.git" show --format=fuller --stat "$head" \
  >"$result_dir/maintainer-change.txt"
git --git-dir="$work_root/repository.git" diff "$base" "$head" -- pom.xml \
  >"$result_dir/maintainer-change.patch"
{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'repository=%s\n' "$repository"
  printf 'base=%s\n' "$base"
  printf 'head=%s\n' "$head"
  printf 'java_home=%s\n' "$JAVA_HOME"
  java -version 2>&1
  mvn -version
} >"$result_dir/environment.txt"

printf 'arm\tcommit\tlog4j_version\taws_sdk_version\texit_code\ttests\tfailures\terrors\tduration_seconds\tdirection_ok\n' \
  >"$result_dir/run-results.tsv"

unexpected=0
for arm in baseline isolated_log4j maintainer_head; do
  consumer="$work_root/consumers/$arm"
  run_dir="$result_dir/runs/$arm"
  mkdir -p "$run_dir"
  git clone --quiet "$work_root/repository.git" "$consumer"
  commit=$base
  extra_args=()
  expected_log4j=2.17.2
  expected_aws=2.17.223
  if [[ $arm == isolated_log4j ]]; then
    extra_args=(-Dlog4j.version=2.18.0 -Daws.sdk.version=2.17.223)
    expected_log4j=2.18.0
  elif [[ $arm == maintainer_head ]]; then
    commit=$head
    expected_log4j=2.18.0
    expected_aws=2.17.224
  fi
  git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "$commit"

  log4j_version=$(mvn -q -f "$consumer/pom.xml" "-Dmaven.repo.local=$work_root/m2" \
    "${extra_args[@]}" help:evaluate -Dexpression=log4j.version -DforceStdout)
  aws_sdk_version=$(mvn -q -f "$consumer/pom.xml" "-Dmaven.repo.local=$work_root/m2" \
    "${extra_args[@]}" help:evaluate -Dexpression=aws.sdk.version -DforceStdout)
  printf 'mvn -pl powertools-logging -am clean test -Dtest=%s -Dsurefire.failIfNoSpecifiedTests=false' \
    "$test_class" >"$run_dir/command.txt"
  if [[ ${#extra_args[@]} -gt 0 ]]; then
    printf ' %q' "${extra_args[@]}" >>"$run_dir/command.txt"
  fi
  printf '\n' >>"$run_dir/command.txt"

  started_epoch=$(date +%s)
  set +e
  (
    cd "$consumer" || exit 125
    timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$work_root/m2" -B -ntp \
      -pl powertools-logging -am clean test \
      "-Dtest=$test_class" -Dsurefire.failIfNoSpecifiedTests=false "${extra_args[@]}"
  ) >"$run_dir/test.log" 2>&1
  exit_code=$?
  set -e
  duration_seconds=$(($(date +%s) - started_epoch))
  printf '%s\n' "$exit_code" >"$run_dir/exit-code.txt"

  report="$consumer/powertools-logging/target/surefire-reports/TEST-${test_class}.xml"
  tests=0
  failures=0
  errors=0
  if [[ -f $report ]]; then
    cp "$report" "$run_dir/"
    tests=$(xmllint --xpath 'string(/testsuite/@tests)' "$report")
    failures=$(xmllint --xpath 'string(/testsuite/@failures)' "$report")
    errors=$(xmllint --xpath 'string(/testsuite/@errors)' "$report")
  fi

  (
    cd "$consumer" || exit 125
    mvn "-Dmaven.repo.local=$work_root/m2" -B -ntp -pl powertools-logging \
      dependency:tree -Dincludes=org.apache.logging.log4j,software.amazon.awssdk "${extra_args[@]}"
  ) >"$run_dir/dependency-tree.log" 2>&1

  direction_ok=false
  if [[ $exit_code -eq 0 && $tests -gt 0 && $failures -eq 0 && $errors -eq 0 && \
        $log4j_version == "$expected_log4j" && $aws_sdk_version == "$expected_aws" ]]; then
    direction_ok=true
  else
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$arm" "$commit" "$log4j_version" "$aws_sdk_version" "$exit_code" "$tests" \
    "$failures" "$errors" "$duration_seconds" "$direction_ok" >>"$result_dir/run-results.tsv"

  if [[ $arm == isolated_log4j && -f $consumer/powertools-logging/target/jacoco.exec ]]; then
    coverage_dir="$run_dir/coverage"
    classfiles="$work_root/log4j-classfiles"
    mkdir -p "$coverage_dir" "$classfiles"
    unzip -q "$work_root/m2/org/apache/logging/log4j/log4j-core/2.18.0/log4j-core-2.18.0.jar" \
      'org/apache/logging/log4j/core/impl/ThreadContextDataInjector*.class' -d "$classfiles"
    java -jar "$work_root/m2/org/jacoco/org.jacoco.cli/0.8.8/org.jacoco.cli-0.8.8-nodeps.jar" \
      report "$consumer/powertools-logging/target/jacoco.exec" --classfiles "$classfiles" \
      --xml "$coverage_dir/log4j-core.xml" --csv "$coverage_dir/log4j-core.csv" \
      >"$coverage_dir/report.log" 2>&1
    missed=$(xmllint --xpath \
      "/report/package[@name='org/apache/logging/log4j/core/impl']/sourcefile[@name='ThreadContextDataInjector.java']/line[@nr='77']/@mi" \
      "$coverage_dir/log4j-core.xml" | sed -n 's/.*mi="\([0-9][0-9]*\)".*/\1/p')
    covered=$(xmllint --xpath \
      "/report/package[@name='org/apache/logging/log4j/core/impl']/sourcefile[@name='ThreadContextDataInjector.java']/line[@nr='77']/@ci" \
      "$coverage_dir/log4j-core.xml" | sed -n 's/.*ci="\([0-9][0-9]*\)".*/\1/p')
    printf 'surface\tmissed_instructions\tcovered_instructions\tsemantic_change_hit\n' \
      >"$result_dir/coverage-results.tsv"
    printf 'ThreadContextDataInjector.java:77\t%s\t%s\t%s\n' \
      "$missed" "$covered" "$([[ ${covered:-0} -gt 0 ]] && printf true || printf false)" \
      >>"$result_dir/coverage-results.tsv"
    if [[ ${covered:-0} -le 0 ]]; then
      unexpected=$((unexpected + 1))
    fi
    rm "$coverage_dir/log4j-core.xml"
  fi
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$result_dir/environment.txt"

exit "$unexpected"
