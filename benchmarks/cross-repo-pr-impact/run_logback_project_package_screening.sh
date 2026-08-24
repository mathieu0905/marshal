#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
work_parent=${MARSHAL_WORK_ROOT:-$repo_root/.work/cross-repo-pr-impact}
result_dir="$script_dir/results/logback-project-package-screening-2026-08-24"
java11_home=${LOGBACK_JAVA11_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
java17_home=${LOGBACK_JAVA17_HOME:-$HOME/.jdks/jdk-17.0.18+8}
gradle74=${LOGBACK_GRADLE74:-$work_parent/tooling/gradle-7.4.2/bin/gradle}
gradle75=${LOGBACK_GRADLE75:-$work_parent/tooling/gradle-7.5.1/bin/gradle}
m2_seed=${LOGBACK_M2_SEED:-$HOME/.m2/repository}
gradle_seed=${LOGBACK_GRADLE_SEED:-$HOME/.gradle}

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有 Logback 筛选目录：$result_dir" >&2
  exit 3
fi
for path in "$java11_home/bin/java" "$java17_home/bin/java" "$gradle74" "$gradle75" "$m2_seed" "$gradle_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少筛选输入：$path" >&2
    exit 4
  fi
done

mkdir -p "$work_parent"
work_root=$(mktemp -d "$work_parent/marshal-logback-screening.XXXXXX")
mkdir -p "$result_dir/runs" "$result_dir/coverage" "$work_root/mirrors" "$work_root/m2" "$work_root/gradle-home" "$work_root/tmp" "$work_root/java-tmp"
export TMPDIR="$work_root/tmp"
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$work_root/java-tmp"
cp -a --reflink=auto "$m2_seed/." "$work_root/m2/"
cp -a --reflink=auto "$gradle_seed/." "$work_root/gradle-home/"

declare -A repo_url=(
  [html2pop3]=https://github.com/matteobaccan/html2pop3.git
  [tokendings]=https://github.com/nais/tokendings.git
  [kompendium]=https://github.com/bkbnio/kompendium.git
)
declare -A repo_commit=(
  [html2pop3]=bc401892bc13d8143552dce7c1e8c79f594c680b
  [tokendings]=1e857fd2b3ccf529f70423c142b79963e3b10990
  [kompendium]=76e6b0a2784d1064b26c33fd1a33128f89688f20
)
repositories=(html2pop3 tokendings kompendium)
configs=(a0 a1 a2 a3-before a3-after)

for repo in "${repositories[@]}"; do
  git clone --mirror --quiet "${repo_url[$repo]}" "$work_root/mirrors/$repo.git"
  git --git-dir="$work_root/mirrors/$repo.git" cat-file -e "${repo_commit[$repo]}^{commit}"
done

export JAVA_HOME=$java11_home
export PATH="$JAVA_HOME/bin:$PATH"
mvn -q "-Dmaven.repo.local=$work_root/m2" dependency:get \
  -Dartifact=org.jacoco:org.jacoco.agent:0.8.12:jar:runtime
mvn -q "-Dmaven.repo.local=$work_root/m2" dependency:get \
  -Dartifact=org.jacoco:org.jacoco.cli:0.8.12:jar:nodeps
for artifact in logback-classic logback-core; do
  mvn -q "-Dmaven.repo.local=$work_root/m2" dependency:get \
    -Dartifact="ch.qos.logback:$artifact:1.4.1"
done

agent="$work_root/m2/org/jacoco/org.jacoco.agent/0.8.12/org.jacoco.agent-0.8.12-runtime.jar"
cli="$work_root/m2/org/jacoco/org.jacoco.cli/0.8.12/org.jacoco.cli-0.8.12-nodeps.jar"
classic_jar="$work_root/m2/ch/qos/logback/logback-classic/1.4.1/logback-classic-1.4.1.jar"
core_jar="$work_root/m2/ch/qos/logback/logback-core/1.4.1/logback-core-1.4.1.jar"

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'java11_home=%s\n' "$java11_home"
  printf 'java17_home=%s\n' "$java17_home"
  "$java11_home/bin/java" -version 2>&1
  "$java17_home/bin/java" -version 2>&1
  "$gradle74" --version
  "$gradle75" --version
  mvn -version
} >"$result_dir/environment.txt"

