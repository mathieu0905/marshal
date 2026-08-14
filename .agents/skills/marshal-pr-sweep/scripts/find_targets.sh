#!/usr/bin/env bash
# Deterministically find open Cowboy PRs that need a Marshal deep review.
# JSONL targets go to stdout; diagnostics go to stderr. Any discovery blind spot
# exits nonzero so callers never process a partial queue as if it were complete.

set -euo pipefail

ORG="${ORG:-cowboyinc}"
REPOS="${REPOS:-node runner cbss cbfs cowboy gateway cowboy-protocol}"
INCLUDE_DRAFT="${INCLUDE_DRAFT:-0}"
REQUIRE_CI_PASS="${REQUIRE_CI_PASS:-1}"
SKIP_CIP10="${SKIP_CIP10:-1}"
PR_LIMIT="${PR_LIMIT:-1000}"

MARKER_RE='<!--[ ]marshal-deep[ ]sha=([0-9a-f]{40})[ ]-->'
CIP10_TITLE_RE='CIP[-_[:space:]]*10([^0-9]|$)|Container Registry'

for toggle_name in INCLUDE_DRAFT REQUIRE_CI_PASS SKIP_CIP10; do
  toggle_value="${!toggle_name}"
  case "$toggle_value" in
    0|1) ;;
    *) echo "ERROR: $toggle_name must be 0 or 1" >&2; exit 2 ;;
  esac
