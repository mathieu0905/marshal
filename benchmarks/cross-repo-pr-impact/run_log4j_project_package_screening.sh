#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
work_parent=${MARSHAL_WORK_ROOT:-$repo_root/.work/cross-repo-pr-impact}
result_dir="$script_dir/results/log4j-project-package-screening-2026-08-24"

if [[ -e $result_dir ]]; then
  echo "拒绝覆盖已有筛选目录：$result_dir" >&2
  exit 3
fi

export JAVA_HOME=${LOG4J_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"
m2_seed=${LOG4J_M2_SEED:-$HOME/.m2/repository}

for path in "$JAVA_HOME" "$m2_seed"; do
  if [[ ! -e $path ]]; then
    echo "缺少筛选所需输入：$path" >&2
    exit 4
  fi
done

mkdir -p "$work_parent"
work_root=$(mktemp -d "$work_parent/marshal-log4j-screening.XXXXXX")
mkdir -p "$result_dir/runs" "$work_root/mirrors" "$work_root/consumers" "$work_root/m2" "$work_root/tmp" "$work_root/java-tmp"
export TMPDIR="$work_root/tmp"
export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$work_root/java-tmp"

repos=(apktoolbox neqsim ivymx archifacts)
configs=(a0 a1 a2 a3-before a3-after)

declare -A source=(
  [apktoolbox]="${LOG4J_APKTOOLBOX_SOURCE:-https://github.com/AloysHF/ApkToolBoxGUI.git}"
  [neqsim]="${LOG4J_NEQSIM_SOURCE:-https://github.com/equinor/neqsim.git}"
  [ivymx]="${LOG4J_IVYMX_SOURCE:-https://github.com/axonivy/ivymx.git}"
  [archifacts]="${LOG4J_ARCHIFACTS_SOURCE:-https://github.com/archifacts/archifacts.git}"
)
declare -A baseline=(
  [apktoolbox]=1e69d9e9267d0babf508f1b13a540d8b994b796f
  [neqsim]=6cea014aecf9ca0956bb402bce2ed18e803b9b4b
  [ivymx]=9a42930e9a3182863e1b1b2c2f33c224246a52de
  [archifacts]=157a8962a1934c346ae09849db69e3d603df6b6c
)

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'java_home=%s\n' "$JAVA_HOME"
  java -version 2>&1
  mvn -version
  uname -a
} >"$result_dir/environment.txt"

printf 'config\trepository\texpected_api_version\texpected_core_version\tactual_api_version\tactual_core_version\texpected_result\texit_code\ttest_count\tfailure_signature_ok\tversion_ok\tdirection_ok\tduration_seconds\n' \
  >"$result_dir/run-results.tsv"

for repo in "${repos[@]}"; do
  git clone --mirror --quiet --no-hardlinks "${source[$repo]}" "$work_root/mirrors/$repo.git"
  git --git-dir="$work_root/mirrors/$repo.git" cat-file -e "${baseline[$repo]}^{commit}"
done

cp -a --reflink=auto "$m2_seed/." "$work_root/m2/"

