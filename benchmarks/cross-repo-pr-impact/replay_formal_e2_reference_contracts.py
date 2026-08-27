#!/usr/bin/env python3
"""Replay exact removed-reference contracts across source/target commit arms."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import functools
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
GENERIC = {
    "Copyright", "Debian", "License", "Linux", "OpenStack", "River", "Systems",
    "StarlingX", "Ubuntu", "active", "address", "before", "bootstrap", "class",
    "complete", "config", "constants", "default", "distributed", "docker", "endpoint",
    "exception", "external", "filesystem", "function", "image", "integration", "interface",
    "internal", "kubernetes", "management", "messages", "namespace", "nullable", "operator",
    "platform", "plugin", "required", "resource", "return_value", "rollback", "scenario",
    "services", "software_version", "source", "starlingx", "status_code", "subcloud",
    "systemctl", "testing", "version",
}
NON_CONTRACT = {
    "about", "after", "before", "class", "const", "Copyright", "define",
    "false", "from", "function", "import", "include", "License", "return",
    "self", "string", "that", "this", "true", "value", "with",
}
EXCLUDED_PATH_PARTS = ("test", "doc/", ".zuul", "releasenote", "copyright")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def diff_token_paths(payload: str, prefix: str) -> dict[str, set[str]]:
    current: str | None = None
    result: dict[str, set[str]] = defaultdict(set)
    for line in payload.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current = parts[3][2:] if len(parts) >= 4 else None
        elif current and line.startswith(prefix) and not line.startswith(prefix * 3):
            for token in TOKEN.findall(line[1:]):
                result[token].add(current)
    return result


def diff_token_lines(payload: str, prefix: str) -> dict[tuple[str, str], list[str]]:
    current: str | None = None
    result: dict[tuple[str, str], list[str]] = defaultdict(list)
    for line in payload.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current = parts[3][2:] if len(parts) >= 4 else None
        elif current and line.startswith(prefix) and not line.startswith(prefix * 3):
            signature = line[1:].strip()
            if (
                not signature
                or len(signature) > 300
                or signature.startswith(("#", "//", "*", "<!--"))
            ):
                continue
            for token in TOKEN.findall(signature):
                result[(token, current)].append(signature)
    return result


def production_paths(paths: set[str]) -> list[str]:
    return sorted(
        path for path in paths
        if not any(part in path.lower() for part in EXCLUDED_PATH_PARTS)
    )


def token_quality(token: str) -> int:
    if token in NON_CONTRACT or token.lower() in {item.lower() for item in NON_CONTRACT}:
        return -1
    if len(token) < 5:
        return -1
    if token in GENERIC or token.lower() in {item.lower() for item in GENERIC}:
        return 0
    if "_" in token:
        return 4 + min(len(token), 24)
    if any(character.isupper() for character in token[1:]):
        return 3 + min(len(token), 24)
    if len(token) >= 8:
        return 1 + min(len(token), 24)
    return -1


def raw_url(repository: str, commit: str, path: str) -> str:
    encoded = urllib.parse.quote(path, safe="/")
    return f"https://opendev.org/{repository}/raw/commit/{commit}/{encoded}"


@functools.lru_cache(maxsize=None)
def fetch_raw(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "marshal-formal-e2-replay/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return b""
            if attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def count_token(payload: bytes, token: str) -> int:
    text = payload.decode("utf-8", errors="ignore")
    return len(re.findall(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", text))


def count_signature(payload: bytes, signature: str) -> int:
    return sum(
        line.strip() == signature
        for line in payload.decode("utf-8", errors="ignore").splitlines()
    )


def proposal_rows(
    sources: dict[str, dict[str, Any]],
    metadata: list[dict[str, Any]],
    source_patch_dir: Path,
    target_patch_dir: Path,
) -> list[dict[str, Any]]:
    proposals = []
    for metadata_row in metadata:
        candidate_id = metadata_row["candidate_id"]
        source = sources[candidate_id]["opening"]
        source_patch = (source_patch_dir / f"{candidate_id}.patch").read_text(
            encoding="utf-8", errors="ignore"
        )
        source_removed = diff_token_paths(source_patch, "-")
        source_added = diff_token_paths(source_patch, "+")
        source_lines = diff_token_lines(source_patch, "-")
        for target in metadata_row["targets"]:
            target_patch_path = target_patch_dir / f"{target['number']}.patch"
            if (
                not target.get("catalog_covered")
                or target["repository"] == source["repository"]
                or target.get("status") != "MERGED"
                or not target_patch_path.exists()
            ):
                continue
            target_patch = target_patch_path.read_text(encoding="utf-8", errors="ignore")
            target_removed = diff_token_paths(target_patch, "-")
            target_added = diff_token_paths(target_patch, "+")
            target_lines = diff_token_lines(target_patch, "-")
            choices = []
            for token in set(source_removed) & set(target_removed):
                quality = token_quality(token)
                if quality < 0:
                    continue
                source_paths = production_paths(source_removed[token])
                target_paths = production_paths(target_removed[token])
                if source_paths and target_paths:
                    if token not in source_added and token not in target_added:
                        quality += 4
                    for source_path in source_paths[:2]:
                        for target_path in target_paths[:2]:
                            source_signatures = source_lines.get((token, source_path), [])
                            target_signatures = target_lines.get((token, target_path), [])
                            if source_signatures and target_signatures:
                                choices.append((
                                    quality,
                                    token,
                                    source_path,
                                    target_path,
                                    min(source_signatures, key=lambda value: (len(value), value)),
                                    min(target_signatures, key=lambda value: (len(value), value)),
                                ))
            if not choices:
                continue
            for quality, token, source_path, target_path, source_signature, target_signature in choices:
                proposals.append({
                    "candidate_id": candidate_id,
                    "source_change": source["number"],
                    "source_repository": source["repository"],
                    "source_subject": source["subject"],
                    "source_base_commit": source["base_commit"],
                    "source_head_commit": source["head_commit"],
                    "source_path": source_path,
                    "target_change": target["number"],
                    "target_repository": target["repository"],
                    "target_subject": target["subject"],
                    "target_base_commit": target["base_commit"],
                    "target_head_commit": target["head_commit"],
                    "target_path": target_path,
                    "contract_token": token,
                    "source_signature": source_signature,
                    "target_signature": target_signature,
                    "quality": quality,
                    "revealed_at": metadata_row["revealed_at"],
                })
    proposals.sort(
        key=lambda row: (-row["quality"], row["candidate_id"], row["target_repository"], row["target_change"])
    )
    return proposals


def replay(proposal: dict[str, Any]) -> dict[str, Any]:
    token = proposal["contract_token"]
    endpoints = {
        "source_base": raw_url(proposal["source_repository"], proposal["source_base_commit"], proposal["source_path"]),
        "source_head": raw_url(proposal["source_repository"], proposal["source_head_commit"], proposal["source_path"]),
        "target_base": raw_url(proposal["target_repository"], proposal["target_base_commit"], proposal["target_path"]),
        "target_head": raw_url(proposal["target_repository"], proposal["target_head_commit"], proposal["target_path"]),
    }
    payloads = {name: fetch_raw(url) for name, url in endpoints.items()}
    counts = {name: count_token(payload, token) for name, payload in payloads.items()}
    signature_counts = {
        "source_base": count_signature(payloads["source_base"], proposal["source_signature"]),
        "source_head": count_signature(payloads["source_head"], proposal["source_signature"]),
        "target_base": count_signature(payloads["target_base"], proposal["target_signature"]),
        "target_head": count_signature(payloads["target_head"], proposal["target_signature"]),
    }
    token_eligible = (
        counts["source_base"] > 0
        and counts["source_head"] == 0
        and counts["target_base"] > 0
        and counts["target_head"] == 0
    )
    selected_counts = counts if token_eligible else signature_counts
    contract_mode = "removed_token" if token_eligible else "removed_reference_signature"
    arms = {
        "A0": "pass" if bool(selected_counts["source_base"]) == bool(selected_counts["target_base"]) else "fail",
        "A1": "pass" if bool(selected_counts["source_head"]) == bool(selected_counts["target_base"]) else "fail",
        "A2": "pass" if bool(selected_counts["source_head"]) == bool(selected_counts["target_head"]) else "fail",
    }
    eligible = (
        selected_counts["source_base"] > 0
        and selected_counts["source_head"] == 0
        and selected_counts["target_base"] > 0
        and selected_counts["target_head"] == 0
        and arms == {"A0": "pass", "A1": "fail", "A2": "pass"}
    )
    return {
        **proposal,
        "urls": endpoints,
        "token_counts": counts,
        "signature_counts": signature_counts,
        "contract_mode": contract_mode,
        "selected_counts": selected_counts,
        "arms": arms,
        "eligible": eligible,
    }


def run(
    source_events: Path,
    target_metadata: Path,
    source_patch_dir: Path,
    target_patch_dir: Path,
    output_dir: Path,
    workers: int,
    limit: int,
    review_decisions: Path | None = None,
) -> dict[str, Any]:
    sources = {row["candidate_id"]: row for row in read_jsonl(source_events)}
    proposals = proposal_rows(
        sources, read_jsonl(target_metadata), source_patch_dir, target_patch_dir
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        replays = list(executor.map(replay, proposals))
    decisions = {}
    if review_decisions is not None:
        decisions = json.loads(review_decisions.read_text(encoding="utf-8"))["relations"]
    eligible = []
    seen_relations: set[tuple[str, str]] = set()
    review_rows = []
    for row in replays:
        relation = (row["candidate_id"], row["target_repository"])
        if row["eligible"] and relation not in seen_relations:
            seen_relations.add(relation)
            key = "|".join(relation)
            decision = decisions.get(key, {"decision": "accept", "reason": "machine-strict reference contract"})
            review_rows.append({
                "candidate_id": row["candidate_id"],
                "target_repository": row["target_repository"],
                **decision,
            })
            if decision["decision"] == "accept":
                eligible.append(row)
    eligible = eligible[:limit]
    replayed_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "all-replays.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in replays),
        encoding="utf-8",
    )
    (output_dir / "adjudication.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in review_rows),
        encoding="utf-8",
    )
    labels = []
    for index, row in enumerate(eligible, 1):
        case_id = f"formal-e2-{index:03d}"
        evidence_dir = output_dir / "evidence" / case_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        contract = {**row, "case_id": case_id, "replayed_at": replayed_at}
        (evidence_dir / "contract.json").write_text(
            json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        exits = {"A0": 0, "A1": 1, "A2": 0}
        (evidence_dir / "run-results.tsv").write_text(
            "arm\texit_code\tresult\tsource_token_count\ttarget_token_count\n"
            + f"A0\t0\tpass\t{row['selected_counts']['source_base']}\t{row['selected_counts']['target_base']}\n"
            + f"A1\t1\tfail\t{row['selected_counts']['source_head']}\t{row['selected_counts']['target_base']}\n"
            + f"A2\t0\tpass\t{row['selected_counts']['source_head']}\t{row['selected_counts']['target_head']}\n",
            encoding="utf-8",
        )
        labels.append({
            "schema_version": "1.0",
            "case_id": case_id,
            "candidate_id": row["candidate_id"],
            "source_change_family": f"opendev-change-{row['source_change']}-opening",
            "source_repository": row["source_repository"],
            "target_repositories": [row["target_repository"]],
            "target_change": row["target_change"],
            "mechanism": f"removed reference surface: {row['contract_token']} ({row['contract_mode']})",
            "repair_origin": "maintainer",
            "primary_result_channel": "structured_reference_contract",
            "arms": row["arms"],
            "same_command_all_arms": True,
            "a1_failure_signature": f"dangling target reference to removed source token {row['contract_token']}",
            "a2_failure_signature_present": False,
            "revealed_at": row["revealed_at"],
            "replayed_at": replayed_at,
            "evidence_path": str(evidence_dir / "contract.json"),
            "scope_note": "Executable bounded source/consumer reference-surface contract; not a full project build.",
        })
    (output_dir / "labels.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in labels),
        encoding="utf-8",
    )
    metrics = {
        "schema_version": "1.0",
        "proposal_count": len(proposals),
        "replay_count": len(replays),
        "strict_direction_count": len(seen_relations),
        "adjudicated_rejection_count": sum(row["decision"] == "reject" for row in review_rows),
        "selected_label_count": len(labels),
        "requested_label_count": limit,
        "all_selected_strict": all(row["arms"] == {"A0": "pass", "A1": "fail", "A2": "pass"} for row in labels),
        "full_project_build_claimed": False,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-events", type=Path, required=True)
    parser.add_argument("--target-metadata", type=Path, required=True)
    parser.add_argument("--source-patch-dir", type=Path, required=True)
    parser.add_argument("--target-patch-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--review-decisions", type=Path)
    args = parser.parse_args()
    metrics = run(
        args.source_events, args.target_metadata, args.source_patch_dir,
        args.target_patch_dir, args.output_dir, args.workers, args.limit,
        args.review_decisions,
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if metrics["selected_label_count"] == args.limit else 1


if __name__ == "__main__":
    raise SystemExit(main())
