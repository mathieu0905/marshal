#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "用法：$0 <Future Converter 克隆> <LPVS 克隆> <IDS Messaging Services 克隆> <Maven 缓存目录> <结果目录>" >&2
  exit 2
fi

future_repo=$1
lpvs_repo=$2
ids_repo=$3
cache_root=$(realpath -m "$4")
output=$(realpath -m "$5")
mkdir -p "$cache_root" "$output"

export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"

run_repository() {
  local name=$1
  local repo_dir=$2
  local a0=$3
  local a1=$4
  local arm commit

  for arm in a0 a1; do
    if [[ "$arm" == a0 ]]; then
      commit=$a0
    else
      commit=$a1
    fi
    git -C "$repo_dir" checkout --detach --force "$commit" \
      >"$output/${name}-${arm}-checkout.log" 2>&1
    set +e
    (
      cd "$repo_dir"
      mvn -B -Dmaven.repo.local="$cache_root/$name" clean test
    ) >"$output/${name}-${arm}.log" 2>&1
    local status=$?
    set -e
    printf '%s\n' "$status" >"$output/${name}-${arm}.exit"
  done
}

run_repository future-converter "$future_repo" \
  60f8e83e1c256992cafa7b4666a525eb23869eae \
  70e13f6bdb7de7f8eda9f174a5616284f2157ea7 &
pid_future=$!

run_repository lpvs "$lpvs_repo" \
  2932c4f8baa3838b1c9e97cb6c45f4b7d53aa7e7 \
  c1fc16b4fe9dfdfa16ce7248fccad0e7d994094d &
pid_lpvs=$!

run_repository ids-messaging-services "$ids_repo" \
  70731ef41c4f9ab4de972218e600166c2058be0b \
  fb71d68c62a6b9263ebc5113d97c91535d3106b2 &
pid_ids=$!

wait "$pid_future"
wait "$pid_lpvs"
wait "$pid_ids"

printf 'repository\tarm\tcommit\texit_code\n' >"$output/run-results.tsv"
for repository in future-converter lpvs ids-messaging-services; do
  case "$repository" in
    future-converter)
      a0=60f8e83e1c256992cafa7b4666a525eb23869eae
      a1=70e13f6bdb7de7f8eda9f174a5616284f2157ea7
      ;;
    lpvs)
      a0=2932c4f8baa3838b1c9e97cb6c45f4b7d53aa7e7
      a1=c1fc16b4fe9dfdfa16ce7248fccad0e7d994094d
      ;;
    ids-messaging-services)
      a0=70731ef41c4f9ab4de972218e600166c2058be0b
      a1=fb71d68c62a6b9263ebc5113d97c91535d3106b2
      ;;
  esac
  for arm in a0 a1; do
    if [[ "$arm" == a0 ]]; then commit=$a0; else commit=$a1; fi
    printf '%s\t%s\t%s\t%s\n' "$repository" "$arm" "$commit" \
      "$(<"$output/${repository}-${arm}.exit")" >>"$output/run-results.tsv"
  done
done
