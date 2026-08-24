#!/usr/bin/env python3
"""Collect a complete direct-link frame across multiple implementation repositories."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
from pathlib import Path
from typing import Any

from collect_github_spec_candidates import gh_api
from collect_opendev import ROOT


SEARCH_DELAY_SECONDS = 2.1
ECOSYSTEMS = {
    "ethereum": {
        "source": "ethereum/EIPs",
        "targets": [
            "ChainSafe/lodestar",
            "Consensys/teku",
            "NethermindEth/nethermind",
            "OffchainLabs/prysm",
            "besu-eth/besu",
            "erigontech/erigon",
            "ethereum/execution-specs",
            "ethereum/go-ethereum",
            "sigp/lighthouse",
            "status-im/nimbus-eth2",
        ],
    },
    "kubernetes": {
        "source": "kubernetes/enhancements",
        "targets": [
            "kubernetes/kubernetes",
            "kubernetes-sigs/gateway-api",
        ],
    },
    "opentelemetry": {
        "source": "open-telemetry/opentelemetry-specification",
        "targets": [
            "open-telemetry/opentelemetry-cpp",
            "open-telemetry/opentelemetry-dotnet",
            "open-telemetry/opentelemetry-erlang",
            "open-telemetry/opentelemetry-go",
            "open-telemetry/opentelemetry-java",
            "open-telemetry/opentelemetry-js",
            "open-telemetry/opentelemetry-php",
            "open-telemetry/opentelemetry-python",
            "open-telemetry/opentelemetry-rust",
            "open-telemetry/opentelemetry-swift",
        ],
    },
    "opencontainers-image": {
        "source": "opencontainers/image-spec",
        "targets": [
            "containerd/containerd",
            "containers/crun",
            "opencontainers/runc",
        ],
    },
    "opencontainers-runtime": {
        "source": "opencontainers/runtime-spec",
        "targets": [
            "containerd/containerd",
            "containers/crun",
            "opencontainers/runc",
        ],
    },
    "python": {
        "source": "python/peps",
        "targets": [
            "pypa/pip",
            "pypa/setuptools",
            "python/cpython",
            "python/mypy",
            "python/typeshed",
            "python/typing",
            "python/typing_extensions",
        ],
    },
    "rust": {
        "source": "rust-lang/rfcs",
        "targets": [
            "rust-lang/cargo",
            "rust-lang/chalk",
            "rust-lang/miri",
            "rust-lang/polonius",
            "rust-lang/rust",
            "rust-lang/rust-analyzer",
            "rust-lang/rust-clippy",
            "rust-lang/rustfmt",
        ],
    },
}


def search_target(source: str, target: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = f'repo:{target} is:pr is:merged in:body "github.com/{source}/pull/"'
    items = []
    total_count = 0
    incomplete_results = False
    for page in range(1, 11):
        payload = gh_api("search/issues", {
            "q": query,
            "per_page": "100",
            "page": str(page),
            "sort": "created",
            "order": "asc",
        })
        time.sleep(SEARCH_DELAY_SECONDS)
        total_count = int(payload["total_count"])
        incomplete_results = incomplete_results or bool(payload["incomplete_results"])
        items.extend(payload["items"])
        if len(items) >= min(total_count, 1000) or not payload["items"]:
            break
    return items, {
        "source_repository": source,
        "target_repository": target,
        "query": query,
        "total_count": total_count,
        "incomplete_results": incomplete_results,
        "items_fetched": len(items),
        "github_search_cap": 1000,
        "truncated": incomplete_results or total_count > 1000,
    }


def linked_sources(body: str, source: str) -> list[int]:
    pattern = re.compile(
        rf"https?://github\.com/{re.escape(source)}/pull/(\d+)",
        re.IGNORECASE,
    )
    return sorted({int(match) for match in pattern.findall(body)})


def collect() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    searches = []
    for ecosystem, config in ECOSYSTEMS.items():
        source = config["source"]
        for target in config["targets"]:
            items, metadata = search_target(source, target)
            metadata["ecosystem"] = ecosystem
            searches.append(metadata)
            for item in items:
                body = item.get("body") or ""
                source_numbers = linked_sources(body, source)
                for source_number in source_numbers:
                    rows.append({
                        "ecosystem": ecosystem,
                        "relation_family": "specification_implementation",
                        "source_repository": source,
                        "source_pull_request": source_number,
                        "target_repository": target,
                        "target_pull_request": int(item["number"]),
                        "target_url": item["html_url"],
                        "target_title": item["title"],
                        "target_created_at": item["created_at"],
                        "target_updated_at": item["updated_at"],
                        "source_links_in_target_body": source_numbers,
                        "multiple_source_links": len(source_numbers) > 1,
                        "target_body": body,
                    })
    rows.sort(key=lambda item: (
        item["ecosystem"],
        item["source_repository"],
        item["source_pull_request"],
        item["target_repository"],
        item["target_pull_request"],
    ))
    searches.sort(key=lambda item: (item["ecosystem"], item["target_repository"]))
    return rows, searches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "candidates" / "github-multi-target-search-frame.jsonl",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=ROOT / "candidates" / "github-multi-target-search-metadata.json",
    )
    args = parser.parse_args()
    rows, searches = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    args.metadata.write_text(json.dumps({
        "schema_version": "1.0",
        "observed_at": dt.datetime.now(dt.UTC).isoformat(),
        "search_order": "created ascending",
        "searches": searches,
        "summary": {
            "searches": len(searches),
            "rows": len(rows),
            "unique_source_pull_requests": len({
                (row["source_repository"], row["source_pull_request"])
                for row in rows
            }),
            "directed_repository_relations": len({
                (row["source_repository"], row["target_repository"])
                for row in rows
            }),
            "truncated_searches": sum(item["truncated"] for item in searches),
        },
        "limitations": (
            "只覆盖目标 PR 正文中的完整源 PR 链接。搜索命中是待复核候选，"
            "不自动构成因果标签。"
        ),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "metadata": str(args.metadata),
        "rows": len(rows),
        "unique_source_pull_requests": len({
            (row["source_repository"], row["source_pull_request"])
            for row in rows
        }),
        "directed_repository_relations": len({
            (row["source_repository"], row["target_repository"])
            for row in rows
        }),
        "truncated_searches": sum(item["truncated"] for item in searches),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