configure_consumer() {
  local repo=$1 config=$2 consumer=$3
  local classic_version core_version
  case $config in
    a0) classic_version=1.2.11; core_version=1.2.11 ;;
    a1) classic_version=1.4.0; core_version=1.2.11 ;;
    a2|a3-before) classic_version=1.4.0; core_version=1.4.0 ;;
    a3-after) classic_version=1.4.1; core_version=1.4.1 ;;
    *) return 2 ;;
  esac

  case $repo in
    html2pop3)
      mvn -q -f "$consumer/pom.xml" "-Dmaven.repo.local=$work_root/m2" \
        org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
        -Dincludes=ch.qos.logback:logback-classic -DdepVersion="$classic_version" \
        -DforceVersion=true -DgenerateBackupPoms=false
      mvn -q -f "$consumer/pom.xml" "-Dmaven.repo.local=$work_root/m2" \
        org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
        -Dincludes=ch.qos.logback:logback-core -DdepVersion="$core_version" \
        -DforceVersion=true -DgenerateBackupPoms=false
      ;;
    tokendings)
      sed -i "s/val logbackVersion = \"1.2.11\"/val logbackVersion = \"$classic_version\"/" \
        "$consumer/build.gradle.kts"
      rg -q "val logbackVersion = \"$classic_version\"" "$consumer/build.gradle.kts"
      ;;
    kompendium)
      sed -i "s/ch.qos.logback:logback-classic:1.2.11/ch.qos.logback:logback-classic:$classic_version/" \
        "$consumer/core/build.gradle.kts"
      rg -q "ch.qos.logback:logback-classic:$classic_version" "$consumer/core/build.gradle.kts"
      ;;
  esac
}

