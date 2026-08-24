#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <结果目录>" >&2
  exit 2
fi

output_dir=$1
mkdir -p "$output_dir"

commits=(
  1053033eef680f0199bf25ec6e3db52cc13ef3da
  12684ee6cfd293b27c08495f97900bcd849b452c
  ee0827d4c9bf80982241e8c3559dceb8b39063e4
)

run_arm() {
  local commit=$1
  local arm=$2
  local image="ghcr.io/chains-project/breaking-updates:${commit}-${arm}"
  local log="$output_dir/${commit}-${arm}.log"
  local status_file="$output_dir/${commit}-${arm}-docker-exit-status.txt"
  local result_file="$output_dir/${commit}-${arm}-maven-result.txt"

  set +e
  docker run --rm "$image" >"$log" 2>&1
  local status=$?
  set -e
  printf '%s\n' "$status" >"$status_file"
  awk '/\[INFO\] BUILD (SUCCESS|FAILURE)/ {result=$NF} END {print result}' \
    "$log" >"$result_file"
}

pids=()
for commit in "${commits[@]}"; do
  for arm in pre breaking; do
    run_arm "$commit" "$arm" &
    pids+=("$!")
  done
done

failed=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    failed=1
  fi
done

exit "$failed"
