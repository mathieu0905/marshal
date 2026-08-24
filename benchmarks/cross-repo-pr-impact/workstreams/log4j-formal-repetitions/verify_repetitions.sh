#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
benchmark_root=$(cd "$script_dir/../.." && pwd)
result_root="$benchmark_root/results/log4j-formal-repetitions-2026-08-25"

export JAVA_HOME=${LOG4J_FORMAL_JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
export PATH="$JAVA_HOME/bin:$PATH"

repos=(neqsim archifacts elimu powertools)
configs=(a0 a1 a2 a3-before a3-after)
negative_repos=(archifacts elimu powertools)

printf 'repeat\tcommands\tversion_matches\tdirection_matches\tinput_parity\tfailure_shape\tfull_graph_parity\n' \
  >"$result_root/verification-results.tsv"

for repeat in 1 2 3; do
  repeat_dir="$result_root/repeat-$repeat"
  result_tsv="$repeat_dir/run-results.tsv"
  environment="$repeat_dir/environment.txt"
  if [[ ! -f $result_tsv || ! -f $environment ]]; then
    echo "重复 $repeat 尚未完成" >&2
    exit 5
  fi
  if [[ $(sed -n 's/^unexpected_results=//p' "$environment") != 0 ]]; then
    echo "重复 $repeat 含意外结果" >&2
    exit 6
  fi

  commands=$(awk 'NR > 1 {count++} END {print count+0}' "$result_tsv")
  version_matches=$(awk -F '\t' 'NR > 1 && $14 == "true" {count++} END {print count+0}' "$result_tsv")
  direction_matches=$(awk -F '\t' 'NR > 1 && $15 == "true" {count++} END {print count+0}' "$result_tsv")
  if [[ $commands -ne 20 || $version_matches -ne 20 || $direction_matches -ne 20 ]]; then
    echo "重复 $repeat 的命令矩阵不完整" >&2
    exit 7
  fi

  input_parity=true
  for repo in "${negative_repos[@]}"; do
    if ! cmp -s "$repeat_dir/runs/a1/$repo/input.diff" "$repeat_dir/runs/a2/$repo/input.diff" \
      || ! cmp -s "$repeat_dir/runs/a1/$repo/input.properties" "$repeat_dir/runs/a2/$repo/input.properties" \
      || ! cmp -s "$repeat_dir/runs/a0/$repo/input.diff" "$repeat_dir/runs/a3-after/$repo/input.diff"; then
      input_parity=false
    fi
  done
  if [[ $input_parity != true ]]; then
    echo "重复 $repeat 的限定负例输入不一致" >&2
    exit 8
  fi

  printf 'config\trepository\ttests\tfailures\terrors\tskipped\tfailing_suites\n' \
    >"$repeat_dir/test-outcomes.tsv"
  failure_shape=true
  for config in "${configs[@]}"; do
    for repo in "${repos[@]}"; do
      report_root="$repeat_dir/runs/$config/$repo/reports"
      tests=0
      failures=0
      errors=0
      skipped=0
      failing_suites=0
      failing_file="$repeat_dir/runs/$config/$repo/failing-suites.tsv"
      : >"$failing_file"
      while IFS= read -r -d '' report; do
        suite=$(xmllint --xpath 'string(/testsuite/@name)' "$report")
        report_tests=$(xmllint --xpath 'string(/testsuite/@tests)' "$report")
        report_failures=$(xmllint --xpath 'string(/testsuite/@failures)' "$report")
        report_errors=$(xmllint --xpath 'string(/testsuite/@errors)' "$report")
        report_skipped=$(xmllint --xpath 'string(/testsuite/@skipped)' "$report")
        tests=$((tests + report_tests))
        failures=$((failures + report_failures))
        errors=$((errors + report_errors))
        skipped=$((skipped + report_skipped))
        if ((report_failures + report_errors > 0)); then
          failing_suites=$((failing_suites + 1))
          printf '%s\t%s\t%s\t%s\t%s\n' "$suite" "$report_tests" "$report_failures" \
            "$report_errors" "$report_skipped" >>"$failing_file"
        fi
      done < <(find "$report_root" -type f -name 'TEST-*.xml' -print0)
      sort -o "$failing_file" "$failing_file"
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$config" "$repo" "$tests" \
        "$failures" "$errors" "$skipped" "$failing_suites" >>"$repeat_dir/test-outcomes.tsv"

      if [[ $repo == neqsim && $config == a1 ]]; then
        if [[ $tests -ne 134 || $failures -ne 0 || $errors -ne 131 || $skipped -ne 1 ]]; then
          failure_shape=false
        fi
      elif [[ $failures -ne 0 || $errors -ne 0 ]]; then
        failure_shape=false
      fi
    done
  done
  if [[ $failure_shape != true ]]; then
    echo "重复 $repeat 的测试失败集合超出既定边界" >&2
    exit 9
  fi

  work_root=$(sed -n 's/^work_root=//p' "$environment")
  maven_settings="$work_root/settings.xml"
  mkdir -p "$work_root/tmp" "$work_root/java-tmp"
  full_graph_parity=true
  for repo in "${negative_repos[@]}"; do
    for config in a1 a2; do
      run_dir="$repeat_dir/runs/$config/$repo"
      consumer="$work_root/consumers/$config/$repo"
      local_repo="$work_root/m2/$config"
      extra_args=()
      module_args=()
      if [[ $repo == powertools ]]; then
        module_args=(-pl powertools-logging)
        extra_args=(-Dlog4j.version=2.18.0 -Daws.sdk.version=2.17.223)
      fi
      (
        cd "$consumer" || exit 125
        export TMPDIR="$work_root/tmp"
        export MAVEN_OPTS="${MAVEN_OPTS:-} -Djava.io.tmpdir=$work_root/java-tmp"
        timeout --signal=TERM 30m mvn -s "$maven_settings" "-Dmaven.repo.local=$local_repo" \
          -Dstyle.color=never -B -ntp "${module_args[@]}" dependency:tree \
          -Dincludes=org.apache.logging.log4j "${extra_args[@]}"
      ) >"$run_dir/log4j-dependency-tree.log" 2>&1
      sed $'s/\\033\\[[0-9;]*m//g' "$run_dir/log4j-dependency-tree.log" | \
        awk '
          match($0, /org\.apache\.logging\.log4j:[^[:space:]]+/) {
            coordinate=substr($0, RSTART, RLENGTH)
            sub(/,$/, "", coordinate)
            print coordinate
          }
        ' | sort -u >"$run_dir/log4j-resolved-coordinates.txt"
      if [[ ! -s $run_dir/log4j-resolved-coordinates.txt ]]; then
        full_graph_parity=false
      fi
    done
    if ! cmp -s "$repeat_dir/runs/a1/$repo/log4j-resolved-coordinates.txt" \
      "$repeat_dir/runs/a2/$repo/log4j-resolved-coordinates.txt"; then
      full_graph_parity=false
    fi
  done
  if [[ $full_graph_parity != true ]]; then
    echo "重复 $repeat 的限定负例完整 Log4j 依赖图不一致" >&2
    exit 10
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$repeat" "$commands" "$version_matches" \
    "$direction_matches" "$input_parity" "$failure_shape" "$full_graph_parity" \
    >>"$result_root/verification-results.tsv"
done

for repeat in 2 3; do
  cmp -s "$result_root/repeat-1/runs/a1/neqsim/failing-suites.tsv" \
    "$result_root/repeat-$repeat/runs/a1/neqsim/failing-suites.tsv"
done

printf 'verification=pass\n' >"$result_root/verification-status.txt"
