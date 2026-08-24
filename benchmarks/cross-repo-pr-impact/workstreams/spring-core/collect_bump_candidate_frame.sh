#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "用法：$0 <BUMP Git 仓库> <输出 JSONL>" >&2
  exit 2
fi

bump_repo=$(realpath "$1")
output=$(realpath -m "$2")
revision=324d5513aa5ca40b5cb32de5b816a58fa60bd7bb
git -C "$bump_repo" cat-file -e "${revision}^{commit}"
mkdir -p "$(dirname "$output")"

git -C "$bump_repo" grep -l -E \
  '"dependencyArtifactID"[[:space:]]*:[[:space:]]*"spring-core"' \
  "$revision" -- data/benchmark data/unsuccessful-reproductions \
  | sed "s#^${revision}:##" \
  | sort \
  | while IFS= read -r record; do
      subset=$(basename "$(dirname "$record")")
      git -C "$bump_repo" show "$revision:$record" \
        | jq -c \
          --arg revision "$revision" \
          --arg subset "$subset" \
          --arg record "$record" '
            select(
              .updatedDependency.dependencyGroupID == "org.springframework"
              and .updatedDependency.dependencyArtifactID == "spring-core"
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
          '
    done >"$output"
