#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
work_parent=${MARSHAL_WORK_ROOT:-$repo_root/.work/cross-repo-pr-impact}
result_dir="$script_dir/results/log4j-elimu-candidate-screening-2026-08-24"
source_url=${LOG4J_ELIMU_SOURCE:-https://github.com/elimu-ai/webapp.git}
consumer_commit=460e263ec22d4768e1b6f171795eef20e4ace80a
export JAVA_HOME=${LOG4J_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
m2_seed=${LOG4J_ELIMU_M2_SEED:-$HOME/.m2/repository}

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有 elimu-ai 筛选目录：$result_dir" >&2
  exit 3
fi
for path in "$JAVA_HOME" "$m2_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少筛选输入：$path" >&2
    exit 4
  fi
done

mkdir -p "$work_parent"
work_root=$(mktemp -d "$work_parent/marshal-log4j-elimu-screening.XXXXXX")
mkdir -p "$result_dir/runs" "$work_root/mirror.git" "$work_root/m2" "$work_root/tmp" "$work_root/java-tmp"
export TMPDIR="$work_root/tmp"
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$work_root/java-tmp"
git clone --mirror --quiet "$source_url" "$work_root/mirror.git"
git --git-dir="$work_root/mirror.git" cat-file -e "$consumer_commit^{commit}"
cp -a --reflink=auto "$m2_seed/." "$work_root/m2/"

mvn -q "-Dmaven.repo.local=$work_root/m2" dependency:get \
  -Dartifact=org.jacoco:org.jacoco.agent:0.8.12:jar:runtime
mvn -q "-Dmaven.repo.local=$work_root/m2" dependency:get \
  -Dartifact=org.jacoco:org.jacoco.cli:0.8.12:jar:nodeps

agent="$work_root/m2/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar"
cli="$work_root/m2/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar"
configs=(a0 a1 a3-before a3-after)

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'consumer_commit=%s\n' "$consumer_commit"
  printf 'java_home=%s\n' "$JAVA_HOME"
  java -version 2>&1
  mvn -version
} >"$result_dir/environment.txt"

printf 'config\texpected_version\tactual_api_version\tactual_core_version\texit_code\ttest_count\tversion_ok\tdirection_ok\tduration_seconds\n' \
  >"$result_dir/run-results.tsv"

unexpected=0
for config in "${configs[@]}"; do
  case $config in
    a0|a3-after) version=2.17.2 ;;
    a1) version=2.19.0 ;;
    a3-before) version=2.17.1 ;;
  esac

  consumer="$work_root/consumers/$config"
  run_dir="$result_dir/runs/$config"
  mkdir -p "$run_dir"
  git clone --quiet "$work_root/mirror.git" "$consumer"
  git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "$consumer_commit"
  mvn -q -f "$consumer/pom.xml" "-Dmaven.repo.local=$work_root/m2" \
    org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
    -Dincludes=org.apache.logging.log4j:log4j-api,org.apache.logging.log4j:log4j-core \
    -DdepVersion="$version" -DforceVersion=true -DgenerateBackupPoms=false

  actual_api=$(xmllint --xpath \
    "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='log4j-api']/*[local-name()='version'])" \
    "$consumer/pom.xml")
  actual_core=$(xmllint --xpath \
    "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='log4j-core']/*[local-name()='version'])" \
    "$consumer/pom.xml")
  git -C "$consumer" diff >"$run_dir/input.diff"
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

  version_ok=false
  direction_ok=false
  if [[ $actual_api == "$version" && $actual_core == "$version" ]]; then
    version_ok=true
  fi
  if [[ $exit_code -eq 0 && $test_count -gt 0 ]]; then
    direction_ok=true
  fi
  if [[ $version_ok != true || $direction_ok != true ]]; then
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$config" "$version" "$actual_api" "$actual_core" "$exit_code" "$test_count" \
    "$version_ok" "$direction_ok" "$duration_seconds" >>"$result_dir/run-results.tsv"
done

printf 'config\taudited_version\texec_bytes\tchange_surface\tmissed_instructions\tcovered_instructions\tsemantic_change_hit\n' \
  >"$result_dir/coverage-results.tsv"
for config in a1 a3-after; do
  if [[ $config == a1 ]]; then
    version=2.19.0
    package=org/apache/logging/log4j/core/impl
    source=ThreadContextDataInjector.java
    line=77
    change_surface=service_loader_call
  else
    version=2.17.2
    package=org/apache/logging/log4j/core
    source=LoggerContext.java
    line=291
    change_surface=logger_context_initialization
  fi

  consumer="$work_root/consumers/$config"
  run_dir="$result_dir/runs/$config/coverage"
  classfiles="$work_root/classfiles/$config"
  exec_file="$run_dir/log4j-core.exec"
  mkdir -p "$run_dir" "$classfiles"
  unzip -q "$work_root/m2/org/apache/logging/log4j/log4j-core/$version/log4j-core-$version.jar" \
    -d "$classfiles"
  find "$classfiles/META-INF/versions" -type f -delete 2>/dev/null || true
  printf "mvn -Dmaven.repo.local=%q '-DargLine=-javaagent:%q=destfile=%q,append=true,includes=org.apache.logging.log4j.core.*' -B -ntp surefire:test -DskipTests=false\n" \
    "$work_root/m2" "$agent" "$exec_file" >"$run_dir/command.txt"
  (
    cd "$consumer" || exit 125
    timeout --signal=TERM 60m mvn "-Dmaven.repo.local=$work_root/m2" \
      "-DargLine=-javaagent:$agent=destfile=$exec_file,append=true,includes=org.apache.logging.log4j.core.*" \
      -B -ntp surefire:test -DskipTests=false
  ) >"$run_dir/test.log" 2>&1
  java -jar "$cli" report "$exec_file" --classfiles "$classfiles" \
    --xml "$run_dir/log4j-core.xml" --csv "$run_dir/log4j-core.csv" \
    >"$run_dir/report.log" 2>&1

  missed=$(xmllint --xpath "/report/package[@name='$package']/sourcefile[@name='$source']/line[@nr='$line']/@mi" \
    "$run_dir/log4j-core.xml" | sed -n 's/.*mi="\([0-9][0-9]*\)".*/\1/p')
  covered=$(xmllint --xpath "/report/package[@name='$package']/sourcefile[@name='$source']/line[@nr='$line']/@ci" \
    "$run_dir/log4j-core.xml" | sed -n 's/.*ci="\([0-9][0-9]*\)".*/\1/p')
  semantic_hit=false
  if [[ ${covered:-0} -gt 0 ]]; then
    semantic_hit=true
  else
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\t%s:%s\t%s\t%s\t%s\n' \
    "$config" "$version" "$(stat -c %s "$exec_file")" "$change_surface" "$line" \
    "$missed" "$covered" "$semantic_hit" >>"$result_dir/coverage-results.tsv"
  rm "$run_dir/log4j-core.xml"
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
  printf 'failed_attempt_note=the exploratory run reused an empty xml-apis-ext jar; this script uses an isolated writable dependency directory\n'
} >>"$result_dir/environment.txt"

exit "$unexpected"