copy_test_results() {
  local consumer=$1 run_dir=$2
  while IFS= read -r -d '' report; do
    local relative=${report#"$consumer"/}
    mkdir -p "$run_dir/test-results/$(dirname "$relative")"
    cp "$report" "$run_dir/test-results/$relative"
  done < <(find "$consumer" -type f \( -path '*/surefire-reports/TEST-*.xml' -o -path '*/test-results/test/TEST-*.xml' \) -print0)
}

count_test_results() {
  local consumer=$1
  local tests=0 failures=0 errors=0 skipped=0
  while IFS= read -r -d '' report; do
    local value
    value=$(xmllint --xpath 'string(/testsuite/@tests)' "$report" 2>/dev/null || printf '0')
    [[ $value =~ ^[0-9]+$ ]] && tests=$((tests + value))
    value=$(xmllint --xpath 'string(/testsuite/@failures)' "$report" 2>/dev/null || printf '0')
    [[ $value =~ ^[0-9]+$ ]] && failures=$((failures + value))
    value=$(xmllint --xpath 'string(/testsuite/@errors)' "$report" 2>/dev/null || printf '0')
    [[ $value =~ ^[0-9]+$ ]] && errors=$((errors + value))
    value=$(xmllint --xpath 'string(/testsuite/@skipped)' "$report" 2>/dev/null || printf '0')
    [[ $value =~ ^[0-9]+$ ]] && skipped=$((skipped + value))
  done < <(find "$consumer" -type f \( -path '*/surefire-reports/TEST-*.xml' -o -path '*/test-results/test/TEST-*.xml' \) -print0)
  printf '%s\t%s\t%s\t%s\n' "$tests" "$failures" "$errors" "$skipped"
}

dependency_versions() {
  local repo=$1 consumer=$2 run_dir=$3
  local classic core slf4j
  case $repo in
    html2pop3)
      (
        cd "$consumer" || exit 125
        mvn "-Dmaven.repo.local=$work_root/m2" -B -ntp dependency:tree \
          -DoutputFile="$run_dir/dependencies.txt" -DoutputType=text
      ) >"$run_dir/dependencies-command.log" 2>&1
      ;;
    tokendings)
      (
        cd "$consumer" || exit 125
        GRADLE_USER_HOME="$work_root/gradle-home" JAVA_HOME="$java17_home" \
          "$gradle74" --no-daemon dependencies --configuration testRuntimeClasspath
      ) >"$run_dir/dependencies.txt" 2>"$run_dir/dependencies-command.log"
      ;;
    kompendium)
      (
        cd "$consumer" || exit 125
        GRADLE_USER_HOME="$work_root/gradle-home" JAVA_HOME="$java11_home" \
          "$gradle75" --no-daemon :kompendium-core:dependencies --configuration testRuntimeClasspath
      ) >"$run_dir/dependencies.txt" 2>"$run_dir/dependencies-command.log"
      ;;
  esac
  if [[ $repo == html2pop3 ]]; then
    classic=$(awk -F: '/ch\.qos\.logback:logback-classic:jar:/ {print $4; exit}' "$run_dir/dependencies.txt")
    core=$(awk -F: '/ch\.qos\.logback:logback-core:jar:/ {print $4; exit}' "$run_dir/dependencies.txt")
    slf4j=$(awk -F: '/org\.slf4j:slf4j-api:jar:/ {print $4; exit}' "$run_dir/dependencies.txt")
  else
    classic=$(rg 'ch\.qos\.logback:logback-classic:' "$run_dir/dependencies.txt" | \
      rg -o '[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1 || true)
    core=$(rg 'ch\.qos\.logback:logback-core:' "$run_dir/dependencies.txt" | \
      rg -o '[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1 || true)
    slf4j=$(rg 'org\.slf4j:slf4j-api:' "$run_dir/dependencies.txt" | \
      rg -o '[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1 || true)
  fi
  printf '%s\t%s\t%s\n' "$classic" "$core" "$slf4j"
}

printf 'repository\tconfig\tclassic_version\tcore_version\tslf4j_version\texit_code\ttests\tfailures\terrors\tskipped\tversion_ok\tdirection_ok\tlog_surface_ok\tduration_seconds\n' \
  >"$result_dir/run-results.tsv"

unexpected=0
for repo in "${repositories[@]}"; do
  for config in "${configs[@]}"; do
    consumer="$work_root/consumers/$repo-$config"
    run_dir="$result_dir/runs/$repo/$config"
    mkdir -p "$run_dir"
    git clone --quiet "$work_root/mirrors/$repo.git" "$consumer"
    git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "${repo_commit[$repo]}"
    configure_consumer "$repo" "$config" "$consumer"
    git -C "$consumer" diff >"$run_dir/input.diff"

    case $repo in
      html2pop3)
        java_home=$java17_home
        command=(mvn "-Dmaven.repo.local=$work_root/m2" -B -ntp clean test)
        ;;
      tokendings)
        java_home=$java17_home
        command=("$gradle74" --no-daemon cleanTest test --tests io.nais.security.oauth2.routing.ObservabilityApiTest)
        ;;
      kompendium)
        java_home=$java11_home
        command=("$gradle75" --no-daemon :kompendium-core:cleanTest :kompendium-core:test)
        ;;
    esac
    printf '%q ' "${command[@]}" >"$run_dir/command.txt"
    printf '\n' >>"$run_dir/command.txt"

    started_epoch=$(date +%s)
    set +e
    (
      cd "$consumer" || exit 125
      GRADLE_USER_HOME="$work_root/gradle-home" JAVA_HOME="$java_home" \
        timeout --signal=TERM 60m "${command[@]}"
    ) >"$run_dir/test.log" 2>&1
    exit_code=$?
    set -e
    duration_seconds=$(($(date +%s) - started_epoch))
    printf '%s\n' "$exit_code" >"$run_dir/exit-code.txt"
    copy_test_results "$consumer" "$run_dir"
    IFS=$'\t' read -r tests failures errors skipped < <(count_test_results "$consumer")
    IFS=$'\t' read -r classic core slf4j < <(dependency_versions "$repo" "$consumer" "$run_dir")

    case $config in
      a0) expected_classic=1.2.11 ;;
      a1|a2|a3-before) expected_classic=1.4.0 ;;
      a3-after) expected_classic=1.4.1 ;;
    esac
    version_ok=false
    [[ $classic == "$expected_classic" ]] && version_ok=true

    direction_ok=false
    if [[ $repo == html2pop3 && $config == a1 ]]; then
      if [[ $exit_code -ne 0 && $errors -ge 2 ]] && rg -q 'NoSuchMethodError.*EnvUtil\.logbackVersion' "$run_dir/test.log"; then
        direction_ok=true
      fi
    elif [[ $exit_code -eq 0 && $tests -gt 0 && $failures -eq 0 && $errors -eq 0 ]]; then
      direction_ok=true
    fi

    log_surface_ok=not_applicable
    if [[ $repo == tokendings ]]; then
      log_surface_ok=false
      if rg -a --no-ignore -q 'Application started' "$run_dir/test-results" && \
         rg -a --no-ignore -q 'RuntimeException: oh noes' "$run_dir/test-results"; then
        log_surface_ok=true
      fi
    elif [[ $repo == kompendium ]]; then
      log_surface_ok=false
      if rg -a --no-ignore -q 'Application started' "$run_dir/test-results" && \
         rg -a --no-ignore -q 'DEBUG|INFO' "$run_dir/test-results"; then
        log_surface_ok=true
      fi
    fi

    if [[ $version_ok != true || $direction_ok != true || $log_surface_ok == false ]]; then
      unexpected=$((unexpected + 1))
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$repo" "$config" "$classic" "$core" "$slf4j" "$exit_code" "$tests" \
      "$failures" "$errors" "$skipped" "$version_ok" "$direction_ok" \
      "$log_surface_ok" "$duration_seconds" >>"$result_dir/run-results.tsv"
  done
