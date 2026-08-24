#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <结果目录>" >&2
  exit 2
fi

output_dir=$1
mkdir -p "$output_dir"

commits=(
  0ee8b9376b967938e8efd89a0959214a30d1b3fb
  ff8b5b61548d50cf60b77784a181e917cb35033b
  9b63e53888ebdd9c84f4eec3cb661299dea41344
  4631885da3cfd6601de5d24133fa3828a590ca9e
  7c90c61e90e9936d8a7e355de8900214c759cb61
  2dfaa41bfb97674d11f09a5885011f19808548a3
  8b057977647445aade80627a06bd65867f64b948
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

for commit in "${commits[@]}"; do
  for arm in pre breaking; do
    while (( $(jobs -pr | wc -l) >= 4 )); do
      wait -n
    done
    run_arm "$commit" "$arm" &
  done
done

wait
