#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <结果目录>" >&2
  exit 2
fi

output_dir=$1
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
pre_image=ghcr.io/chains-project/breaking-updates:2dfaa41bfb97674d11f09a5885011f19808548a3-pre
breaking_image=ghcr.io/chains-project/breaking-updates:2dfaa41bfb97674d11f09a5885011f19808548a3-breaking
log=$output_dir/bval-a2.log

mkdir -p "$output_dir"
cache_root=$(mktemp -d "$output_dir/.bval-cache.XXXXXX")
cache_container=marshal-mockito-bval-cache-$$

cleanup() {
  docker rm -f "$cache_container" >/dev/null 2>&1 || true
  rm -rf -- "$cache_root"
}
trap cleanup EXIT

# A1 stops before the TCK, so its image lacks historical snapshot artifacts
# which remain available in the matching A0 image cache.
docker create --name "$cache_container" "$pre_image" sh -c true >/dev/null
mkdir -p "$cache_root/openwebbeans"
docker cp \
  "$cache_container:/root/.m2/repository/org/apache/openwebbeans/." \
  "$cache_root/openwebbeans"
docker rm "$cache_container" >/dev/null

set +e
docker run --rm \
  --entrypoint sh \
  --volume "$script_dir/bval-maintainer-repair.patch:/input/bval-maintainer-repair.patch:ro" \
  --volume "$cache_root/openwebbeans:/root/.m2/repository/org/apache/openwebbeans" \
  "$breaking_image" \
  -c 'git apply --no-index /input/bval-maintainer-repair.patch && mvn clean test -B' \
  >"$log" 2>&1
status=$?
set -e

printf '%s\n' "$status" >"$output_dir/bval-a2-exit-status.txt"
awk '/\[INFO\] BUILD (SUCCESS|FAILURE)/ {result=$NF} END {print result}' \
  "$log" >"$output_dir/bval-a2-maven-result.txt"

exit "$status"
