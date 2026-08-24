#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
result_dir="$script_dir/results/log4j-2.18-negative-screening-2026-08-24"
export JAVA_HOME=${LOG4J_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
m2_seed=${LOG4J_NEGATIVE_M2_SEED:-$HOME/.m2/repository}

declare -A source=(
  [archifacts]="${LOG4J_ARCHIFACTS_SOURCE:-https://github.com/archifacts/archifacts.git}"
  [elimu]="${LOG4J_ELIMU_SOURCE:-https://github.com/elimu-ai/webapp.git}"
)
declare -A baseline=(
  [archifacts]=157a8962a1934c346ae09849db69e3d603df6b6c
  [elimu]=460e263ec22d4768e1b6f171795eef20e4ace80a
)

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有 Log4j 2.18 限定负例筛选目录：$result_dir" >&2
  exit 3
fi
for path in "$JAVA_HOME" "$m2_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少筛选输入：$path" >&2
    exit 4
  fi
done

work_root=$(mktemp -d /tmp/marshal-log4j-2.18-negative.XXXXXX)
mkdir -p "$result_dir/runs" "$work_root/mirrors" "$work_root/m2"
for repo in archifacts elimu; do
  git clone --mirror --quiet "${source[$repo]}" "$work_root/mirrors/$repo.git"
  git --git-dir="$work_root/mirrors/$repo.git" cat-file -e "${baseline[$repo]}^{commit}"
done
cp -a --reflink=auto "$m2_seed/." "$work_root/m2/"
mvn -q "-Dmaven.repo.local=$work_root/m2" dependency:get \
  -Dartifact=org.jacoco:org.jacoco.agent:0.8.12:jar:runtime
mvn -q "-Dmaven.repo.local=$work_root/m2" dependency:get \
  -Dartifact=org.jacoco:org.jacoco.cli:0.8.12:jar:nodeps
agent="$work_root/m2/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar"
cli="$work_root/m2/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar"

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'java_home=%s\n' "$JAVA_HOME"
  java -version 2>&1
  mvn -version
} >"$result_dir/environment.txt"

printf 'repository\tactual_api_version\tactual_core_version\texit_code\ttest_count\tversion_ok\tdirection_ok\tduration_seconds\n' \
  >"$result_dir/run-results.tsv"
printf 'repository\texec_bytes\tchange_surface\tmissed_instructions\tcovered_instructions\tsemantic_change_hit\n' \
  >"$result_dir/coverage-results.tsv"

unexpected=0
for repo in archifacts elimu; do
  consumer="$work_root/consumers/$repo"
  run_dir="$result_dir/runs/$repo"
  mkdir -p "$run_dir"
  git clone --quiet "$work_root/mirrors/$repo.git" "$consumer"
  git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "${baseline[$repo]}"

  if [[ $repo == archifacts ]]; then
    mvn -q -f "$consumer/pom.xml" "-Dmaven.repo.local=$work_root/m2" \
      org.codehaus.mojo:versions-maven-plugin:2.16.2:set-property \
      -Dproperty=log4j.version -DnewVersion=2.18.0 -DgenerateBackupPoms=false
    property_pom="$consumer/parent/pom.xml"
  else
    mvn -q -f "$consumer/pom.xml" "-Dmaven.repo.local=$work_root/m2" \
      org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
      -Dincludes=org.apache.logging.log4j:log4j-api,org.apache.logging.log4j:log4j-core \
      -DdepVersion=2.18.0 -DforceVersion=true -DgenerateBackupPoms=false
    property_pom="$consumer/pom.xml"
  fi

  if [[ $repo == archifacts ]]; then
    actual_api=$(xmllint --xpath "string(/*[local-name()='project']/*[local-name()='properties']/*[local-name()='log4j.version'])" "$property_pom")
    actual_core=$actual_api
  else
    actual_api=$(xmllint --xpath \
      "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='log4j-api']/*[local-name()='version'])" \
      "$property_pom")
    actual_core=$(xmllint --xpath \
      "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='log4j-core']/*[local-name()='version'])" \
      "$property_pom")
  fi
  git -C "$consumer" diff >"$run_dir/input.diff"
  printf 'mvn -Dmaven.repo.local=%q -B -ntp clean test -DskipTests=false\n' "$work_root/m2" >"$run_dir/command.txt"

  started_epoch=$(date +%s)
  set +e
  (
    cd "$consumer" || exit 125
    timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$work_root/m2" -B -ntp clean test -DskipTests=false
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
  version_ok=false
  direction_ok=false
  if [[ $actual_api == 2.18.0 && $actual_core == 2.18.0 ]]; then
    version_ok=true
  fi
  if [[ $exit_code -eq 0 && $test_count -gt 0 ]]; then
    direction_ok=true
  fi
  if [[ $version_ok != true || $direction_ok != true ]]; then
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$repo" "$actual_api" "$actual_core" "$exit_code" "$test_count" "$version_ok" \
    "$direction_ok" "$duration_seconds" >>"$result_dir/run-results.tsv"

  coverage_dir="$run_dir/coverage"
  classfiles="$work_root/classfiles/$repo"
  exec_file="$coverage_dir/log4j-core.exec"
  mkdir -p "$coverage_dir" "$classfiles"
  unzip -q "$work_root/m2/org/apache/logging/log4j/log4j-core/2.18.0/log4j-core-2.18.0.jar" -d "$classfiles"
  find "$classfiles/META-INF/versions" -type f -delete 2>/dev/null || true
  if [[ $repo == archifacts ]]; then
    (
      cd "$consumer" || exit 125
      timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$work_root/m2" -B -ntp \
        install -DskipTests -Dmaven.javadoc.skip=true
    ) >"$coverage_dir/install.log" 2>&1
  fi
  (
    cd "$consumer" || exit 125
    timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$work_root/m2" \
      "-DargLine=-javaagent:$agent=destfile=$exec_file,append=true,includes=org.apache.logging.log4j.core.*" \
      -B -ntp surefire:test -DskipTests=false
  ) >"$coverage_dir/test.log" 2>&1
  java -jar "$cli" report "$exec_file" --classfiles "$classfiles" \
    --xml "$coverage_dir/log4j-core.xml" --csv "$coverage_dir/log4j-core.csv" \
    >"$coverage_dir/report.log" 2>&1
  missed=$(xmllint --xpath \
    "/report/package[@name='org/apache/logging/log4j/core/impl']/sourcefile[@name='ThreadContextDataInjector.java']/line[@nr='77']/@mi" \
    "$coverage_dir/log4j-core.xml" | sed -n 's/.*mi="\([0-9][0-9]*\)".*/\1/p')
  covered=$(xmllint --xpath \
    "/report/package[@name='org/apache/logging/log4j/core/impl']/sourcefile[@name='ThreadContextDataInjector.java']/line[@nr='77']/@ci" \
    "$coverage_dir/log4j-core.xml" | sed -n 's/.*ci="\([0-9][0-9]*\)".*/\1/p')
  semantic_hit=false
  if [[ ${covered:-0} -gt 0 ]]; then
    semantic_hit=true
  else
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\tservice_loader_call:77\t%s\t%s\t%s\n' \
    "$repo" "$(stat -c %s "$exec_file")" "$missed" "$covered" "$semantic_hit" \
    >>"$result_dir/coverage-results.tsv"
  rm "$coverage_dir/log4j-core.xml"
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$result_dir/environment.txt"

exit "$unexpected"
