#!/usr/bin/env bash
set -u

if [ "$#" -ne 4 ]; then
  echo "usage: $0 <a0-checkout> <a1-checkout> <a2-checkout> <result-dir>" >&2
  exit 2
fi

a0_checkout=$1
a1_checkout=$2
a2_checkout=$3
result_dir=$4
mkdir -p "$result_dir"
: > "$result_dir/run-results.tsv"

run_arm() {
  checkout=$1
  arm=$2
  expected_full_status=$3

  (
    cd "$checkout" || exit 125
    mvn -B -Dincludes=org.antlr:antlr4-runtime dependency:tree
  ) > "$result_dir/${arm}-dependency-tree.log" 2>&1
  dependency_status=$?

  (
    cd "$checkout" || exit 125
    mvn -B -Dtest=test.AdvancedCSSTest test
  ) > "$result_dir/${arm}.log" 2>&1
  selected_status=$?

  (
    cd "$checkout" || exit 125
    mvn -B clean test
  ) > "$result_dir/full-${arm}.log" 2>&1
  full_status=$?

  printf '%s\t%s\t%s\t%s\n' \
    "$arm" "$dependency_status" "$selected_status" "$full_status" \
    >> "$result_dir/run-results.tsv"

  if [ "$dependency_status" -ne 0 ] || [ "$full_status" -ne "$expected_full_status" ]; then
    return 1
  fi
}

overall_status=0
run_arm "$a0_checkout" A0 0 || overall_status=1
run_arm "$a1_checkout" A1 1 || overall_status=1
run_arm "$a2_checkout" A2 0 || overall_status=1
exit "$overall_status"
