#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
benchmark_root=$(cd "$script_dir/../../.." && pwd)
result_dir="$benchmark_root/results/log4j-a3-aws-powertools-screening-2026-08-25"
repository=${LOG4J_POWERTOOLS_SOURCE:-https://github.com/aws-powertools/powertools-lambda-java.git}
base=0184106b997ba587a33a5ac09a669ad33c3aa6b5
test_class=org.apache.logging.log4j.core.layout.LambdaJsonLayoutTest
export JAVA_HOME=${LOG4J_POWERTOOLS_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
m2_seed=${LOG4J_POWERTOOLS_M2_SEED:-$HOME/.m2/repository}

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有 Powertools A3 目录：$result_dir" >&2
  exit 3
fi
for path in "$JAVA_HOME" "$m2_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少筛选输入：$path" >&2
    exit 4
  fi
done

work_root=$(mktemp -d /tmp/marshal-log4j-powertools-a3.XXXXXX)
mkdir -p "$result_dir/runs" "$work_root/m2"
git clone --mirror --quiet "$repository" "$work_root/repository.git"
git --git-dir="$work_root/repository.git" cat-file -e "$base^{commit}"
cp -a --reflink=auto "$m2_seed/." "$work_root/m2/"

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'repository=%s\n' "$repository"
  printf 'base=%s\n' "$base"
  printf 'java_home=%s\n' "$JAVA_HOME"
  java -version 2>&1
  mvn -version
} >"$result_dir/environment.txt"

printf 'arm\tcommit\tlog4j_version\texit_code\ttests\tfailures\terrors\tduration_seconds\tdirection_ok\n' \
  >"$result_dir/run-results.tsv"

unexpected=0
after_consumer=
for arm in before after; do
  version=2.17.1
  if [[ $arm == after ]]; then
    version=2.17.2
  fi
  consumer="$work_root/consumers/$arm"
  run_dir="$result_dir/runs/$arm"
  mkdir -p "$run_dir"
  git clone --quiet "$work_root/repository.git" "$consumer"
  git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "$base"

  printf 'mvn -pl powertools-logging -am clean test -Dtest=%s -Dsurefire.failIfNoSpecifiedTests=false -Dlog4j.version=%s\n' \
    "$test_class" "$version" >"$run_dir/command.txt"
  started_epoch=$(date +%s)
  set +e
  (
    cd "$consumer" || exit 125
    timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$work_root/m2" -B -ntp \
      -pl powertools-logging -am clean test \
      "-Dtest=$test_class" -Dsurefire.failIfNoSpecifiedTests=false "-Dlog4j.version=$version"
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
      dependency:tree -Dincludes=org.apache.logging.log4j "-Dlog4j.version=$version"
  ) >"$run_dir/dependency-tree.log" 2>&1

  direction_ok=false
  if [[ $exit_code -eq 0 && $tests -gt 0 && $failures -eq 0 && $errors -eq 0 ]]; then
    direction_ok=true
  else
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$arm" "$base" "$version" "$exit_code" "$tests" "$failures" "$errors" \
    "$duration_seconds" "$direction_ok" >>"$result_dir/run-results.tsv"

  if [[ $arm == after ]]; then
    after_consumer=$consumer
  fi
done

exec_file="$after_consumer/powertools-logging/target/jacoco.exec"
core_jar="$work_root/m2/org/apache/logging/log4j/log4j-core/2.17.2/log4j-core-2.17.2.jar"
cli="$work_root/m2/org/jacoco/org.jacoco.cli/0.8.8/org.jacoco.cli-0.8.8-nodeps.jar"
classfiles="$work_root/log4j-classfiles"
coverage_dir="$result_dir/runs/after/coverage"
mkdir -p "$classfiles" "$coverage_dir"

if [[ ! -s $exec_file || ! -f $core_jar || ! -f $cli ]]; then
  echo "缺少 Powertools A3 覆盖输入" >&2
  exit 5
fi
unzip -q "$core_jar" -d "$classfiles"
find "$classfiles/META-INF/versions" -type f -delete 2>/dev/null || true
java -jar "$cli" report "$exec_file" --classfiles "$classfiles" \
  --xml "$coverage_dir/log4j-core.xml" --csv "$coverage_dir/log4j-core.csv" \
  >"$coverage_dir/report.log" 2>&1

line_value() {
  package_name=$1
  source_name=$2
  line_number=$3
  xmllint --xpath \
    "concat(/report/package[@name='$package_name']/sourcefile[@name='$source_name']/line[@nr='$line_number']/@mi, '/', /report/package[@name='$package_name']/sourcefile[@name='$source_name']/line[@nr='$line_number']/@ci)" \
    "$coverage_dir/log4j-core.xml"
}

logger_context=$(line_value org/apache/logging/log4j/core LoggerContext.java 291)
abstract_220=$(line_value org/apache/logging/log4j/core/config AbstractConfiguration.java 220)
abstract_221=$(line_value org/apache/logging/log4j/core/config AbstractConfiguration.java 221)
abstract_222=$(line_value org/apache/logging/log4j/core/config AbstractConfiguration.java 222)
semantic_hit=false
for value in "$logger_context" "$abstract_220" "$abstract_221" "$abstract_222"; do
  if [[ $value == 0/* ]]; then
    semantic_hit=true
  fi
done
if [[ $semantic_hit != true ]]; then
  unexpected=$((unexpected + 1))
fi

printf 'logger_context_291\tabstract_configuration_220\tabstract_configuration_221\tabstract_configuration_222\tsemantic_change_hit\n' \
  >"$result_dir/coverage-results.tsv"
printf '%s\t%s\t%s\t%s\t%s\n' \
  "$logger_context" "$abstract_220" "$abstract_221" "$abstract_222" "$semantic_hit" \
  >>"$result_dir/coverage-results.tsv"
rm "$coverage_dir/log4j-core.xml"

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$result_dir/environment.txt"

exit "$unexpected"
