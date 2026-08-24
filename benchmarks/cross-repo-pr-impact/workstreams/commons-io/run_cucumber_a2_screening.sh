#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <结果目录>" >&2
  exit 2
fi

output_dir=$1
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
image=ghcr.io/chains-project/breaking-updates:12684ee6cfd293b27c08495f97900bcd849b452c-breaking
log=$output_dir/cucumber-a2.log

mkdir -p "$output_dir"

set +e
docker run --rm \
  --entrypoint sh \
  --volume "$script_dir/cucumber-maintainer-repair.patch:/input/cucumber-maintainer-repair.patch:ro" \
  "$image" \
  -c 'git apply --no-index /input/cucumber-maintainer-repair.patch && mvn clean test -B' \
  >"$log" 2>&1
status=$?
set -e

printf '%s\n' "$status" >"$output_dir/cucumber-a2-exit-status.txt"
awk '/\[INFO\] BUILD (SUCCESS|FAILURE)/ {result=$NF} END {print result}' \
  "$log" >"$output_dir/cucumber-a2-maven-result.txt"

exit "$status"
