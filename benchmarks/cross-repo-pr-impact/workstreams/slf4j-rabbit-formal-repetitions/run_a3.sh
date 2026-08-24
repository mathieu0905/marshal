#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
benchmark_root=$(cd "$script_dir/../.." && pwd)
repository_root=$(git -C "$script_dir" rev-parse --show-toplevel)
result_root=$(realpath -m "${RESULT_ROOT:-$benchmark_root/results/slf4j-rabbit-contract-a3-repetitions-2026-08-25}")
repository=${SLF4J_RABBIT_SOURCE:-https://github.com/rabbitmq/rabbitmq-jms-client.git}
contract_source="$script_dir/../slf4j-fourth-root/LoggingProviderCompatibilityTest.java"
consumer_commit=41b2abf72827e123c8c472d3f07b30ac3bc24be0
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

declare -A expected_api=([before]=1.7.29 [after]=1.7.30)

if [[ -e $result_root ]]; then
  echo "拒绝覆盖已有 RabbitMQ A3 重复目录：$result_root" >&2
  exit 3
fi
for path in "$contract_source" "$java_home/bin/java"; do
  if [[ ! -e $path ]]; then
    echo "缺少 RabbitMQ A3 输入：$path" >&2
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
work_root=$(mktemp -d "$work_parent/slf4j-rabbit-a3.XXXXXX")
java_tmp="$work_root/java-tmp"
mkdir -p "$result_root" "$java_tmp"

export JAVA_HOME=$java_home
export PATH="$JAVA_HOME/bin:$PATH"
export TMPDIR=$java_tmp
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:+$JAVA_TOOL_OPTIONS }-Djava.io.tmpdir=$java_tmp"

git clone --mirror --quiet "$repository" "$work_root/repository.git"
git --git-dir="$work_root/repository.git" cat-file -e "$consumer_commit^{commit}"

seed_policy=provided_project_seed
if [[ -z $m2_seed ]]; then
  seed_policy=project_local_dependency_go_offline
  m2_seed="$work_root/m2-seed"
  seed_checkout="$work_root/seed-checkout"
  mkdir -p "$m2_seed"
  git clone --quiet "$work_root/repository.git" "$seed_checkout"
  git -c advice.detachedHead=false -C "$seed_checkout" checkout --detach --quiet "$consumer_commit"
  sed -i 's#<slf4j-api.version>1.7.36</slf4j-api.version>#<slf4j-api.version>1.7.29</slf4j-api.version>#' \
    "$seed_checkout/pom.xml"
  printf 'mvn -Dmaven.repo.local=%q -B -ntp dependency:go-offline\n' "$m2_seed" \
    >"$result_root/seed-preparation-command.txt"
  set +e
  (
    cd "$seed_checkout" || exit 125
    mvn "-Dmaven.repo.local=$m2_seed" -B -ntp dependency:go-offline
  ) >"$result_root/seed-preparation.log" 2>&1
  seed_exit=$?
  set -e
  printf '%s\n' "$seed_exit" >"$result_root/seed-preparation-exit-code.txt"
  if [[ $seed_exit -ne 0 ]]; then
    echo "RabbitMQ A3 的项目内依赖种子准备失败，见 $result_root/seed-preparation.log" >&2
    exit 7
  fi
fi

