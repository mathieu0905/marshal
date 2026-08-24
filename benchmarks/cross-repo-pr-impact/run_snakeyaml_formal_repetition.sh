#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[123]$ ]]; then
  echo "用法：$0 <重复编号：1、2 或 3>" >&2
  exit 2
fi

repeat=$1
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
work_parent=${MARSHAL_WORK_ROOT:-$repo_root/.work/cross-repo-pr-impact}
result_root="$script_dir/results/snakeyaml-formal-repetitions-2026-08-24"
repeat_dir="$result_root/repeat-$repeat"
input_dir="$result_root/inputs"

# 正式运行日志不可由同编号重跑覆盖；Git 不能恢复这些生成证据。
if [[ -e $repeat_dir ]]; then
  echo "拒绝覆盖已有正式重复目录：$repeat_dir" >&2
  exit 3
fi

export JAVA_HOME=${SNAKEYAML_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
gradle_bin=${SNAKEYAML_GRADLE_BIN:-$work_parent/tooling/gradle-7.2/bin/gradle}
m2_seed=${SNAKEYAML_M2_SEED:-$HOME/.m2/repository}
coursier_seed=${SNAKEYAML_COURSIER_SEED:-$HOME/.cache/coursier}
ivy_seed=${SNAKEYAML_IVY_SEED:-$HOME/.ivy2}
sbt_seed=${SNAKEYAML_SBT_SEED:-$HOME/.sbt}
gradle_seed=${SNAKEYAML_GRADLE_SEED:-$HOME/.gradle}

for path in "$JAVA_HOME" "$gradle_bin" "$m2_seed" "$coursier_seed" "$ivy_seed" "$sbt_seed" "$gradle_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少正式重复所需输入：$path" >&2
    exit 4
  fi
done

mkdir -p "$work_parent"
work_root=$(mktemp -d "$work_parent/marshal-snakeyaml-formal-r${repeat}.XXXXXX")
mkdir -p "$repeat_dir/runs" "$work_root/mirrors" "$work_root/consumers" \
  "$work_root/caches/m2" "$work_root/caches/sbt" "$work_root/caches/gradle" \
  "$work_root/tmp" "$work_root/java-tmp"
export TMPDIR="$work_root/tmp"
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$work_root/java-tmp"

repos=(jclouds zio xlate xvik)
configs=(a0 a1 a2 a3-before a3-after)

declare -A source=(
  [jclouds]="${SNAKEYAML_JCLOUDS_SEED:-https://github.com/apache/jclouds.git}"
  [zio]="${SNAKEYAML_ZIO_SEED:-https://github.com/zio/zio-json.git}"
  [xlate]="${SNAKEYAML_XLATE_SEED:-https://github.com/xlate/yaml-json.git}"
  [xvik]="${SNAKEYAML_XVIK_SEED:-https://github.com/xvik/yaml-updater.git}"
)
declare -A baseline=(
  [jclouds]=788f75f9379287e70a2e2197297cb0efd45f96f7
  [zio]=716a08ddb1c503f25cfd664cbc24502cbc46c09c
  [xlate]=ce9f3933c975dd33ecd3d285ccb81898f5dcdf57
  [xvik]=bfa3fd754e97c58ea132f46ddc00d83811fd6724
)
declare -A repair=(
  [jclouds]=dafa59d61fd0bafc17b941df8fb12159463ccf71
  [zio]=b895d3148e8ce3dded7c15de1bdc62eb3a3f2681
)
declare -A version=(
  [a0]=1.32
  [a1]=2.0
  [a2]=2.0
  [a3-before]=1.31
  [a3-after]=1.32
)

{
  printf 'repeat=%s\n' "$repeat"
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'java_home=%s\n' "$JAVA_HOME"
  printf 'gradle=%s\n' "$gradle_bin"
  java -version 2>&1
  mvn -version
  "$gradle_bin" --version
  uname -a
} >"$repeat_dir/environment.txt"

printf 'repeat\tconfig\trepository\texpected_version\tactual_version\texpected_result\tstarted_at\tfinished_at\tduration_seconds\texit_code\ttest_executed\tfailure_signature_ok\tversion_ok\tdirection_ok\n' \
  >"$repeat_dir/run-results.tsv"

for repo in "${repos[@]}"; do
  git clone --mirror --quiet --no-hardlinks "${source[$repo]}" "$work_root/mirrors/$repo.git"
  git --git-dir="$work_root/mirrors/$repo.git" cat-file -e "${baseline[$repo]}^{commit}"
  if [[ -n ${repair[$repo]:-} ]]; then
    git --git-dir="$work_root/mirrors/$repo.git" cat-file -e "${repair[$repo]}^{commit}"
  fi
done

for config in "${configs[@]}"; do
  mkdir -p "$work_root/caches/m2/$config" \
    "$work_root/caches/sbt/$config/coursier" \
    "$work_root/caches/sbt/$config/ivy2" \
    "$work_root/caches/sbt/$config/global" \
    "$work_root/caches/gradle/$config"
  cp -a --reflink=auto "$m2_seed/." "$work_root/caches/m2/$config/"
  cp -a --reflink=auto "$coursier_seed/." "$work_root/caches/sbt/$config/coursier/"
  cp -a --reflink=auto "$ivy_seed/." "$work_root/caches/sbt/$config/ivy2/"
  cp -a --reflink=auto "$sbt_seed/." "$work_root/caches/sbt/$config/global/"
  cp -a --reflink=auto "$gradle_seed/." "$work_root/caches/gradle/$config/"
done

unexpected=0
for config in "${configs[@]}"; do
  expected_version=${version[$config]}

  for repo in "${repos[@]}"; do
    consumer="$work_root/consumers/$config/$repo"
    run_dir="$repeat_dir/runs/$config/$repo"
    mkdir -p "$run_dir/reports"
    git clone --quiet "$work_root/mirrors/$repo.git" "$consumer"

    checkout_commit=${baseline[$repo]}
    if [[ $config == a2 && -n ${repair[$repo]:-} ]]; then
      checkout_commit=${repair[$repo]}
    fi
    git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "$checkout_commit"

    if [[ ! ($repo == jclouds && ($config == a0 || $config == a3-after)) \
       && ! ($repo == jclouds && $config == a2) \
       && ! ($repo == zio && $config == a2) ]]; then
      git -C "$consumer" apply "$input_dir/$repo-to-$expected_version.patch"
    fi

    git -C "$consumer" rev-parse HEAD >"$run_dir/consumer-commit.txt"
    git -C "$consumer" status --short >"$run_dir/git-status.txt"
    if [[ $checkout_commit == "${baseline[$repo]}" ]]; then
      git -C "$consumer" diff >"$run_dir/input.diff"
    else
      git -C "$consumer" diff "${baseline[$repo]}".."$checkout_commit" >"$run_dir/input.diff"
    fi

    case $repo in
      jclouds)
        actual_version=$(sed -n '/<artifactId>snakeyaml<\/artifactId>/{n;s/.*<version>\([^<]*\)<\/version>.*/\1/p;q;}' "$consumer/apis/byon/pom.xml")
        command=(mvn "-Dmaven.repo.local=$work_root/caches/m2/$config" -B -ntp -pl apis/byon -am clean test -DskipTests=false)
        ;;
      zio)
        actual_version=$(sed -n 's/.*"org.yaml" % "snakeyaml" *% "\([^"]*\)".*/\1/p' "$consumer/build.sbt")
        command=(./sbt -batch zioJsonYaml/clean zioJsonYaml/test)
        ;;
      xlate)
        actual_version=$(sed -n 's/.*<version.snakeyaml>\([^<]*\)<\/version.snakeyaml>.*/\1/p' "$consumer/pom.xml")
        command=(mvn "-Dmaven.repo.local=$work_root/caches/m2/$config" -B -ntp clean test -DskipTests=false)
        ;;
      xvik)
        actual_version=$(sed -n "s/.*org.yaml:snakeyaml:\([^']*\).*/\1/p" "$consumer/yaml-config-updater/build.gradle")
        command=("$gradle_bin" :yaml-config-updater:clean :yaml-config-updater:test --no-daemon)
        ;;
    esac

    expected_result=pass
    if [[ $config == a1 && ($repo == jclouds || $repo == zio) ]]; then
      expected_result=fail
    fi
    {
      printf 'timeout --signal=TERM 45m'
      printf ' %q' "${command[@]}"
      printf '\n'
    } >"$run_dir/command.txt"

    started_at=$(date --iso-8601=seconds)
    started_epoch=$(date +%s)
    set +e
    (
      cd "$consumer" || exit 125
      if [[ $repo == zio ]]; then
        export COURSIER_CACHE="$work_root/caches/sbt/$config/coursier"
        export SBT_IVY_HOME="$work_root/caches/sbt/$config/ivy2"
        export SBT_GLOBAL_BASE="$work_root/caches/sbt/$config/global"
        export SBT_OPTS="-Dsbt.global.base=$SBT_GLOBAL_BASE -Dsbt.ivy.home=$SBT_IVY_HOME -Dsbt.boot.directory=$SBT_GLOBAL_BASE/boot"
      elif [[ $repo == xvik ]]; then
        export GRADLE_USER_HOME="$work_root/caches/gradle/$config"
      fi
      timeout --signal=TERM 45m "${command[@]}"
    ) >"$run_dir/build.log" 2>&1
    exit_code=$?
    set -e
    finished_epoch=$(date +%s)
    finished_at=$(date --iso-8601=seconds)
    duration_seconds=$((finished_epoch - started_epoch))
    printf '%s\n' "$exit_code" >"$run_dir/exit-code.txt"

    (
      cd "$consumer" || exit 0
      find . -type f \
        \( -path '*/surefire-reports/*' \
        -o -path '*/test-results/*' \
        -o -path '*/test-reports/*' \) \
        -exec cp --parents {} "$run_dir/reports" \; 2>/dev/null || true
    )

    test_executed=false
    failure_signature_ok=true
    case $repo in
      jclouds)
        if [[ $expected_result == fail ]]; then
          failure_signature_ok=false
          if rg -q 'cannot be converted to org.yaml.snakeyaml.LoaderOptions' "$run_dir/build.log"; then
            failure_signature_ok=true
          fi
        elif rg -q 'Tests run: 31, Failures: 0, Errors: 0, Skipped: 0' "$run_dir/build.log"; then
          test_executed=true
        fi
        ;;
      zio)
        if [[ $expected_result == fail ]]; then
          failure_signature_ok=false
          if rg -q 'not enough arguments for constructor SafeConstructor|Unspecified value parameter' "$run_dir/build.log"; then
            failure_signature_ok=true
          fi
        elif rg -q '16 tests passed\. 0 tests failed\. 0 tests ignored\.' "$run_dir/build.log"; then
          test_executed=true
        fi
        ;;
      xlate)
        if rg -q 'Tests run: 78, Failures: 0, Errors: 0' "$run_dir/build.log" \
          && [[ $(rg -c 'Tests run: 60, Failures: 0, Errors: 0' "$run_dir/build.log") -ge 2 ]]; then
          test_executed=true
        fi
        ;;
      xvik)
        suites=0
        tests=0
        for report in "$consumer"/yaml-config-updater/build/test-results/test/TEST-*.xml; do
          [[ -e $report ]] || continue
          suites=$((suites + 1))
          count=$(xmllint --xpath 'string(/testsuite/@tests)' "$report")
          tests=$((tests + count))
        done
        printf 'suites=%s\ntests=%s\n' "$suites" "$tests" >"$run_dir/test-counts.txt"
        if [[ $suites -eq 33 && $tests -eq 146 ]]; then
          test_executed=true
        fi
        ;;
    esac

    version_ok=false
    if [[ $actual_version == "$expected_version" ]]; then
      version_ok=true
    fi
    direction_ok=false
    if [[ $expected_result == pass && $exit_code -eq 0 && $test_executed == true ]]; then
      direction_ok=true
    elif [[ $expected_result == fail && $exit_code -ne 0 && $failure_signature_ok == true ]]; then
      direction_ok=true
    fi
    if [[ $version_ok != true || $direction_ok != true ]]; then
      unexpected=$((unexpected + 1))
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$repeat" "$config" "$repo" "$expected_version" "$actual_version" \
      "$expected_result" "$started_at" "$finished_at" "$duration_seconds" \
      "$exit_code" "$test_executed" "$failure_signature_ok" "$version_ok" \
      "$direction_ok" >>"$repeat_dir/run-results.tsv"
    printf '%s %s: exit=%s version=%s tests=%s direction=%s\n' \
      "$config" "$repo" "$exit_code" "$actual_version" "$test_executed" "$direction_ok"
  done
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$repeat_dir/environment.txt"

exit "$unexpected"
