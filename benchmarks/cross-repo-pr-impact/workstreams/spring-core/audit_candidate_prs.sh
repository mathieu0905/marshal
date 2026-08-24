#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "用法：$0 <候选框 JSONL> <输出 JSONL>" >&2
  exit 2
fi

frame=$(realpath "$1")
output=$(realpath -m "$2")
mkdir -p "$(dirname "$output")"

while IFS=$'\t' read -r subset repository url; do
  number=${url##*/}
  gh api "repos/${repository}/pulls/${number}" \
    | jq -c \
      --arg subset "$subset" \
      --arg repository "$repository" '
        {
          source_subset: $subset,
          repository: $repository,
          pull_request_url: .html_url,
          number: .number,
          state: .state,
          merged: .merged,
          merged_at: .merged_at,
          base_sha: .base.sha,
          head_sha: .head.sha,
          title: .title
        }
      '
done < <(
  jq -r '[.source_subset, .repository, .pull_request_url] | @tsv' "$frame"
) >"$output"
