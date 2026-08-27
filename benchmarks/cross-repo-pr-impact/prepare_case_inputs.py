#!/usr/bin/env python3
"""Download and unpack the source patch and pre-cutoff candidate repositories."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
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


def code_only_diff(payload: bytes) -> bytes:
    """Remove mail-patch metadata while preserving the complete code diff."""

    markers = (b"diff --git ", b"diff -urN ")
    offsets = [payload.find(marker) for marker in markers]
    offsets = [offset for offset in offsets if offset >= 0]
    if not offsets:
        raise ValueError("downloaded patch does not contain a code-diff boundary")
    return payload[min(offsets):]


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
        bundle.extractall(destination, filter=code_snapshot_filter)
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


def code_snapshot_filter(
    member: tarfile.TarInfo, destination: str
) -> tarfile.TarInfo | None:
    """Apply the safe data filter and omit unsafe links/special entries."""

    try:
        return tarfile.data_filter(member, destination)
    except tarfile.FilterError:
        return None


def cached_archive(
    repository: str,
    snapshot: dict[str, Any],
    archive_cache: Path,
) -> Path:
    repository_dir = archive_cache / repository.replace("/", "__")
    repository_dir.mkdir(parents=True, exist_ok=True)
    archive = repository_dir / f"{snapshot['commit']}.tar.gz"
    if archive.exists():
        return archive
    partial = repository_dir / f".{snapshot['commit']}.tar.gz.part"
    download(snapshot["archive_url"], partial)
    partial.replace(archive)
    return archive


def cache_case_archives(
    snapshot: dict[str, Any], archive_cache: Path, workers: int = 1
) -> int:
    available = [
        repository
        for repository in snapshot["repositories"]
        if repository["status"] == "available"
    ]

    def cache_repository(repository: dict[str, Any]) -> None:
        archive = cached_archive(repository["repository"], repository, archive_cache)
        try:
            with tarfile.open(archive, "r:gz") as bundle:
                if bundle.next() is None:
                    raise tarfile.ReadError("empty archive")
        except (OSError, tarfile.TarError):
            archive.unlink(missing_ok=True)
            raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(cache_repository, available))
    return len(available)


def prepare(
    case_id: str,
    output_root: Path,
    inputs: dict[str, Any],
    snapshots: dict[str, Any],
    archive_cache: Path | None = None,
    workers: int = 1,
) -> None:
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
                payload = code_only_diff(payload)
            source_patch.write_bytes(payload)

        repositories_root = staging / "repositories"
        repositories_root.mkdir()
        available_repositories = [
            repository
            for repository in snapshot["repositories"]
            if repository["status"] == "available"
        ]

        def prepare_repository(repository: dict[str, Any]) -> None:
            repository_path = repositories_root / repository["repository"].replace("/", "__")
            if archive_cache is not None:
                archive = cached_archive(
                    repository["repository"], repository, archive_cache
                )
                extract_archive(archive, repository_path)
            else:
                with tempfile.TemporaryDirectory(prefix="marshal-repository-") as temp_dir:
                    archive = Path(temp_dir) / "repository.tar.gz"
                    download(repository["archive_url"], archive)
                    extract_archive(archive, repository_path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(prepare_repository, available_repositories))

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
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dataset-dir", type=Path, default=ROOT)
    parser.add_argument("--archive-cache", type=Path)
    parser.add_argument("--archives-only", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
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
    if args.archive_cache:
        args.archive_cache.mkdir(parents=True, exist_ok=True)
    if args.archives_only:
        if args.archive_cache is None:
            raise SystemExit("--archives-only requires --archive-cache")
        counts = {
            case_id: cache_case_archives(snapshots[case_id], args.archive_cache, args.workers)
            for case_id in args.case_ids
        }
        print(json.dumps({
            "cached_cases": args.case_ids,
            "available_archives": counts,
            "archive_cache": str(args.archive_cache.resolve()),
            "workers": args.workers,
        }, indent=2, ensure_ascii=False))
        return 0
    if args.output_dir is None:
        raise SystemExit("--output-dir is required unless --archives-only is used")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for case_id in args.case_ids:
        prepare(
            case_id,
            args.output_dir,
            inputs,
            snapshots,
            args.archive_cache,
            args.workers,
        )
    print(json.dumps({
        "prepared_cases": args.case_ids,
        "output_directory": str(args.output_dir.resolve()),
        "archive_cache": str(args.archive_cache.resolve()) if args.archive_cache else None,
        "workers": args.workers,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