done
if ! [[ "$PR_LIMIT" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: PR_LIMIT must be a positive integer" >&2
  exit 2
fi

for tool in gh jq grep sed; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $tool" >&2
    exit 1
  }
done

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: GitHub authentication is not healthy" >&2
  exit 1
fi
if ! marker_author="$(gh api user --jq '.login' 2>/dev/null)" || [ -z "$marker_author" ]; then
  echo "ERROR: cannot resolve the authenticated GitHub login" >&2
  exit 1
fi

ci_state() {
  gh pr view "$2" -R "$1" --json statusCheckRollup --jq '
    .statusCheckRollup as $r
    | ($r | map(select(
        (.__typename=="CheckRun" and (.conclusion|IN("FAILURE","CANCELLED","TIMED_OUT","ACTION_REQUIRED","STARTUP_FAILURE","ERROR")))
        or (.__typename=="StatusContext" and (.state|IN("FAILURE","ERROR")))
      )) | length) as $fail
    | ($r | map(select(
        (.__typename=="CheckRun" and .status!="COMPLETED")
        or (.__typename=="StatusContext" and (.state|IN("PENDING","EXPECTED")))
      )) | length) as $pending
    | ($r | map(select(
        (.__typename=="CheckRun" and .status=="COMPLETED" and
          ((.conclusion|IN("SUCCESS","NEUTRAL","SKIPPED"))|not))
        or (.__typename=="StatusContext" and
          ((.state|IN("SUCCESS","FAILURE","ERROR","PENDING","EXPECTED"))|not))
        or (.__typename!="CheckRun" and .__typename!="StatusContext")
      )) | length) as $unknown
    | if $fail>0 then "failing"
      elif $pending>0 or $unknown>0 then "pending"
      else "clean" end
  ' 2>/dev/null
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
degraded=0

for repo in $REPOS; do
  if ! prs="$(gh pr list -R "$ORG/$repo" --state open --limit "$PR_LIMIT" \
      --json number,headRefOid,isDraft,title,url 2>/dev/null)"; then
    echo "WARN: cannot list PRs for $ORG/$repo" >&2
    degraded=1
    continue
  fi
  if ! count="$(printf '%s' "$prs" | jq -er \
      'if type == "array" then length else error("not an array") end' 2>/dev/null)"; then
    echo "WARN: invalid PR list for $ORG/$repo" >&2
    degraded=1
    continue
  fi
  echo "INFO: $repo — $count open PR(s)" >&2
  if [ "$count" -ge "$PR_LIMIT" ]; then
    echo "WARN: PR list for $ORG/$repo reached PR_LIMIT=$PR_LIMIT; discovery may be truncated" >&2
    degraded=1
    continue
  fi
  if ! pr_rows="$(printf '%s' "$prs" | jq -c '.[]' 2>/dev/null)"; then
    echo "WARN: invalid PR list for $ORG/$repo" >&2
    degraded=1
    continue
  fi

  while IFS= read -r pr; do
    [ -n "$pr" ] || continue
    if ! printf '%s' "$pr" | jq -e '
        (.number | type == "number" and . > 0 and . == floor)
        and (.headRefOid | type == "string" and test("^[0-9a-f]{40}$"))
        and (.isDraft | type == "boolean")
        and (.title | type == "string")
        and (.url | type == "string" and length > 0)
      ' >/dev/null 2>&1; then
      echo "WARN: invalid PR metadata in $ORG/$repo" >&2
      degraded=1
      continue
    fi
    num="$(printf '%s' "$pr" | jq -r '.number')"
    head="$(printf '%s' "$pr" | jq -r '.headRefOid')"
    draft="$(printf '%s' "$pr" | jq -r '.isDraft')"
    title="$(printf '%s' "$pr" | jq -r '.title')"
    url="$(printf '%s' "$pr" | jq -r '.url')"

    if [ "$draft" = "true" ] && [ "$INCLUDE_DRAFT" != "1" ]; then
      echo "INFO:   $repo#$num skip (draft)" >&2
      continue
    fi
    if [ "$SKIP_CIP10" = "1" ] && printf '%s' "$title" | grep -qiE "$CIP10_TITLE_RE"; then
      echo "INFO:   $repo#$num skip (cip-10 avoidance)" >&2
      continue
    fi

    if ! comments_json="$(gh api "repos/$ORG/$repo/issues/$num/comments" \
        --paginate 2>/dev/null)"; then
      echo "WARN: cannot read comments for $repo#$num" >&2
      degraded=1
      continue
    fi
    if ! comments="$(printf '%s\n' "$comments_json" | jq -rs --arg author "$marker_author" \
        'add // [] | .[] | select(.user.login == $author) | .body // empty' 2>/dev/null)"; then
      echo "WARN: invalid comments response for $repo#$num" >&2
      degraded=1
      continue
    fi

    reviewed_sha="$(printf '%s' "$comments" | grep -oE "$MARKER_RE" \
      | sed -E 's/.*sha=([0-9a-f]{40}).*/\1/' | tail -n1 || true)"
    if [ -z "$reviewed_sha" ]; then
      reason="never"
    elif [ "$reviewed_sha" = "$head" ]; then
      echo "INFO:   $repo#$num skip (deep-reviewed at $reviewed_sha)" >&2
      continue
    else
      reason="updated"
    fi

    if [ "$REQUIRE_CI_PASS" = "1" ]; then
      if ! ci="$(ci_state "$ORG/$repo" "$num")"; then
        echo "WARN: cannot read CI state for $repo#$num" >&2
        degraded=1
        continue
      fi
      if [ "$ci" != "clean" ]; then
        echo "INFO:   $repo#$num skip (ci-$ci)" >&2
        continue
      fi
    fi

    if ! ct="$(gh api "repos/$ORG/$repo/commits/$head" \
        --jq '.commit.committer.date' 2>/dev/null)" || [ -z "$ct" ]; then
      echo "WARN: cannot read head commit time for $repo#$num" >&2
      degraded=1
      continue
    fi

    jq -nc --arg repo "$repo" --argjson pr "$num" --arg head "$head" \
      --arg reason "$reason" --arg ct "$ct" --arg title "$title" --arg url "$url" \
      '{repo:$repo, pr:$pr, head:$head, reason:$reason, commit_time:$ct, title:$title, url:$url}' \
      >>"$tmp"
  done <<<"$pr_rows"
done

if [ "$degraded" -ne 0 ]; then
  exit "$degraded"
fi
jq -s 'sort_by(.commit_time) | reverse | .[]' -c "$tmp"
