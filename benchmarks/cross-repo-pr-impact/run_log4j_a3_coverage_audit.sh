#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
work_parent=${MARSHAL_WORK_ROOT:-$repo_root/.work/cross-repo-pr-impact}
screening_dir="$script_dir/results/log4j-project-package-screening-2026-08-24"
result_dir="$script_dir/results/log4j-a3-coverage-audit-2026-08-24"

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有覆盖审计目录：$result_dir" >&2
  exit 3
fi
if [[ ! -f $screening_dir/environment.txt ]]; then
  echo "缺少 Log4j 筛选环境记录：$screening_dir/environment.txt" >&2
  exit 4
fi

work_root=${LOG4J_SCREENING_WORK_ROOT:-$(sed -n 's/^work_root=//p' "$screening_dir/environment.txt")}
export JAVA_HOME=${LOG4J_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
m2="$work_root/m2"
agent="$m2/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar"
cli="$m2/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar"
core_jar="$m2/org/apache/logging/log4j/log4j-core/2.17.2/log4j-core-2.17.2.jar"

for path in "$work_root/consumers/a3-after" "$m2" "$core_jar"; do
  if [[ ! -e $path ]]; then
    echo "缺少覆盖审计输入：$path" >&2
    exit 4
  fi
done

mkdir -p "$work_parent"
coverage_work=$(mktemp -d "$work_parent/marshal-log4j-a3-coverage.XXXXXX")
classfiles="$coverage_work/classfiles"
mkdir -p "$result_dir/runs" "$classfiles" "$coverage_work/tmp" "$coverage_work/java-tmp"
export TMPDIR="$coverage_work/tmp"
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$coverage_work/java-tmp"
mvn -q "-Dmaven.repo.local=$m2" dependency:get \
  -Dartifact=org.jacoco:org.jacoco.agent:0.8.12:jar:runtime
mvn -q "-Dmaven.repo.local=$m2" dependency:get \
  -Dartifact=org.jacoco:org.jacoco.cli:0.8.12:jar:nodeps
unzip -q "$core_jar" -d "$classfiles"
find "$classfiles/META-INF/versions" -type f -delete 2>/dev/null || true

printf 'repository\ttest_exit_code\texec_bytes\tlogger_context_291\tabstract_configuration_220\tabstract_configuration_221\tabstract_configuration_222\tsemantic_change_hit\n' \
  >"$result_dir/changed-line-coverage.tsv"

repos=(apktoolbox neqsim ivymx archifacts)
unexpected=0
for repo in "${repos[@]}"; do
  consumer="$work_root/consumers/a3-after/$repo"
  run_dir="$result_dir/runs/$repo"
  mkdir -p "$run_dir"
  exec_file="$run_dir/log4j-core.exec"

  if [[ $repo == archifacts ]]; then
    (
      cd "$consumer" || exit 125
      timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$m2" -B -ntp \
        install -DskipTests -Dmaven.javadoc.skip=true
    ) >"$run_dir/install.log" 2>&1
  fi

  printf "mvn -Dmaven.repo.local=%q '-DargLine=-javaagent:%q=destfile=%q,append=true,includes=org.apache.logging.log4j.core.*' -B -ntp surefire:test -DskipTests=false\n" \
    "$m2" "$agent" "$exec_file" >"$run_dir/command.txt"
  set +e
  (
    cd "$consumer" || exit 125
    timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$m2" \
      "-DargLine=-javaagent:$agent=destfile=$exec_file,append=true,includes=org.apache.logging.log4j.core.*" \
      -B -ntp surefire:test -DskipTests=false
  ) >"$run_dir/test.log" 2>&1
  exit_code=$?
  set -e
  printf '%s\n' "$exit_code" >"$run_dir/exit-code.txt"

  if [[ ! -s $exec_file ]]; then
    echo "覆盖执行数据为空：$repo" >&2
    unexpected=$((unexpected + 1))
    continue
  fi
  java -jar "$cli" report "$exec_file" \
    --classfiles "$classfiles" \
    --xml "$run_dir/log4j-core.xml" \
    --csv "$run_dir/log4j-core.csv" \
    >"$run_dir/report.log" 2>&1

  logger_context=$(xmllint --xpath \
    "concat(/report/package[@name='org/apache/logging/log4j/core']/sourcefile[@name='LoggerContext.java']/line[@nr='291']/@mi, '/', /report/package[@name='org/apache/logging/log4j/core']/sourcefile[@name='LoggerContext.java']/line[@nr='291']/@ci)" \
    "$run_dir/log4j-core.xml")
  abstract_220=$(xmllint --xpath \
    "concat(/report/package[@name='org/apache/logging/log4j/core/config']/sourcefile[@name='AbstractConfiguration.java']/line[@nr='220']/@mi, '/', /report/package[@name='org/apache/logging/log4j/core/config']/sourcefile[@name='AbstractConfiguration.java']/line[@nr='220']/@ci)" \
    "$run_dir/log4j-core.xml")
  abstract_221=$(xmllint --xpath \
    "concat(/report/package[@name='org/apache/logging/log4j/core/config']/sourcefile[@name='AbstractConfiguration.java']/line[@nr='221']/@mi, '/', /report/package[@name='org/apache/logging/log4j/core/config']/sourcefile[@name='AbstractConfiguration.java']/line[@nr='221']/@ci)" \
    "$run_dir/log4j-core.xml")
  abstract_222=$(xmllint --xpath \
    "concat(/report/package[@name='org/apache/logging/log4j/core/config']/sourcefile[@name='AbstractConfiguration.java']/line[@nr='222']/@mi, '/', /report/package[@name='org/apache/logging/log4j/core/config']/sourcefile[@name='AbstractConfiguration.java']/line[@nr='222']/@ci)" \
    "$run_dir/log4j-core.xml")

  semantic_hit=false
  if [[ $logger_context == 0/* || $abstract_220 == 0/* || $abstract_221 == 0/* || $abstract_222 == 0/* ]]; then
    semantic_hit=true
  fi
  if [[ $exit_code -ne 0 ]]; then
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$repo" "$exit_code" "$(stat -c %s "$exec_file")" "$logger_context" \
    "$abstract_220" "$abstract_221" "$abstract_222" "$semantic_hit" \
    >>"$result_dir/changed-line-coverage.tsv"
  rm "$run_dir/log4j-core.xml"
done

{
  printf 'screening_work_root=%s\n' "$work_root"
  printf 'audited_version=2.17.2\n'
  printf 'unexpected_test_results=%s\n' "$unexpected"
  printf 'coverage_scope=Log4j Core classes only; direct surefire replay after the full screening build\n'
  printf 'multi_release_note=Java 9 SystemClock differs from the base class; target semantic lines are outside that class\n'
} >"$result_dir/README.txt"

exit "$unexpected"
