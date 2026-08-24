#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
benchmark_root=$(cd "$script_dir/../.." && pwd)
repository_root=$(git -C "$script_dir" rev-parse --show-toplevel)
result_root=$(realpath -m "${RESULT_ROOT:-$benchmark_root/results/slf4j-rabbit-contract-formal-repetitions-2026-08-25}")
repository=${SLF4J_RABBIT_SOURCE:-https://github.com/rabbitmq/rabbitmq-jms-client.git}
contract_source="$script_dir/../slf4j-fourth-root/LoggingProviderCompatibilityTest.java"
java_home=${SLF4J_RABBIT_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
m2_seed=${SLF4J_RABBIT_M2_SEED:-}
allowed_work_root=$(realpath -m "$repository_root/.work/slf4j-rabbit")
work_parent=$(realpath -m "${SLF4J_RABBIT_WORK_PARENT:-$allowed_work_root}")

require_project_work_path() {
  local path
  path=$(realpath -m "$1")
  if [[ $path != "$allowed_work_root" && $path != "$allowed_work_root/"* ]]; then
    echo "RabbitMQ 工作路径必须位于 $allowed_work_root：$path" >&2
    exit 4
  fi
}

if [[ $result_root != "$repository_root/"* ]]; then
  echo "RabbitMQ 结果目录必须位于仓库根 $repository_root：$result_root" >&2
  exit 4
fi

declare -A commit=(
  [A0]=41b2abf72827e123c8c472d3f07b30ac3bc24be0
  [A1]=4fa8b7fea9971db148c98a5a3816a3c850332a92
  [A2]=c2695a908a60b5c3db041afa193399cceb18f10c
)
declare -A expected_api=([A0]=1.7.36 [A1]=2.0.0 [A2]=2.0.0)
declare -A expected_classic=([A0]=1.2.11 [A1]=1.2.11 [A2]=1.4.0)
declare -A expected_core=([A0]=1.2.11 [A1]=1.2.11 [A2]=1.4.0)

if [[ -e $result_root ]]; then
  echo "拒绝覆盖已有 RabbitMQ 正式重复目录：$result_root" >&2
  exit 3
fi
for path in "$contract_source" "$java_home/bin/java"; do
  if [[ ! -e $path ]]; then
    echo "缺少正式重复输入：$path" >&2
    exit 4
  fi
done
require_project_work_path "$work_parent"
if [[ -n $m2_seed ]]; then
  m2_seed=$(realpath -m "$m2_seed")
  require_project_work_path "$m2_seed"
  if [[ ! -d $m2_seed ]]; then
    echo "指定的 Maven 小型种子不存在：$m2_seed" >&2
    exit 4
  fi
fi

mkdir -p "$work_parent"
work_root=$(mktemp -d "$work_parent/slf4j-rabbit-formal.XXXXXX")
java_tmp="$work_root/java-tmp"
mkdir -p "$result_root" "$work_root/m2" "$java_tmp"

export JAVA_HOME=$java_home
export PATH="$JAVA_HOME/bin:$PATH"
export TMPDIR=$java_tmp
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:+$JAVA_TOOL_OPTIONS }-Djava.io.tmpdir=$java_tmp"

git clone --mirror --quiet "$repository" "$work_root/repository.git"
for arm in A0 A1 A2; do
  git --git-dir="$work_root/repository.git" cat-file -e "${commit[$arm]}^{commit}"
done

seed_policy=provided_project_seed
if [[ -z $m2_seed ]]; then
  seed_policy=project_local_dependency_go_offline
  m2_seed="$work_root/m2-seed"
  seed_checkout="$work_root/seed-checkout"
  mkdir -p "$m2_seed"
  git clone --quiet "$work_root/repository.git" "$seed_checkout"
  : >"$result_root/seed-preparation.log"
  for arm in A0 A1 A2; do
    git -c advice.detachedHead=false -C "$seed_checkout" checkout --detach --force --quiet "${commit[$arm]}"
    printf 'arm=%s mvn -Dmaven.repo.local=%q -B -ntp dependency:go-offline\n' \
      "$arm" "$m2_seed" >>"$result_root/seed-preparation-command.txt"
    set +e
    (
      cd "$seed_checkout" || exit 125
      mvn "-Dmaven.repo.local=$m2_seed" -B -ntp dependency:go-offline
    ) >>"$result_root/seed-preparation.log" 2>&1
    seed_exit=$?
    set -e
    printf '%s\t%s\n' "$arm" "$seed_exit" >>"$result_root/seed-preparation-exit-codes.tsv"
    if [[ $seed_exit -ne 0 ]]; then
      echo "RabbitMQ $arm 的项目内依赖种子准备失败，见 $result_root/seed-preparation.log" >&2
      exit 7
    fi
  done
fi

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'repository=%s\n' "$repository"
  printf 'contract_source=%s\n' "$contract_source"
  printf 'java_home=%s\n' "$JAVA_HOME"
  printf 'java_tmp=%s\n' "$java_tmp"
  printf 'maven_seed=%s\n' "$m2_seed"
  printf 'maven_seed_policy=%s\n' "$seed_policy"
  java -version 2>&1
  mvn -version
  printf 'repeat_count=3\n'
  printf 'checkout_policy=fresh checkout for every repeat and arm\n'
  printf 'maven_repository_policy=one project-local small-seed copy per repeat and arm\n'
  printf 'test_command=mvn -B -ntp clean test\n'
} >"$result_root/environment.txt"