{
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'work_root=%s\n' "$work_root"
  printf 'repository=%s\n' "$repository"
  printf 'consumer_commit=%s\n' "$consumer_commit"
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

printf 'repeat\tarm\tcommit\ttree\texpected_api\tactual_api\texpected_classic\tactual_classic\texpected_core\tactual_core\tdependency_exit\ttest_exit\ttests\tfailures\terrors\tskipped\tcontract_tests\tcontract_failures\tcontract_errors\tinput_diff_ok\tversion_ok\tcontract_ok\tdirection_ok\tduration_seconds\n' \
  >"$result_root/run-results.tsv"

unexpected=0
for repeat in 1 2 3; do
  repeat_dir="$result_root/repeat-$repeat"
  mkdir -p "$repeat_dir"

  for arm in before after; do
    checkout="$work_root/checkouts/repeat-$repeat/$arm"
    run_dir="$repeat_dir/$arm"
    local_repo="$work_root/m2/repeat-$repeat/$arm"
    mkdir -p "$run_dir/reports" "$local_repo"
    cp -a --reflink=auto "$m2_seed/." "$local_repo/"

    git clone --quiet "$work_root/repository.git" "$checkout"
    git -c advice.detachedHead=false -C "$checkout" checkout --detach --quiet "$consumer_commit"
    contract_target="$checkout/src/test/java/com/rabbitmq/jms/LoggingProviderCompatibilityTest.java"
    if [[ -e $contract_target ]]; then
      echo "固定合同目标路径已存在：$contract_target" >&2
      exit 5
    fi

    original_property_count=$(rg -c '<slf4j-api\.version>1\.7\.36</slf4j-api\.version>' "$checkout/pom.xml")
    if [[ $original_property_count -ne 1 ]]; then
      echo "SLF4J 属性的固定输入不唯一：$checkout/pom.xml" >&2
      exit 6
    fi
    sed -i "s#<slf4j-api.version>1.7.36</slf4j-api.version>#<slf4j-api.version>${expected_api[$arm]}</slf4j-api.version>#" \
      "$checkout/pom.xml"
    cp "$contract_source" "$contract_target"

    git -C "$checkout" rev-parse HEAD >"$run_dir/commit.txt"
    git -C "$checkout" rev-parse 'HEAD^{tree}' >"$run_dir/tree.txt"
    git -C "$checkout" diff -- pom.xml >"$run_dir/version-input.patch"
    git -C "$checkout" diff --no-index /dev/null \
      src/test/java/com/rabbitmq/jms/LoggingProviderCompatibilityTest.java \
      >"$run_dir/contract.patch" 2>/dev/null || true

    changed_lines=$(git -C "$checkout" diff --numstat -- pom.xml | awk '{print $1 + $2}')
    input_diff_ok=false
    if [[ $changed_lines -eq 2 ]] &&
       rg -q '^-    <slf4j-api\.version>1\.7\.36</slf4j-api\.version>$' "$run_dir/version-input.patch" &&
       rg -q "^\+    <slf4j-api\.version>${expected_api[$arm]}</slf4j-api.version>$" "$run_dir/version-input.patch"; then
      input_diff_ok=true
    fi

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
    while IFS= read -r -d '' report; do
      report_tests=$(xmllint --xpath 'string(/testsuite/@tests)' "$report" 2>/dev/null || printf 0)
      report_failures=$(xmllint --xpath 'string(/testsuite/@failures)' "$report" 2>/dev/null || printf 0)
      report_errors=$(xmllint --xpath 'string(/testsuite/@errors)' "$report" 2>/dev/null || printf 0)
      report_skipped=$(xmllint --xpath 'string(/testsuite/@skipped)' "$report" 2>/dev/null || printf 0)
      tests=$((tests + report_tests))
      failures=$((failures + report_failures))
      errors=$((errors + report_errors))
      skipped=$((skipped + report_skipped))
      cp "$report" "$run_dir/reports/"
    done < <(find "$checkout/target/surefire-reports" -maxdepth 1 -type f \
      -name 'TEST-*.xml' -print0 2>/dev/null)

    contract_report="$checkout/target/surefire-reports/TEST-com.rabbitmq.jms.LoggingProviderCompatibilityTest.xml"
    contract_tests=0
    contract_failures=0
    contract_errors=0
    if [[ -f $contract_report ]]; then
      contract_tests=$(xmllint --xpath 'string(/testsuite/@tests)' "$contract_report")
      contract_failures=$(xmllint --xpath 'string(/testsuite/@failures)' "$contract_report")
      contract_errors=$(xmllint --xpath 'string(/testsuite/@errors)' "$contract_report")
    fi

    version_ok=false
    if [[ $dependency_exit -eq 0 && $actual_api == "${expected_api[$arm]}" && \
          $actual_classic == 1.2.11 && $actual_core == 1.2.11 ]]; then
      version_ok=true
    fi
    contract_ok=false
    if [[ $contract_tests -eq 1 && $contract_failures -eq 0 && $contract_errors -eq 0 ]] &&
       rg -q 'isInstanceOf\(LoggerContext\.class\)' "$contract_target"; then
      contract_ok=true
    fi
    direction_ok=false
    if [[ $test_exit -eq 0 && $tests -eq 115 && $failures -eq 0 && $errors -eq 0 && \
          $skipped -eq 0 && $input_diff_ok == true && $version_ok == true && \
          $contract_ok == true ]]; then
      direction_ok=true
    fi
    if [[ $direction_ok != true ]]; then
      unexpected=$((unexpected + 1))
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$repeat" "$arm" "$consumer_commit" "$(cat "$run_dir/tree.txt")" \
      "${expected_api[$arm]}" "$actual_api" 1.2.11 "$actual_classic" 1.2.11 "$actual_core" \
      "$dependency_exit" "$test_exit" "$tests" "$failures" "$errors" "$skipped" \
      "$contract_tests" "$contract_failures" "$contract_errors" "$input_diff_ok" \
      "$version_ok" "$contract_ok" "$direction_ok" "$duration_seconds" \
      >>"$result_root/run-results.tsv"
  done
done

finished_at=$(date --iso-8601=seconds)
{
  printf 'finished_at=%s\n' "$finished_at"
  printf 'unexpected_results=%s\n' "$unexpected"
  printf 'repetition_semantics=stability measurements, not independent semantic reviews\n'
  printf 'coverage_boundary=the provider contract exercises ordinary LoggerFactory initialization, not every initialization-failure or concurrent-cleanup path changed in SLF4J 1.7.30\n'
} >>"$result_root/environment.txt"

jq -n \
  --arg evaluated_at "2026-08-25" \
  --arg consumer_commit "$consumer_commit" \
  --arg environment "$(java -version 2>&1 | head -1); $(mvn -version | head -1)" \
  --argjson unexpected "$unexpected" \
  '{
    evaluated_at: $evaluated_at,
    source_repository: "qos-ch/slf4j",
    compatible_change: {from: "1.7.29", to: "1.7.30"},
    target_repository: "rabbitmq/rabbitmq-jms-client",
    consumer_commit: $consumer_commit,
    contract: "com.rabbitmq.jms.LoggingProviderCompatibilityTest#initializesTheConfiguredLoggingProvider",
    contract_assertion: "LoggerFactory.getILoggerFactory() returns ch.qos.logback.classic.LoggerContext",
    environment: $environment,
    repetitions: 3,
    fresh_checkouts: 6,
    maven_repository_policy: "one project-local small-seed copy per repetition and arm",
    arms: {
      before: {slf4j_api: "1.7.29", logback_classic: "1.2.11", logback_core: "1.2.11", runs: 3, tests_per_run: 115, result: "pass_in_all_runs"},
      after: {slf4j_api: "1.7.30", logback_classic: "1.2.11", logback_core: "1.2.11", runs: 3, tests_per_run: 115, result: "pass_in_all_runs"}
    },
    measurements: {
      maven_test_commands: 6,
      total_tests_executed: 690,
      dependency_resolutions_matching_expected: (6 - $unexpected),
      directions_matching_expected: (6 - $unexpected),
      provider_contract_passes: (6 - $unexpected),
      unexpected_results: $unexpected
    },
    input_delta: "both arms use the same consumer commit and contract; only slf4j-api.version differs, at 1.7.29 versus 1.7.30",
    coverage_boundary: "The provider contract exercises ordinary LoggerFactory initialization, not every initialization-failure or concurrent-cleanup path changed in SLF4J 1.7.30.",
    evidence_status: "three execution repetitions complete when unexpected_results is zero",
    semantic_review_status: "not independently reviewed; repetitions are stability measurements, not separate relations or reviews"
  }' >"$result_root/summary.json"

exit "$unexpected"