done

printf 'repository\texec_bytes\tcontext_line_81_covered\tcontext_line_82_covered\tenv_line_36_covered\tenv_line_56_covered\tenv_line_60_covered\tsemantic_change_hit\n' \
  >"$result_dir/coverage-results.tsv"

for repo in "${repositories[@]}"; do
  consumer="$work_root/consumers/$repo-a3-after"
  coverage_dir="$result_dir/coverage/$repo"
  exec_file="$coverage_dir/logback.exec"
  mkdir -p "$coverage_dir"
  agent_arg="-javaagent:$agent=destfile=$exec_file,append=true,includes=ch.qos.logback.*"

  case $repo in
    html2pop3)
      printf 'mvn -Dmaven.repo.local=%q -DargLine=%q -B -ntp surefire:test\n' \
        "$work_root/m2" "$agent_arg" >"$coverage_dir/command.txt"
      set +e
      (
        cd "$consumer" || exit 125
        JAVA_HOME="$java11_home" timeout --signal=TERM 60m mvn \
          "-Dmaven.repo.local=$work_root/m2" "-DargLine=$agent_arg" -B -ntp surefire:test
      ) >"$coverage_dir/test.log" 2>&1
      coverage_exit=$?
      set -e
      ;;
    tokendings)
      printf '%s\n' \
        'allprojects {' \
        '  tasks.withType(org.gradle.api.tasks.testing.Test).configureEach {' \
        "    jvmArgs '$agent_arg'" \
        '  }' \
        '}' >"$work_root/logback-jacoco.init.gradle"
      coverage_command=(cleanTest test --tests io.nais.security.oauth2.routing.ObservabilityApiTest)
      printf '%q --no-daemon --init-script %q ' "$gradle74" "$work_root/logback-jacoco.init.gradle" \
        >"$coverage_dir/command.txt"
      printf '%q ' "${coverage_command[@]}" >>"$coverage_dir/command.txt"
      printf '\n' >>"$coverage_dir/command.txt"
      set +e
      (
        cd "$consumer" || exit 125
        GRADLE_USER_HOME="$work_root/gradle-home" JAVA_HOME="$java17_home" \
          timeout --signal=TERM 60m "$gradle74" --no-daemon \
          --init-script "$work_root/logback-jacoco.init.gradle" "${coverage_command[@]}"
      ) >"$coverage_dir/test.log" 2>&1
      coverage_exit=$?
      set -e
      ;;
    kompendium)
      printf '%q --no-daemon :kompendium-core:cleanTest :kompendium-core:test\n' \
        "$gradle75" >"$coverage_dir/command.txt"
      set +e
      (
        cd "$consumer" || exit 125
        GRADLE_USER_HOME="$work_root/gradle-home" JAVA_HOME="$java11_home" \
          timeout --signal=TERM 60m "$gradle75" --no-daemon \
          :kompendium-core:cleanTest :kompendium-core:test
      ) >"$coverage_dir/test.log" 2>&1
      coverage_exit=$?
      set -e
      if [[ $coverage_exit -eq 0 ]]; then
        cp "$consumer/core/build/kover/test.exec" "$exec_file"
      fi
      ;;
  esac
  printf '%s\n' "$coverage_exit" >"$coverage_dir/exit-code.txt"

  if [[ $coverage_exit -ne 0 || ! -s $exec_file ]]; then
    unexpected=$((unexpected + 1))
    printf '%s\t%s\t0\t0\t0\t0\t0\tfalse\n' "$repo" "${exec_file:+0}" \
      >>"$result_dir/coverage-results.tsv"
    continue
  fi
  java -jar "$cli" report "$exec_file" --classfiles "$classic_jar" --classfiles "$core_jar" \
    --xml "$coverage_dir/logback.xml" --csv "$coverage_dir/logback.csv" \
    >"$coverage_dir/report.log" 2>&1

  line_covered() {
    local package=$1 source=$2 line=$3 xml=$4
    local covered
    covered=$(xmllint --xpath "/report/package[@name='$package']/sourcefile[@name='$source']/line[@nr='$line']/@ci" \
      "$xml" 2>/dev/null | sed -n 's/.*ci="\([0-9][0-9]*\)".*/\1/p')
    printf '%s\n' "${covered:-0}"
  }
  context81=$(line_covered ch/qos/logback/classic/util ContextInitializer.java 81 "$coverage_dir/logback.xml")
  context82=$(line_covered ch/qos/logback/classic/util ContextInitializer.java 82 "$coverage_dir/logback.xml")
  env36=$(line_covered ch/qos/logback/core/util EnvUtil.java 36 "$coverage_dir/logback.xml")
  env56=$(line_covered ch/qos/logback/core/util EnvUtil.java 56 "$coverage_dir/logback.xml")
  env60=$(line_covered ch/qos/logback/core/util EnvUtil.java 60 "$coverage_dir/logback.xml")
  semantic_hit=false
  if [[ $context81 -gt 0 && $context82 -gt 0 && $env36 -gt 0 && $env56 -gt 0 && $env60 -gt 0 ]]; then
    semantic_hit=true
  else
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$repo" "$(stat -c %s "$exec_file")" "$context81" "$context82" "$env36" \
    "$env56" "$env60" "$semantic_hit" >>"$result_dir/coverage-results.tsv"
  rm "$coverage_dir/logback.xml"
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$result_dir/environment.txt"

exit "$unexpected"
