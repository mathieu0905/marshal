#!/usr/bin/env python3
"""Build label-independent OpenDev catalogs before formal-E2 label review."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from build_e2_candidate_catalogs import (
    OPENSTACK_CATALOG_CUTOFF,
    OPENSTACK_PROJECTS_URL,
    OPENSTACK_REQUIREMENTS_COMMIT,
    parse_openstack_projects,
)


ROOT = Path(__file__).resolve().parent
OPENSTACK_SNAPSHOT = ROOT / "results/e2-candidate-catalog-build-2026-08-25/sources/openstack-requirements-projects.txt"
STARLINGX_MANIFEST_URL = "https://opendev.org/starlingx/manifest/raw/branch/master/default.xml"


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "marshal-formal-e2-catalog-builder"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def parse_starlingx_manifest(text: str) -> list[str]:
    root = ET.fromstring(text)
    repositories = {"starlingx/manifest"}
    for project in root.findall("project"):
        if project.get("remote") != "starlingx":
            continue
        name = project.get("name")
        if not name:
            raise ValueError("StarlingX manifest project lacks name")
        if name.endswith(".git"):
            name = name[:-4]
        repositories.add(f"starlingx/{name}")
    if len(repositories) < 2:
        raise ValueError("StarlingX manifest produced no reusable project catalog")
    return sorted(repositories)


def build(openstack_text: str, starlingx_text: str, created_at: str) -> dict[str, Any]:
    openstack = sorted(set(parse_openstack_projects(openstack_text)) | {"openstack/requirements"})
    starlingx = parse_starlingx_manifest(starlingx_text)
    return {
        "schema_version": "1.0",
        "catalogs": {
            "formal-openstack-global-requirements-2026-08-26": {
                "catalog_id": "formal-openstack-global-requirements-2026-08-26",
                "catalog_status": "constructed_before_label_review",
                "membership_reads_labels": False,
                "reused_across_source_events": True,
                "selection_rule": "All repositories in openstack/requirements projects.txt at the recorded revision, plus the coordination repository itself.",
                "membership_source": {
                    "kind": "project_build_orchestration",
                    "repository": "openstack/requirements",
                    "commit": OPENSTACK_REQUIREMENTS_COMMIT,
                    "url": OPENSTACK_PROJECTS_URL,
                    "catalog_cutoff": OPENSTACK_CATALOG_CUTOFF,
                    "snapshot": "sources/openstack-requirements-projects.txt",
                },
                "constructed_at": created_at,
                "repository_host": "opendev.org",
                "repositories": openstack,
            },
            "formal-starlingx-manifest-2026-08-26": {
                "catalog_id": "formal-starlingx-manifest-2026-08-26",
                "catalog_status": "constructed_before_label_review",
                "membership_reads_labels": False,
                "reused_across_source_events": True,
                "selection_rule": "All repositories using the official starlingx remote in starlingx/manifest default.xml, plus the manifest repository.",
                "membership_source": {
                    "kind": "project_build_manifest",
                    "repository": "starlingx/manifest",
                    "branch": "master",
                    "url": STARLINGX_MANIFEST_URL,
                    "catalog_cutoff": created_at,
                    "snapshot": "sources/starlingx-default.xml",
                },
                "constructed_at": created_at,
                "repository_host": "opendev.org",
                "repositories": starlingx,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openstack-projects", type=Path, default=OPENSTACK_SNAPSHOT)
    parser.add_argument("--starlingx-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    openstack_text = args.openstack_projects.read_text(encoding="utf-8")
    starlingx_text = (
        args.starlingx_manifest.read_text(encoding="utf-8")
        if args.starlingx_manifest
        else fetch_text(STARLINGX_MANIFEST_URL)
    )
    created_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    bundle = build(openstack_text, starlingx_text, created_at)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sources").mkdir(exist_ok=True)
    (args.output_dir / "sources/openstack-requirements-projects.txt").write_text(openstack_text, encoding="utf-8")
    (args.output_dir / "sources/starlingx-default.xml").write_text(starlingx_text, encoding="utf-8")
    (args.output_dir / "candidate-repositories.json").write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = {
        "schema_version": "1.0",
        "catalog_count": len(bundle["catalogs"]),
        "repository_counts": {key: len(value["repositories"]) for key, value in bundle["catalogs"].items()},
        "membership_reads_labels": False,
        "constructed_before_label_review": True,
        "network_used": args.starlingx_manifest is None,
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