unexpected=0
for config in "${configs[@]}"; do
  for repo in "${repos[@]}"; do
    consumer="$work_root/consumers/$config/$repo"
    run_dir="$result_dir/runs/$config/$repo"
    mkdir -p "$run_dir/reports"
    git clone --quiet "$work_root/mirrors/$repo.git" "$consumer"
    git -c advice.detachedHead=false -C "$consumer" checkout --detach --quiet "${baseline[$repo]}"

    expected_api=2.17.2
    expected_core=2.17.2
    expected_result=pass
    case $config in
      a0|a3-after)
        ;;
      a1)
        expected_core=2.19.0
        if [[ $repo == apktoolbox || $repo == neqsim ]]; then
          expected_result=fail
          mvn -q -f "$consumer/pom.xml" \
            org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
            -Dincludes=org.apache.logging.log4j:log4j-core \
            -DdepVersion=2.19.0 -DforceVersion=true -DgenerateBackupPoms=false
        else
          expected_api=2.19.0
          mvn -q -f "$consumer/pom.xml" \
            org.codehaus.mojo:versions-maven-plugin:2.16.2:set-property \
            -Dproperty=log4j.version -DnewVersion=2.19.0 -DgenerateBackupPoms=false
        fi
        ;;
      a2)
        expected_api=2.19.0
        expected_core=2.19.0
        if [[ $repo == apktoolbox || $repo == neqsim ]]; then
          mvn -q -f "$consumer/pom.xml" \
            org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
            -Dincludes=org.apache.logging.log4j:log4j-api,org.apache.logging.log4j:log4j-core \
            -DdepVersion=2.19.0 -DforceVersion=true -DgenerateBackupPoms=false
        else
          mvn -q -f "$consumer/pom.xml" \
            org.codehaus.mojo:versions-maven-plugin:2.16.2:set-property \
            -Dproperty=log4j.version -DnewVersion=2.19.0 -DgenerateBackupPoms=false
        fi
        ;;
      a3-before)
        expected_api=2.17.1
        expected_core=2.17.1
        if [[ $repo == apktoolbox || $repo == neqsim ]]; then
          mvn -q -f "$consumer/pom.xml" \
            org.codehaus.mojo:versions-maven-plugin:2.16.2:use-dep-version \
            -Dincludes=org.apache.logging.log4j:log4j-api,org.apache.logging.log4j:log4j-core \
            -DdepVersion=2.17.1 -DforceVersion=true -DgenerateBackupPoms=false
        else
          mvn -q -f "$consumer/pom.xml" \
            org.codehaus.mojo:versions-maven-plugin:2.16.2:set-property \
            -Dproperty=log4j.version -DnewVersion=2.17.1 -DgenerateBackupPoms=false
        fi
        ;;
    esac

    if [[ $repo == apktoolbox || $repo == neqsim ]]; then
      actual_api=$(xmllint --xpath \
        "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='log4j-api']/*[local-name()='version'])" \
        "$consumer/pom.xml")
      actual_core=$(xmllint --xpath \
        "string(/*[local-name()='project']/*[local-name()='dependencies']/*[local-name()='dependency'][*[local-name()='groupId']='org.apache.logging.log4j' and *[local-name()='artifactId']='log4j-core']/*[local-name()='version'])" \
        "$consumer/pom.xml")
    else
      property_pom="$consumer/pom.xml"
      if [[ $repo == archifacts ]]; then
        property_pom="$consumer/parent/pom.xml"
      fi
      actual_api=$(xmllint --xpath \
        "string(/*[local-name()='project']/*[local-name()='properties']/*[local-name()='log4j.version'])" \
        "$property_pom")
      actual_core=$actual_api
    fi

    git -C "$consumer" diff >"$run_dir/input.diff"
    git -C "$consumer" status --short >"$run_dir/git-status.txt"
    git -C "$consumer" rev-parse HEAD >"$run_dir/consumer-commit.txt"
    printf 'mvn -Dmaven.repo.local=%q -B -ntp clean test -DskipTests=false\n' \
      "$work_root/m2" >"$run_dir/command.txt"

    started_epoch=$(date +%s)
    set +e
    (
      cd "$consumer" || exit 125
      timeout --signal=TERM 60m mvn \
        "-Dmaven.repo.local=$work_root/m2" \
        -B -ntp clean test -DskipTests=false
    ) >"$run_dir/build.log" 2>&1
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
      cp --parents "$report" "$run_dir/reports" 2>/dev/null || true
    done < <(find "$consumer" -type f -path '*/surefire-reports/TEST-*.xml' -print0)

    failure_signature_ok=true
    if [[ $expected_result == fail ]]; then
      failure_signature_ok=false
      if rg -q 'ThreadContextDataInjector|ServiceLoaderUtil|LoggerContextShutdownAware|NoSuchFieldError|NoClassDefFoundError' \
        "$run_dir/build.log"; then
        failure_signature_ok=true
      fi
    fi

    version_ok=false
    if [[ $actual_api == "$expected_api" && $actual_core == "$expected_core" ]]; then
      version_ok=true
    fi
    direction_ok=false
    if [[ $expected_result == pass && $exit_code -eq 0 && $test_count -gt 0 ]]; then
      direction_ok=true
    elif [[ $expected_result == fail && $exit_code -ne 0 && $failure_signature_ok == true ]]; then
      direction_ok=true
    fi
    if [[ $version_ok != true || $direction_ok != true ]]; then
      unexpected=$((unexpected + 1))
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$config" "$repo" "$expected_api" "$expected_core" "$actual_api" "$actual_core" \
      "$expected_result" "$exit_code" "$test_count" "$failure_signature_ok" "$version_ok" \
      "$direction_ok" "$duration_seconds" >>"$result_dir/run-results.tsv"
    printf '%s %s: exit=%s tests=%s versions=%s/%s direction=%s\n' \
      "$config" "$repo" "$exit_code" "$test_count" "$actual_api" "$actual_core" "$direction_ok"
  done
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
} >>"$result_dir/environment.txt"

exit "$unexpected"
