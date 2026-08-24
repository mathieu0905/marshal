#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法：$0 <BUMP 仓库目录>" >&2
  exit 2
fi

bump_dir=$1
revision=324d5513aa5ca40b5cb32de5b816a58fa60bd7bb
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
output=$script_dir/bump-candidate-frame.jsonl

if [[ $(git -C "$bump_dir" rev-parse HEAD) != "$revision" ]]; then
  echo "BUMP 版本不符，要求 $revision" >&2
  exit 3
fi

for subset in benchmark unsuccessful-reproductions; do
  find "$bump_dir/data/$subset" -maxdepth 1 -type f -name '*.json' -print0 |
    sort -z |
    xargs -0 jq -c --arg revision "$revision" --arg subset "$subset" '
      select(
        .updatedDependency.dependencyGroupID == "org.mockito" and
        .updatedDependency.dependencyArtifactID == "mockito-core"
      ) |
      {
        source_dataset: "BUMP",
        source_revision: $revision,
        source_subset: $subset,
        source_record: ("data/" + $subset + "/" + .breakingCommit + ".json"),
        repository: (.projectOrganisation + "/" + .project),
        pull_request_url: .url,
        breaking_commit: .breakingCommit,
        previous_version: .updatedDependency.previousVersion,
        new_version: .updatedDependency.newVersion,
        declared_failure_category: .failureCategory,
        reproduction_java: .javaVersionUsedForReproduction,
        native_command_status: "not_independently_verified_by_frame",
        label_status: "lead_only"
      }
    '
done | sort -t '"' -k 24,24 >"$output"

count=$(wc -l <"$output")
repo_count=$(jq -r .repository "$output" | sort -u | wc -l)
printf '写入 %s：%s 条记录，%s 个唯一消费仓。\n' "$output" "$count" "$repo_count"
