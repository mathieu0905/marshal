#!/usr/bin/env python3
"""Download and unpack the source patch and pre-cutoff candidate repositories."""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "marshal-evaluation-preparer"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response, destination.open(
                "wb"
            ) as output:
                shutil.copyfileobj(response, output)
            return
        except (urllib.error.URLError, TimeoutError):
            destination.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def extract_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as bundle:
        bundle.extractall(destination, filter="data")
    children = list(destination.iterdir())
    if len(children) == 1 and children[0].is_dir():
        wrapper = children[0]
        with tempfile.TemporaryDirectory(
            prefix=f".{destination.name}-wrapper-",
            dir=destination.parent,
        ) as temporary_dir:
            relocated = Path(temporary_dir) / "wrapper"
            wrapper.rename(relocated)
            for child in relocated.iterdir():
                shutil.move(str(child), destination / child.name)


def prepare(case_id: str, output_root: Path, inputs: dict[str, Any], snapshots: dict[str, Any]) -> None:
    item = inputs[case_id]
    snapshot = snapshots[case_id]
    destination = output_root / case_id
    if destination.exists():
        raise RuntimeError(f"output already exists: {destination}")
    with tempfile.TemporaryDirectory(prefix=f".{case_id}-", dir=output_root) as staging_dir:
        staging = Path(staging_dir)
        source_patch = staging / "source.patch"
        with tempfile.TemporaryDirectory(prefix="marshal-source-patch-") as temp_dir:
            encoded = Path(temp_dir) / "source-patch-response"
            download(item["source"]["patch_url"], encoded)
            payload = encoded.read_bytes()
            if item["source"]["host"] == "review.opendev.org":
                payload = base64.b64decode(payload)
            source_patch.write_bytes(payload)

        repositories_root = staging / "repositories"
        repositories_root.mkdir()
        for repository in snapshot["repositories"]:
            if repository["status"] != "available":
                continue
            repository_path = repositories_root / repository["repository"].replace("/", "__")
            with tempfile.TemporaryDirectory(prefix="marshal-repository-") as temp_dir:
                archive = Path(temp_dir) / "repository.tar.gz"
                download(repository["archive_url"], archive)
                extract_archive(archive, repository_path)

        (staging / "input.json").write_text(
            json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (staging / "repository-snapshots.json").write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        staging.rename(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_ids", nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    inputs = {
        item["case_id"]: item for item in read_jsonl(args.dataset_dir / "inputs.jsonl")
    }
    snapshots = {
        item["case_id"]: item
        for item in read_jsonl(args.dataset_dir / "repository-snapshots.jsonl")
    }
    unknown = sorted(set(args.case_ids) - set(inputs))
    if unknown:
        raise SystemExit(f"unknown case IDs: {', '.join(unknown)}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for case_id in args.case_ids:
        prepare(case_id, args.output_dir, inputs, snapshots)
    print(json.dumps({
        "prepared_cases": args.case_ids,
        "output_directory": str(args.output_dir.resolve()),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
