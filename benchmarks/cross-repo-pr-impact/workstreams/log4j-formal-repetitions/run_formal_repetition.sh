#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[123]$ ]]; then
  echo "用法：$0 <重复编号：1、2 或 3>" >&2
  exit 2
fi

repeat=$1
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
benchmark_root=$(cd "$script_dir/../.." && pwd)
repo_root=$(cd "$benchmark_root/../.." && pwd)
result_root="$benchmark_root/results/log4j-formal-repetitions-2026-08-25"
repeat_dir="$result_root/repeat-$repeat"

if [[ -e $repeat_dir ]]; then
  echo "拒绝覆盖已有 Log4j 正式重复目录：$repeat_dir" >&2
  exit 3
fi

export JAVA_HOME=${LOG4J_FORMAL_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
m2_seed=${LOG4J_FORMAL_M2_SEED:-$HOME/.m2/repository}

for path in "$JAVA_HOME/bin/java" "$m2_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少正式重复输入：$path" >&2
    exit 4
  fi
done

work_base="$repo_root/.work/log4j-formal"
mkdir -p "$work_base"
work_root=$(mktemp -d "$work_base/repeat-${repeat}.XXXXXX")
mkdir -p "$repeat_dir/runs" "$work_root/mirrors" "$work_root/consumers" "$work_root/m2"
mkdir -p "$work_root/tmp" "$work_root/java-tmp"
export TMPDIR="$work_root/tmp"
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$work_root/java-tmp"
maven_settings="$work_root/settings.xml"
seed_uri="file://$(readlink -f "$m2_seed")"
sed "s|@SEED_URI@|$seed_uri|g" "$script_dir/maven-seed-settings.xml" >"$maven_settings"

repos=(neqsim archifacts elimu powertools)
configs=(a0 a1 a2 a3-before a3-after)

declare -A source=(
  [neqsim]="${LOG4J_FORMAL_NEQSIM_SOURCE:-https://github.com/equinor/neqsim.git}"
  [archifacts]="${LOG4J_FORMAL_ARCHIFACTS_SOURCE:-https://github.com/archifacts/archifacts.git}"
  [elimu]="${LOG4J_FORMAL_ELIMU_SOURCE:-https://github.com/elimu-ai/webapp.git}"
  [powertools]="${LOG4J_FORMAL_POWERTOOLS_SOURCE:-https://github.com/aws-powertools/powertools-lambda-java.git}"
)
declare -A baseline=(
  [neqsim]=6cea014aecf9ca0956bb402bce2ed18e803b9b4b
  [archifacts]=157a8962a1934c346ae09849db69e3d603df6b6c
  [elimu]=460e263ec22d4768e1b6f171795eef20e4ace80a
  [powertools]=0184106b997ba587a33a5ac09a669ad33c3aa6b5
)
declare -A neqsim_commit=(
  [a0]=6cea014aecf9ca0956bb402bce2ed18e803b9b4b
  [a1]=e23721cb00132a55b32efcbd6fc6b382fb60e959
  [a2]=d622943718685b394364d36d5af61474cf881339
  [a3-before]=6cea014aecf9ca0956bb402bce2ed18e803b9b4b
  [a3-after]=6cea014aecf9ca0956bb402bce2ed18e803b9b4b
)
declare -A aligned_version=(
  [a0]=2.17.2
  [a1]=2.18.0
  [a2]=2.18.0
  [a3-before]=2.17.1
  [a3-after]=2.17.2
)
declare -A expected_tests=(
  [neqsim-pass]=180
  [neqsim-fail]=134
  [archifacts-pass]=92
  [elimu-pass]=122
  [powertools-pass]=3
)

{
  printf 'repeat=%s\n' "$repeat"
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'java_home=%s\n' "$JAVA_HOME"
  printf 'maven_seed=%s\n' "$seed_uri"
  printf 'maven_isolation=one initially empty writable local repository per arm\n'
  printf 'tmpdir=%s\n' "$TMPDIR"
  printf 'java_io_tmpdir=%s\n' "$work_root/java-tmp"
  java -version 2>&1
  mvn -version
  uname -a
} >"$repeat_dir/environment.txt"

printf 'repeat\tconfig\trepository\tcommit\texpected_api\texpected_core\tresolved_api\tresolved_core\texpected_result\texit_code\ttest_count\texpected_test_count\tfailure_signature_ok\tversion_ok\tdirection_ok\tduration_seconds\n' \
  >"$repeat_dir/run-results.tsv"

for repo in "${repos[@]}"; do
  git clone --mirror --quiet --no-hardlinks "${source[$repo]}" "$work_root/mirrors/$repo.git"
  git --git-dir="$work_root/mirrors/$repo.git" cat-file -e "${baseline[$repo]}^{commit}"
done
for commit in "${neqsim_commit[@]}"; do
  git --git-dir="$work_root/mirrors/neqsim.git" cat-file -e "$commit^{commit}"
done

for config in "${configs[@]}"; do
  mkdir -p "$work_root/m2/$config"
done

set_direct_log4j_version() {
  local consumer=$1
  local local_repo=$2
  local version=$3
  local artifact
  local actual
  for artifact in log4j-api log4j-core; do
    mvn -q -s "$maven_settings" -f "$consumer/pom.xml" "-Dmaven.repo.local=$local_repo" \
      org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
      "-Dincludes=org.apache.logging.log4j:$artifact" \
      "-DdepVersion=$version" -DforceVersion=true -DgenerateBackupPoms=false
    actual=$(xmllint --xpath \
      "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='$artifact']/*[local-name()='version'])" \
      "$consumer/pom.xml")
    if [[ $actual != "$version" ]]; then
      echo "Log4j 版本合成失败：$consumer $artifact 期望 $version，实际 ${actual:-<空>}" >&2
      return 1
    fi
  done
}

set_archifacts_log4j_version() {
  local consumer=$1
  local local_repo=$2
  local version=$3
  mvn -q -s "$maven_settings" -f "$consumer/pom.xml" "-Dmaven.repo.local=$local_repo" \
    org.codehaus.mojo:versions-maven-plugin:2.16.2:set-property \
    -Dproperty=log4j.version "-DnewVersion=$version" -DgenerateBackupPoms=false
}

resolved_version() {
  local artifact=$1
  local dependency_log=$2
  sed $'s/\\033\\[[0-9;]*m//g' "$dependency_log" | \
    awk -v artifact="$artifact" '
      index($0, "org.apache.logging.log4j:" artifact ":jar:") {
        line=$0
        sub(/^.*org.apache.logging.log4j:/, "", line)
        count=split(line, fields, ":")
        if (count >= 3) versions[fields[3]]=1
      }
      END {
        separator=""
        for (version in versions) {
          printf "%s%s", separator, version
          separator=","
        }
        printf "\n"
      }
    '
}

unexpected=0
for config in "${configs[@]}"; do
  for repo in "${repos[@]}"; do
    local_repo="$work_root/m2/$config"
    consumer="$work_root/consumers/$config/$repo"
    run_dir="$repeat_dir/runs/$config/$repo"
    mkdir -p "$run_dir/reports"
    git clone --quiet "$work_root/mirrors/$repo.git" "$consumer"

    checkout_commit=${baseline[$repo]}
    if [[ $repo == neqsim ]]; then
      checkout_commit=${neqsim_commit[$config]}
    fi
    git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "$checkout_commit"

    expected_api=${aligned_version[$config]}
    expected_core=${aligned_version[$config]}
    extra_args=()
    if [[ $repo == neqsim && $config == a1 ]]; then
      expected_api=2.17.2
      expected_core=2.18.0
    elif [[ $repo == neqsim ]]; then
      if [[ $config == a3-before ]]; then
        set_direct_log4j_version "$consumer" "$local_repo" 2.17.1
      fi
    elif [[ $repo == archifacts ]]; then
      set_archifacts_log4j_version "$consumer" "$local_repo" "${aligned_version[$config]}"
    elif [[ $repo == elimu ]]; then
      set_direct_log4j_version "$consumer" "$local_repo" "${aligned_version[$config]}"
    else
      extra_args=("-Dlog4j.version=${aligned_version[$config]}" -Daws.sdk.version=2.17.223)
    fi

    git -C "$consumer" rev-parse HEAD >"$run_dir/consumer-commit.txt"
    git -C "$consumer" status --short >"$run_dir/git-status.txt"
    if [[ $checkout_commit == "${baseline[$repo]}" ]]; then
      git -C "$consumer" diff >"$run_dir/input.diff"
    else
      git -C "$consumer" diff "${baseline[$repo]}".."$checkout_commit" >"$run_dir/input.diff"
    fi
    {
      printf 'expected_api=%s\n' "$expected_api"
      printf 'expected_core=%s\n' "$expected_core"
      if [[ $repo == powertools ]]; then
        printf 'aws_sdk_version=2.17.223\n'
        printf 'command_property=%s\n' "${extra_args[@]}"
      fi
    } >"$run_dir/input.properties"

    dependency_command=(mvn -s "$maven_settings" "-Dmaven.repo.local=$local_repo" -Dstyle.color=never -B -ntp)
    if [[ $repo == powertools ]]; then
      dependency_command+=(-pl powertools-logging dependency:tree \
        -Dincludes=org.apache.logging.log4j:log4j-api,org.apache.logging.log4j:log4j-core)
    else
      dependency_command+=(dependency:tree \
        -Dincludes=org.apache.logging.log4j:log4j-api,org.apache.logging.log4j:log4j-core)
    fi
    dependency_command+=("${extra_args[@]}")
    (
      cd "$consumer" || exit 125
      timeout --signal=TERM 30m "${dependency_command[@]}"
    ) >"$run_dir/dependency-tree.log" 2>&1
    resolved_api=$(resolved_version log4j-api "$run_dir/dependency-tree.log")
    resolved_core=$(resolved_version log4j-core "$run_dir/dependency-tree.log")

    if [[ $repo == powertools ]]; then
      command=(mvn -s "$maven_settings" "-Dmaven.repo.local=$local_repo" -B -ntp \
        -pl powertools-logging -am clean test \
        -Dtest=org.apache.logging.log4j.core.layout.LambdaJsonLayoutTest \
        -Dsurefire.failIfNoSpecifiedTests=false "${extra_args[@]}")
    else
      command=(mvn -s "$maven_settings" "-Dmaven.repo.local=$local_repo" -B -ntp clean test -DskipTests=false)
    fi
    {
      printf 'timeout --signal=TERM 60m'
      printf ' %q' "${command[@]}"
      printf '\n'
    } >"$run_dir/command.txt"

    started_epoch=$(date +%s)
    set +e
    (
      cd "$consumer" || exit 125
      timeout --signal=TERM 60m "${command[@]}"
    ) >"$run_dir/test.log" 2>&1
    exit_code=$?
    set -e
    duration_seconds=$(($(date +%s) - started_epoch))
    printf '%s\n' "$exit_code" >"$run_dir/exit-code.txt"

    test_count=0
    if [[ $repo == powertools ]]; then
      report="$consumer/powertools-logging/target/surefire-reports/TEST-org.apache.logging.log4j.core.layout.LambdaJsonLayoutTest.xml"
      if [[ -f $report ]]; then
        cp "$report" "$run_dir/reports/"
        test_count=$(xmllint --xpath 'string(/testsuite/@tests)' "$report")
      fi
    else
      while IFS= read -r -d '' report; do
        count=$(xmllint --xpath 'string(/testsuite/@tests)' "$report" 2>/dev/null || printf '0')
        if [[ $count =~ ^[0-9]+$ ]]; then
          test_count=$((test_count + count))
        fi
        cp --parents "$report" "$run_dir/reports" 2>/dev/null || true
      done < <(find "$consumer" -type f -path '*/surefire-reports/TEST-*.xml' -print0)
    fi

    expected_result=pass
    expected_test_count=${expected_tests[$repo-pass]}
    failure_signature_ok=true
    if [[ $repo == neqsim && $config == a1 ]]; then
      expected_result=fail
      expected_test_count=${expected_tests[neqsim-fail]}
      failure_signature_ok=false
      if rg -q 'NoClassDefFoundError: org/apache/logging/log4j/util/ServiceLoaderUtil' "$run_dir/test.log"; then
        failure_signature_ok=true
      fi
    fi

    version_ok=false
    if [[ $resolved_api == "$expected_api" && $resolved_core == "$expected_core" ]]; then
      version_ok=true
    fi
    direction_ok=false
    if [[ $expected_result == pass && $exit_code -eq 0 && $test_count -eq $expected_test_count ]]; then
      direction_ok=true
    elif [[ $expected_result == fail && $exit_code -ne 0 && $test_count -eq $expected_test_count && $failure_signature_ok == true ]]; then
      direction_ok=true
    fi
    if [[ $version_ok != true || $direction_ok != true ]]; then
      unexpected=$((unexpected + 1))
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$repeat" "$config" "$repo" "$checkout_commit" "$expected_api" "$expected_core" \
      "$resolved_api" "$resolved_core" "$expected_result" "$exit_code" "$test_count" \
      "$expected_test_count" "$failure_signature_ok" "$version_ok" "$direction_ok" \
      "$duration_seconds" >>"$repeat_dir/run-results.tsv"
    printf 'repeat=%s config=%s repo=%s versions=%s/%s exit=%s tests=%s direction=%s\n' \
      "$repeat" "$config" "$repo" "$resolved_api" "$resolved_core" "$exit_code" \
      "$test_count" "$direction_ok"
  done
done

printf 'repository\ta1_a2_same_input\ta0_a3_after_same_input\n' >"$repeat_dir/input-parity.tsv"
for repo in archifacts elimu powertools; do
  a1_a2=false
  a0_a3=false
  if cmp -s "$repeat_dir/runs/a1/$repo/input.diff" "$repeat_dir/runs/a2/$repo/input.diff" \
    && cmp -s "$repeat_dir/runs/a1/$repo/input.properties" "$repeat_dir/runs/a2/$repo/input.properties"; then
    a1_a2=true
  fi
  if cmp -s "$repeat_dir/runs/a0/$repo/input.diff" "$repeat_dir/runs/a3-after/$repo/input.diff" \
    && cmp -s "$repeat_dir/runs/a0/$repo/input.properties" "$repeat_dir/runs/a3-after/$repo/input.properties"; then
    a0_a3=true
  fi
  if [[ $a1_a2 != true || $a0_a3 != true ]]; then
    unexpected=$((unexpected + 1))
  fi
  printf '%s\t%s\t%s\n' "$repo" "$a1_a2" "$a0_a3" >>"$repeat_dir/input-parity.tsv"
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$repeat_dir/environment.txt"

exit "$unexpected"