git --git-dir="$work_root/repository.git" diff "${commit[A0]}" "${commit[A1]}" \
  >"$result_root/source-upgrade.patch"
git --git-dir="$work_root/repository.git" diff "${commit[A1]}" "${commit[A2]}" \
  >"$result_root/maintainer-repair.patch"
git --git-dir="$work_root/repository.git" show --format=fuller --stat \
  7075e98c50a70e05cd3e4890fd49d7afe2ec9aa0 >"$result_root/later-strategy-reversion.txt"

printf 'repeat\tarm\tcommit\ttree\texpected_api\tactual_api\texpected_classic\tactual_classic\texpected_core\tactual_core\tdependency_exit\ttest_exit\ttests\tfailures\terrors\tskipped\tfailing_suites\tnop_signature\tunique_failure_ok\tdirection_ok\tduration_seconds\n' \
  >"$result_root/run-results.tsv"

unexpected=0
for repeat in 1 2 3; do
  repeat_dir="$result_root/repeat-$repeat"
  mkdir -p "$repeat_dir"

  for arm in A0 A1 A2; do
    checkout="$work_root/checkouts/repeat-$repeat/$arm"
    run_dir="$repeat_dir/$arm"
    local_repo="$work_root/m2/repeat-$repeat/$arm"
    mkdir -p "$run_dir/reports" "$local_repo"
    cp -a --reflink=auto "$m2_seed/." "$local_repo/"
    git clone --quiet "$work_root/repository.git" "$checkout"
    git -c advice.detachedHead=false -C "$checkout" checkout --detach --quiet "${commit[$arm]}"
    contract_target="$checkout/src/test/java/com/rabbitmq/jms/LoggingProviderCompatibilityTest.java"
    if [[ -e $contract_target ]]; then
      echo "固定合同目标路径已存在：$contract_target" >&2
      exit 5
    fi
    cp "$contract_source" "$contract_target"
    git -C "$checkout" rev-parse HEAD >"$run_dir/commit.txt"
    git -C "$checkout" rev-parse 'HEAD^{tree}' >"$run_dir/tree.txt"
    git -C "$checkout" diff --no-index /dev/null \
      src/test/java/com/rabbitmq/jms/LoggingProviderCompatibilityTest.java \
      >"$run_dir/contract.patch" 2>/dev/null || true
    printf 'mvn -Dmaven.repo.local=%q -B -ntp dependency:tree -Dincludes=org.slf4j:slf4j-api,ch.qos.logback:logback-classic,ch.qos.logback:logback-core\n' \
      "$local_repo" >"$run_dir/dependency-command.txt"
    set +e
    (
      cd "$checkout" || exit 125
      mvn "-Dmaven.repo.local=$local_repo" -B -ntp dependency:tree \
        -Dincludes=org.slf4j:slf4j-api,ch.qos.logback:logback-classic,ch.qos.logback:logback-core
    ) >"$run_dir/dependency-tree.log" 2>&1
    dependency_exit=$?
    set -e

    actual_api=$(sed -n 's/.*org\.slf4j:slf4j-api:jar:\([^:]*\):.*/\1/p' \
      "$run_dir/dependency-tree.log" | head -1)
    actual_classic=$(sed -n 's/.*ch\.qos\.logback:logback-classic:jar:\([^:]*\):.*/\1/p' \
      "$run_dir/dependency-tree.log" | head -1)
    actual_core=$(sed -n 's/.*ch\.qos\.logback:logback-core:jar:\([^:]*\):.*/\1/p' \
      "$run_dir/dependency-tree.log" | head -1)

    printf 'mvn -Dmaven.repo.local=%q -B -ntp clean test\n' "$local_repo" \
      >"$run_dir/test-command.txt"
    started_epoch=$(date +%s)
    set +e
    (
      cd "$checkout" || exit 125
      mvn "-Dmaven.repo.local=$local_repo" -B -ntp clean test
    ) >"$run_dir/maven-test.log" 2>&1
    test_exit=$?
    set -e
    duration_seconds=$(($(date +%s) - started_epoch))
    printf '%s\n' "$dependency_exit" >"$run_dir/dependency-exit-code.txt"
    printf '%s\n' "$test_exit" >"$run_dir/test-exit-code.txt"

    tests=0
    failures=0
    errors=0
    skipped=0
    failing_suites=0
    while IFS= read -r -d '' report; do
      report_tests=$(xmllint --xpath 'string(/testsuite/@tests)' "$report" 2>/dev/null || printf 0)
      report_failures=$(xmllint --xpath 'string(/testsuite/@failures)' "$report" 2>/dev/null || printf 0)
      report_errors=$(xmllint --xpath 'string(/testsuite/@errors)' "$report" 2>/dev/null || printf 0)
      report_skipped=$(xmllint --xpath 'string(/testsuite/@skipped)' "$report" 2>/dev/null || printf 0)
      tests=$((tests + report_tests))
      failures=$((failures + report_failures))
      errors=$((errors + report_errors))
      skipped=$((skipped + report_skipped))
      if [[ $report_failures -gt 0 || $report_errors -gt 0 ]]; then
        failing_suites=$((failing_suites + 1))
      fi
      cp "$report" "$run_dir/reports/"
    done < <(find "$checkout/target/surefire-reports" -maxdepth 1 -type f \
      -name 'TEST-*.xml' -print0 2>/dev/null)

    contract_report="$checkout/target/surefire-reports/TEST-com.rabbitmq.jms.LoggingProviderCompatibilityTest.xml"
    nop_signature=false
    if rg -q 'org\.slf4j\.helpers\.NOPLoggerFactory' "$run_dir/maven-test.log"; then
      nop_signature=true
    fi
    unique_failure_ok=true
    if [[ $arm == A1 ]]; then
      unique_failure_ok=false
      if [[ -f $contract_report && $failures -eq 1 && $errors -eq 0 && $failing_suites -eq 1 && \
            $(xmllint --xpath 'string(/testsuite/@failures)' "$contract_report") -eq 1 && \
            $nop_signature == true ]]; then
        unique_failure_ok=true
      fi
    fi

    version_ok=false
    if [[ $dependency_exit -eq 0 && $actual_api == "${expected_api[$arm]}" && \
          $actual_classic == "${expected_classic[$arm]}" && \
          $actual_core == "${expected_core[$arm]}" ]]; then
      version_ok=true
    fi
    direction_ok=false
    if [[ $arm == A1 ]]; then
      if [[ $test_exit -ne 0 && $tests -eq 115 && $unique_failure_ok == true && $version_ok == true ]]; then
        direction_ok=true
      fi
    elif [[ $test_exit -eq 0 && $tests -eq 115 && $failures -eq 0 && $errors -eq 0 && \
            $version_ok == true ]]; then
      direction_ok=true
    fi
    if [[ $direction_ok != true ]]; then
      unexpected=$((unexpected + 1))
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$repeat" "$arm" "${commit[$arm]}" "$(cat "$run_dir/tree.txt")" \
      "${expected_api[$arm]}" "$actual_api" "${expected_classic[$arm]}" "$actual_classic" \
      "${expected_core[$arm]}" "$actual_core" "$dependency_exit" "$test_exit" "$tests" \
      "$failures" "$errors" "$skipped" "$failing_suites" "$nop_signature" \
      "$unique_failure_ok" "$direction_ok" "$duration_seconds" >>"$result_root/run-results.tsv"
  done
done

{
  printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'unexpected_results=%s\n' "$unexpected"
  printf 'repetition_semantics=stability measurements, not independent semantic reviews\n'
  printf 'later_strategy_boundary=7075e98c50a70e05cd3e4890fd49d7afe2ec9aa0 reverted to the SLF4J 1.7 dependency line one week later\n'
} >>"$result_root/environment.txt"

exit "$unexpected"
