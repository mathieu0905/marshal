#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "用法：$0 <BUMP 仓库> <输出 JSONL>" >&2
  exit 2
fi

bump_repo=$(realpath "$1")
output=$(realpath -m "$2")
revision=$(git -C "$bump_repo" rev-parse HEAD)
mkdir -p "$(dirname "$output")"

find "$bump_repo/data/benchmark" "$bump_repo/data/unsuccessful-reproductions" \
  -maxdepth 1 -type f -name '*.json' -print0 \
  | sort -z \
  | while IFS= read -r -d '' record; do
      subset=$(basename "$(dirname "$record")")
      jq -c \
        --arg revision "$revision" \
        --arg subset "$subset" \
        --arg record "${record#"$bump_repo/"}" '
          select(
            .updatedDependency.githubRepoSlug == "checkstyle/checkstyle"
            or (
              .updatedDependency.dependencyGroupID == "com.puppycrawl.tools"
              and .updatedDependency.dependencyArtifactID == "checkstyle"
            )
          )
          | {
              source_dataset: "BUMP",
              source_revision: $revision,
              source_subset: $subset,
              source_record: $record,
              repository: (.projectOrganisation + "/" + .project),
              pull_request_url: .url,
              breaking_commit: .breakingCommit,
              previous_version: .updatedDependency.previousVersion,
              new_version: .updatedDependency.newVersion,
              dependency_section: .updatedDependency.dependencySection,
              declared_failure_category: .failureCategory,
              reproduction_java: .javaVersionUsedForReproduction,
              label_status: "lead_only"
            }
        ' "$record"
    done >"$output"
