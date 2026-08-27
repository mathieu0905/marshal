#!/usr/bin/env python3
"""Build label-independent candidate catalogs for strict-E2 cases.

The builder is intentionally incremental.  A catalog is emitted only when a
repository-owned project/governance/build-orchestration source defines membership
without consulting E2 targets.  Target labels are read afterward for coverage
auditing and never appended to the catalog.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
E2_INDEX = ROOT / "results" / "final-e2-dataset-50-2026-08-25" / "final-index.jsonl"
OPENSTACK_REQUIREMENTS_COMMIT = "377f367109c44aaaefc73aa8776e314810e3ad37"
OPENSTACK_CATALOG_ID = "openstack-global-requirements-2026-08-11"
OPENSTACK_PROJECTS_URL = (
    "https://raw.githubusercontent.com/openstack/requirements/"
    f"{OPENSTACK_REQUIREMENTS_COMMIT}/projects.txt"
)
OPENSTACK_CATALOG_CUTOFF = "2026-08-11T17:17:39Z"
OPENSTACK_CASE_CUTOFFS = {
    "e2-001": "2026-08-15T12:56:38Z",
    "e2-006": "2026-08-12T00:46:17Z",
}
GITHUB_ORGANIZATIONS = {
    "jcabi": {
        "catalog_id": "jcabi-github-organization-2026-08-25",
        "case_cutoffs": {
            # The causal deletion first existed in the integration commit produced
            # while merging jcabi/jcabi-aspects#336.
            "e2-002": "2022-09-23T04:31:48Z",
            "e2-003": "2022-09-23T04:31:48Z",
        },
        "input_spec_opening_cutoff_conformant": False,
        "cutoff_policy": "causal_integration_commit_first_public_time_after_pr_creation",
    },
    "assertj": {
        "catalog_id": "assertj-github-organization-2026-08-25",
        # GitHub resolves the historical assertj/assertj-core slug to the current
        # assertj/assertj name.  Rewrite that organization-directory entry to the
        # name visible at these 2022 case cutoffs; this is derived from the visible
        # source repository identity, not either hidden target label.
        "historical_name_rewrites": {
            "assertj/assertj": "assertj/assertj-core",
        },
        "case_cutoffs": {
            # Earliest recovered head of assertj/assertj-core#2477 existed when
            # the pull request was first created; a later force push is excluded.
            "e2-018": "2022-01-29T12:04:35Z",
            "e2-019": "2022-01-29T12:04:35Z",
        },
        "input_spec_opening_cutoff_conformant": True,
        "cutoff_policy": "pull_request_creation_with_recovered_pre_force_push_head",
    },
}
H2_FSE_CATALOGS = {
    "h2-1.4.200": {
        "catalog_id": "h2-fse-1.4.200-source-family-2026-08-25",
        "default_source": ROOT / "workstreams" / "h2-1.4.200-fse-extension" / "candidate-frame.jsonl",
        "repository_field": ("repository_resolution", "canonical_repository"),
        "case_cutoffs": {
            "e2-034": "2019-10-01T11:41:21Z",
            "e2-035": "2019-10-01T11:41:21Z",
            "e2-038": "2019-09-01T13:45:07Z",
        },
        "source_description": (
            "All canonical repository roots in the FSE H2 1.4.200 source-transition "
            "frame, including both the pre-existing MVCC rows and every audited "
            "1.4.200 extension row."
        ),
        "input_spec_opening_cutoff_conformant": True,
        "cutoff_policy": "pull_request_creation_with_causal_commit_already_present",
    },
    "h2-2.0.202": {
        "catalog_id": "h2-fse-2.0.202-source-family-2026-08-25",
        "default_source": ROOT / "workstreams" / "h2-2.0-fse" / "candidate-root-audit.jsonl",
        "repository_field": ("root_repository",),
        "case_cutoffs": {
            # The causal commit entered PR 2297 after its opening force-push state.
            # Development inputs therefore stop at the commit's first public time.
            "e2-036": "2019-12-01T14:50:19Z",
            "e2-037": "2019-12-01T14:50:19Z",
        },
        "source_description": (
            "All 36 canonical repository roots in the exhaustively folded FSE H2 "
            "2.0.202 candidate-root audit."
        ),
        "input_spec_opening_cutoff_conformant": False,
        "cutoff_policy": "causal_commit_first_public_time_after_pr_creation",
    },
}
BUMP_COMPONENT_CATALOGS = {
    "checkstyle": {
        "catalog_id": "checkstyle-bump-source-family-2026-08-25",
        "default_source": ROOT / "workstreams" / "checkstyle" / "bump-candidate-frame.jsonl",
        "source_component": "com.puppycrawl.tools:checkstyle",
        "case_cutoffs": {
            # PR 12737 was opened months before the recovered one-commit head that
            # contains the causal FinalClass change. Development inputs stop at that
            # head commit's first recorded public timestamp.
            "e2-023": "2023-06-27T16:38:11Z",
            "e2-024": "2023-06-27T16:38:11Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-023": False,
            "e2-024": False,
        },
        "cutoff_policy": {
            "e2-023": "causal_pull_request_head_first_public_time_after_pr_creation",
            "e2-024": "causal_pull_request_head_first_public_time_after_pr_creation",
        },
    },
    "mockito": {
        "catalog_id": "mockito-bump-source-family-2026-08-25",
        "default_source": ROOT / "workstreams" / "mockito" / "bump-candidate-frame.jsonl",
        "source_component": "org.mockito:mockito-core",
        "case_cutoffs": {
            "e2-025": "2016-05-16T19:45:48Z",
            "e2-026": "2021-09-01T17:26:27Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-025": False,
            "e2-026": True,
        },
        "cutoff_policy": {
            "e2-025": "causal_pull_request_head_first_public_time_after_pr_creation",
            "e2-026": "pull_request_creation_with_causal_head_already_present",
        },
    },
    "commons-io": {
        "catalog_id": "commons-io-bump-source-family-2026-08-25",
        "default_source": ROOT / "workstreams" / "commons-io" / "bump-candidate-frame.jsonl",
        "source_component": "commons-io:commons-io",
        "case_cutoffs": {
            "e2-021": "2021-01-11T06:45:34Z",
            "e2-022": "2023-04-16T16:08:18Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-021": False,
            "e2-022": False,
        },
        "cutoff_policy": {
            "e2-021": "causal_direct_commit_public_timestamp_no_source_pr",
            "e2-022": "causal_direct_commit_public_timestamp_no_source_pr",
        },
    },
    "slf4j": {
        "catalog_id": "slf4j-screening-source-family-2026-08-25",
        "default_source": ROOT / "workstreams" / "slf4j-fourth-root" / "candidate-frame.jsonl",
        "source_component": "org.slf4j:slf4j-api",
        "repository_field": ("root_repository",),
        "membership_kind": "local_dependency_screening_frame",
        "dataset": "prior BUMP and FSE screening",
        "source_revision": "slf4j-fourth-root candidate frame 2026-08-25",
        "snapshot": "sources/slf4j-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All six independent consumer roots retained in the complete local "
            "SLF4J fourth-root screening frame, including positive, bounded-negative, "
            "unknown-rejected, and different-transition rows; final E2 target fields "
            "are not read while constructing membership."
        ),
        "case_cutoffs": {
            "e2-004": "2022-08-20T19:04:05Z",
            "e2-005": "2022-08-20T19:04:05Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-004": False,
            "e2-005": False,
        },
        "cutoff_policy": {
            "e2-004": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
            "e2-005": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
        },
    },
    "jackson": {
        "catalog_id": "jackson-fse-component-family-2026-08-25",
        "default_source": ROOT / "candidates" / "fse2024-behavioral-breakage-frame.jsonl",
        "source_component": "com.fasterxml.jackson.*",
        "membership_kind": "external_component_coordinate_slice",
        "dataset": "FSE 2024 behavioral breakage frame",
        "source_revision": "10.5281/zenodo.10678852",
        "snapshot": "sources/jackson-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All 18 canonical consumer roots in the complete Jackson-coordinate "
            "slice of the FSE 2024 behavioral breakage frame; every coordinate whose "
            "group starts with com.fasterxml.jackson is included before labels are read."
        ),
        "case_cutoffs": {
            "e2-016": "2020-04-25T23:57:08Z",
            "e2-042": "2020-04-25T23:57:08Z",
            "e2-047": "2021-09-30T21:38:57Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-016": False,
            "e2-042": False,
            "e2-047": False,
        },
        "cutoff_policy": {
            "e2-016": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
            "e2-042": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
            "e2-047": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
        },
    },
    "snakeyaml": {
        "catalog_id": "snakeyaml-project-package-frame-2026-08-25",
        "default_source": ROOT / "workstreams" / "snakeyaml" / "project-package-candidate-frame.jsonl",
        "source_component": "org.yaml:snakeyaml",
        "membership_kind": "local_dependency_screening_frame",
        "dataset": "SnakeYAML project-package screening",
        "source_revision": "results/snakeyaml-project-package-screening-2026-08-24/summary.json",
        "snapshot": "sources/snakeyaml-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All four consumer roots in the complete SnakeYAML project-package "
            "screening frame, including both strict-E2 positives and both bounded "
            "native-check passes; no row is filtered using the final E2 index."
        ),
        "case_cutoffs": {
            "e2-011": "2023-02-26T11:07:37Z",
            "e2-012": "2023-02-26T11:07:37Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-011": False,
            "e2-012": False,
        },
        "cutoff_policy": {
            "e2-011": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
            "e2-012": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
        },
    },
    "plexus-utils": {
        "catalog_id": "plexus-utils-project-package-frame-2026-08-25",
        "default_source": ROOT / "workstreams" / "plexus-utils" / "project-package-candidate-frame.jsonl",
        "source_component": "org.codehaus.plexus:plexus-utils",
        "membership_kind": "local_dependency_screening_frame",
        "dataset": "Plexus Utils project-package screening",
        "source_revision": "results/plexus-utils-project-package-screening-2026-08-24/summary.json",
        "snapshot": "sources/plexus-utils-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All four consumer roots in the complete Plexus Utils project-package "
            "screening frame, including both strict-E2 positives and both bounded "
            "native-check passes; no row is filtered using the final E2 index."
        ),
        "case_cutoffs": {
            "e2-013": "2023-05-22T15:15:06Z",
            "e2-014": "2023-05-22T15:15:06Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-013": False,
            "e2-014": False,
        },
        "cutoff_policy": {
            "e2-013": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
            "e2-014": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
        },
    },
    "terser": {
        "catalog_id": "terser-project-package-frame-2026-08-25",
        "default_source": ROOT / "workstreams" / "terser" / "project-package-candidate-frame.jsonl",
        "source_component": "terser",
        "membership_kind": "local_dependency_screening_frame",
        "dataset": "Terser 4.3 project-package repeated screening",
        "source_revision": "results/terser-unified-430-repetitions-2026-08-24/summary.json",
        "snapshot": "sources/terser-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All four roots in the complete executed Terser 4.3 project-package "
            "frame, including two strict-E2 positives, the rejected process-exit "
            "case, and the bounded native-check pass; final E2 labels are not used "
            "to filter membership."
        ),
        "case_cutoffs": {
            "e2-009": "2019-08-19T21:20:06Z",
            "e2-010": "2019-08-19T21:20:06Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-009": True,
            "e2-010": True,
        },
        "cutoff_policy": {
            "e2-009": "pull_request_creation_with_causal_head_already_present",
            "e2-010": "pull_request_creation_with_causal_head_already_present",
        },
    },
    "fse-assertj-derby": {
        "catalog_id": "fse-assertj-derby-component-family-2026-08-25",
        "default_source": ROOT / "workstreams" / "fse-assertj-derby" / "component-family-candidate-frame.jsonl",
        "source_component": "org.assertj:assertj-core + org.apache.derby:derby",
        "membership_kind": "external_component_coordinate_union",
        "dataset": "FSE 2024 behavioral breakage frame",
        "source_revision": "10.5281/zenodo.10678852",
        "snapshot": "sources/fse-assertj-derby-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All 16 canonical consumer roots in the union of the complete AssertJ "
            "Core and Apache Derby coordinate slices of the FSE frame; redirects "
            "and duplicate roots are folded before final E2 labels are read."
        ),
        "known_unavailable_repositories": {
            "ralscha/wampspring": "GitHub repository API returned 404 during canonical-root resolution on 2026-08-25",
            "stratosphere/stratosphere": "GitHub repository API returned 404 during canonical-root resolution on 2026-08-25",
        },
        "case_cutoffs": {
            "e2-020": "2021-01-24T05:06:38Z",
            "e2-040": "2019-03-10T23:36:25Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-020": False,
            "e2-040": False,
        },
        "cutoff_policy": {
            "e2-020": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
            "e2-040": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
        },
    },
    "fse-java-compat": {
        "catalog_id": "fse-java-compat-component-family-2026-08-25",
        "default_source": ROOT / "workstreams" / "fse-java-compat" / "component-family-candidate-frame.jsonl",
        "source_component": (
            "org.apache.logging.log4j + io.swagger.core.v3:swagger-models + "
            "com.neovisionaries:nv-i18n + org.ow2.asm + io.micrometer"
        ),
        "membership_kind": "external_component_coordinate_union",
        "dataset": "FSE 2024 behavioral breakage frame",
        "source_revision": "10.5281/zenodo.10678852",
        "snapshot": "sources/fse-java-compat-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All 10 canonical consumer roots in the union of the complete Log4j, "
            "Swagger Models, nv-i18n, ASM, and Micrometer coordinate slices of the "
            "FSE frame; repository redirects and duplicate component rows are folded "
            "before final E2 labels are read."
        ),
        "case_cutoffs": {
            "e2-039": "2021-12-09T18:26:12Z",
            "e2-041": "2021-06-21T12:49:36Z",
            "e2-048": "2021-03-18T16:41:33Z",
            "e2-049": "2021-11-22T18:23:59Z",
            "e2-050": "2022-05-11T22:37:17Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-039": False,
            "e2-041": True,
            "e2-048": False,
            "e2-049": True,
            "e2-050": False,
        },
        "cutoff_policy": {
            "e2-039": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
            "e2-041": "pull_request_creation_with_causal_head_already_present",
            "e2-048": "causal_pull_request_commit_first_public_time_after_pr_creation",
            "e2-049": "merge_request_creation_with_causal_head_already_present",
            "e2-050": "causal_direct_commit_diff_with_release_publication_cutoff_no_source_pr",
        },
    },
    "crater-linked-fixes": {
        "catalog_id": "crater-linked-fix-frame-2026-08-25",
        "default_source": ROOT / "candidates" / "crater-linked-fix-candidates.jsonl",
        "source_component": "rust-lang/rust compiler pull requests",
        "repository_field": ("fix", "repository"),
        "membership_kind": "local_crater_linked_fix_frame",
        "dataset": "20 Rust compiler Crater experiments with direct downstream-fix screening",
        "source_revision": "candidates/crater-linked-fix-candidates.jsonl",
        "snapshot": "sources/crater-linked-fixes-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All four downstream repositories in the complete direct-fix yield of "
            "the 20 audited Crater experiments; every retained fix candidate is "
            "included before the final E2 index is read."
        ),
        "case_cutoffs": {
            "e2-043": "2026-04-12T11:04:16Z",
            "e2-044": "2026-04-08T15:18:39Z",
            "e2-045": "2026-05-20T15:05:03Z",
            "e2-046": "2026-05-20T15:05:03Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-043": True,
            "e2-044": True,
            "e2-045": True,
            "e2-046": True,
        },
        "cutoff_policy": {
            "e2-043": "pull_request_creation_with_causal_head_already_present",
            "e2-044": "pull_request_creation_with_causal_head_already_present",
            "e2-045": "pull_request_creation_with_causal_head_already_present",
            "e2-046": "pull_request_creation_with_causal_head_already_present",
        },
    },
    "legacy-component-screening": {
        "catalog_id": "legacy-component-screening-union-2026-08-25",
        "default_source": ROOT / "workstreams" / "legacy-component-screening" / "candidate-frame.jsonl",
        "source_component": "11 legacy npm and JVM compatibility transitions",
        "membership_kind": "local_dependency_screening_union",
        "dataset": "Complete executed consumer frames retained by the legacy compatibility workstreams",
        "source_revision": "workstreams/legacy-component-screening/candidate-frame.jsonl",
        "snapshot": "sources/legacy-component-screening-candidate-frame.jsonl",
        "selection_rule": (
            "All 17 canonical consumer roots in the union of the complete executed "
            "frames for the 11 remaining legacy component transitions, including "
            "positive, diagnostic, compatible, rejected, and unavailable roots; "
            "the final E2 index is not read while constructing membership."
        ),
        "known_unavailable_repositories": {
            "Brightspace/images-to-variables": "Historical repository was deleted; no canonical GitHub archive is available at collection time",
            "loggur/react-redux-provide": "Historical repository was deleted; evidence is preserved by npm and Software Heritage rather than a live GitHub repository",
        },
        "case_snapshot_overrides": {
            "e2-028": {
                "loggur/react-redux-provide": {
                    "repository": "loggur/react-redux-provide",
                    "host": "registry.npmjs.org",
                    "status": "available",
                    "commit": "72bba55b6464ae2dfa060ecb04a3346e35d8bf04",
                    "committed_at": "2016-01-28T09:17:07Z",
                    "archive_url": "https://registry.npmjs.org/react-redux-provide/-/react-redux-provide-5.1.0.tgz",
                    "snapshot_source_kind": "npm_published_source_artifact",
                    "published_package": "react-redux-provide@5.1.0",
                    "provenance": (
                        "The npm registry version record names the deleted canonical "
                        "GitHub repository, records gitHead 72bba55b6464ae2dfa060ecb04a3346e35d8bf04, "
                        "and published this source artifact before the case cutoff."
                    ),
                },
            },
            "e2-030": {
                "Brightspace/images-to-variables": {
                    "repository": "Brightspace/images-to-variables",
                    "host": "github.com",
                    "status": "available",
                    "commit": "94da609777c4af78dc06bd9a0f773531ec0635e6",
                    "committed_at": "2014-12-05T16:12:24Z",
                    "archive_url": "https://github.com/omsmith/images-to-variables/archive/94da609777c4af78dc06bd9a0f773531ec0635e6.tar.gz",
                    "snapshot_source_kind": "preserved_git_history_fork",
                    "preservation_repository": "omsmith/images-to-variables",
                    "provenance": (
                        "The deleted canonical repository's complete pre-deletion history "
                        "is preserved by multiple historical forks. The omsmith fork retains "
                        "the exact v0.0.4 commit and tree before the case cutoff."
                    ),
                },
            },
        },
        "case_cutoffs": {
            "e2-007": "2016-02-01T16:35:49Z",
            "e2-008": "2014-08-29T21:48:00Z",
            "e2-015": "2022-03-27T02:31:02Z",
            "e2-017": "2022-06-28T22:04:37Z",
            "e2-027": "2022-08-28T17:27:02Z",
            "e2-028": "2016-02-01T18:14:47Z",
            "e2-029": "2016-08-05T04:12:19Z",
            "e2-030": "2015-01-27T01:08:57Z",
            "e2-031": "2018-03-16T19:58:59Z",
            "e2-032": "2014-02-13T19:57:44Z",
            "e2-033": "2016-01-05T23:45:05Z",
        },
        "input_spec_opening_cutoff_conformant": {
            "e2-007": False,
            "e2-008": False,
            "e2-015": False,
            "e2-017": False,
            "e2-027": False,
            "e2-028": False,
            "e2-029": False,
            "e2-030": False,
            "e2-031": False,
            "e2-032": False,
            "e2-033": False,
        },
        "cutoff_policy": {
            "e2-007": "causal_diff_with_release_publication_cutoff",
            "e2-008": "causal_direct_commit_diff_with_release_publication_cutoff",
            "e2-015": "causal_direct_commit_diff_with_release_publication_cutoff",
            "e2-017": "causal_direct_commit_diff_with_release_publication_cutoff",
            "e2-027": "causal_direct_commit_diff_with_release_publication_cutoff",
            "e2-028": "causal_direct_commit_diff_with_release_publication_cutoff",
            "e2-029": "causal_release_diff_with_release_publication_cutoff",
            "e2-030": "causal_direct_commit_diff_with_release_publication_cutoff",
            "e2-031": "causal_direct_commit_diff_with_release_publication_cutoff",
            "e2-032": "causal_direct_commit_diff_with_release_publication_cutoff",
            "e2-033": "causal_direct_commit_diff_with_release_publication_cutoff",
        },
    },
}
JACKSON_FSE_HINT_REPOSITORIES = {
    "sdl_dxa-web-application-java": "RWS/dxa-web-application-java",
    "wix_openrest4j": "wix-incubator/openrest4j",
    "opentripplanner_OpenTripPlanner": "opentripplanner/OpenTripPlanner",
    "internetitem_logback-elasticsearch-appender": "internetitem/logback-elasticsearch-appender",
    "cowtowncoder_ClusterMate": "cowtowncoder/ClusterMate",
    "santanusinha_json-rules": "santanusinha/json-rules",
    "corballis_json-fixtures": "corballis/json-fixtures",
    "wordnik_swagger-core": "swagger-api/swagger-core",
    "phonedeck_gcm4j": "phonedeck/gcm4j",
    "osiam_scim-schema": "osiam/scim-schema",
    "alexec_docker-java-orchestration": "alexec/docker-java-orchestration",
    "docker-java_docker-java": "docker-java/docker-java",
    "tamtam-chat_tamtam-bot-api": "tamtam-chat/tamtam-bot-api",
    "stackify_stackify-log-log4j2": "stackify/stackify-log-log4j2",
    "sualeh_SchemaCrawler": "SchemaCrawler/SchemaCrawler",
    "protostuff_protostuff-compiler": "protostuff/protostuff-compiler",
    "openscoring_openscoring": "openscoring/openscoring",
    "channelape_shopify-sdk": "ChannelApe/shopify-sdk",
}
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "marshal-e2-candidate-catalog-builder"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def fetch_github_org_snapshot(organization: str) -> dict[str, Any]:
    url = f"https://api.github.com/orgs/{organization}/repos?type=all&per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "marshal-e2-candidate-catalog-builder",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        rows = json.load(response)
    if len(rows) == 100:
        raise ValueError(
            f"{organization} repository response may be paginated; add pagination"
        )
    return {
        "organization": organization,
        "endpoint": url,
        "fetched_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "repositories": [{
            "full_name": row["full_name"],
            "private": row["private"],
            "fork": row["fork"],
            "archived": row["archived"],
            "created_at": row["created_at"],
        } for row in rows],
    }


def parse_github_org_snapshot(
    snapshot: dict[str, Any], organization: str
) -> list[str]:
    if snapshot.get("organization") != organization:
        raise ValueError(f"expected {organization} organization snapshot")
    repositories = []
    for row in snapshot.get("repositories", []):
        name = row.get("full_name", "")
        if not REPOSITORY.fullmatch(name) or not name.startswith(f"{organization}/"):
            raise ValueError(f"invalid {organization} repository: {name!r}")
        if row.get("private"):
            continue
        if row.get("fork"):
            continue
        repositories.append(
            GITHUB_ORGANIZATIONS[organization]
            .get("historical_name_rewrites", {})
            .get(name, name)
        )
    if len(repositories) != len(set(repositories)):
        raise ValueError(f"{organization} snapshot contains duplicate repositories")
    return sorted(repositories)


def parse_openstack_projects(text: str) -> list[str]:
    repositories = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if not REPOSITORY.fullmatch(value):
            raise ValueError(f"invalid projects.txt row {line_number}: {value!r}")
        repositories.append(value)
    if len(repositories) != len(set(repositories)):
        raise ValueError("projects.txt contains duplicate repositories")
    # The orchestration file enumerates governed consumers.  The coordination
    # repository itself is a candidate repair location for dependency additions.
    return sorted(set(repositories) | {"openstack/requirements"})


def nested_value(row: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = row
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"missing frame field {'.'.join(path)}")
        value = value[key]
    return value


def parse_source_family_frame(text: str, repository_field: tuple[str, ...]) -> list[str]:
    repositories = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        repository = nested_value(row, repository_field)
        if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
            raise ValueError(f"invalid frame repository at row {line_number}: {repository!r}")
        repositories.append(repository)
    if not repositories:
        raise ValueError("source-family frame is empty")
    return sorted(set(repositories))


def frame_snapshot_name(family: str) -> str:
    if family.endswith(("-bump", "-screening")):
        return f"sources/{family}-candidate-frame.jsonl"
    return f"sources/{family}-fse-source-family-frame.jsonl"


def parse_jackson_fse_component_frame(text: str) -> list[str]:
    repositories = []
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not row["dependency"]["coordinate"].startswith("com.fasterxml.jackson"):
            continue
        hint = row["client"]["repository_directory_hint"].split("\\", 1)[0]
        if hint not in JACKSON_FSE_HINT_REPOSITORIES:
            raise ValueError(f"unresolved Jackson FSE repository hint: {hint}")
        repositories.append(JACKSON_FSE_HINT_REPOSITORIES[hint])
    if not repositories:
        raise ValueError("Jackson FSE component slice is empty")
    return sorted(set(repositories))


def build_openstack_catalog(
    cases: list[dict[str, Any]], projects_text: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    repositories = parse_openstack_projects(projects_text)
    membership = set(repositories)
    case_by_id = {case["case_id"]: case for case in cases}
    case_ids = sorted(OPENSTACK_CASE_CUTOFFS)
    missing_cases = sorted(set(case_ids) - set(case_by_id))
    if missing_cases:
        raise ValueError(f"missing E2 cases: {missing_cases}")

    catalog = {
        "catalog_id": OPENSTACK_CATALOG_ID,
        "schema_version": "1.0",
        "catalog_status": "label_independent_reusable",
        "selection_rule": (
            "All repositories listed by openstack/requirements projects.txt at "
            f"{OPENSTACK_REQUIREMENTS_COMMIT}, plus openstack/requirements as the "
            "shared coordination repository."
        ),
        "membership_source": {
            "kind": "project_build_orchestration",
            "repository": "openstack/requirements",
            "commit": OPENSTACK_REQUIREMENTS_COMMIT,
            "path": "projects.txt",
            "url": OPENSTACK_PROJECTS_URL,
            "catalog_cutoff": OPENSTACK_CATALOG_CUTOFF,
        },
        "membership_reads_e2_targets": False,
        "repository_host": "opendev.org",
        "repositories": repositories,
    }
    assignments = [{
        "case_id": case_id,
        "candidate_repository_catalog": (
            f"candidate-repositories.json#{OPENSTACK_CATALOG_ID}"
        ),
        "observation_cutoff": OPENSTACK_CASE_CUTOFFS[case_id],
        "catalog_membership_cutoff": OPENSTACK_CATALOG_CUTOFF,
        "input_spec_opening_cutoff_conformant": True,
        "cutoff_policy": "first_review_creation_patchset_one",
        "assignment_basis": (
            "The source repository participates in the OpenStack global-requirements "
            "orchestration surface; assignment does not inspect target labels."
        ),
    } for case_id in case_ids]

    coverage_rows = []
    for case_id in case_ids:
        case = case_by_id[case_id]
        targets = sorted(case["target_repositories"])
        missing_targets = sorted(set(targets) - membership)
        coverage_rows.append({
            "case_id": case_id,
            "source_repository": case["source_repository"],
            "target_repositories": targets,
            "source_covered": case["source_repository"] in membership,
            "targets_covered": not missing_targets,
            "missing_targets": missing_targets,
            "non_target_candidate_count": len(membership - set(targets) - {case["source_repository"]}),
            "labels_read_after_membership_construction": True,
        })
    coverage = {
        "catalog_id": OPENSTACK_CATALOG_ID,
        "case_count": len(case_ids),
        "repository_count": len(repositories),
        "reused_across_cases": len(case_ids) > 1,
        "all_sources_covered": all(row["source_covered"] for row in coverage_rows),
        "all_targets_covered": all(row["targets_covered"] for row in coverage_rows),
        "formal_catalog_eligible": (
            len(case_ids) > 1
            and all(row["source_covered"] for row in coverage_rows)
            and all(row["targets_covered"] for row in coverage_rows)
            and all(row["non_target_candidate_count"] > 0 for row in coverage_rows)
        ),
        "cases": coverage_rows,
        "boundary": (
            "Catalog eligibility does not make inputs ready. Candidate repository "
            "commits still have to be resolved at each observation cutoff."
        ),
    }
    return catalog, assignments, coverage


def build_github_org_catalog(
    cases: list[dict[str, Any]], organization: str, snapshot: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    definition = GITHUB_ORGANIZATIONS[organization]
    repositories = parse_github_org_snapshot(snapshot, organization)
    rewrites = definition.get("historical_name_rewrites", {})
    repository_created_at = {
        rewrites.get(row["full_name"], row["full_name"]): row["created_at"]
        for row in snapshot.get("repositories", [])
        if not row.get("private") and not row.get("fork") and row.get("created_at")
    }
    membership = set(repositories)
    case_by_id = {case["case_id"]: case for case in cases}
    case_cutoffs = definition["case_cutoffs"]
    missing_cases = sorted(set(case_cutoffs) - set(case_by_id))
    if missing_cases:
        raise ValueError(f"missing E2 cases: {missing_cases}")
    fetched_at = snapshot["fetched_at"]
    catalog_id = definition["catalog_id"]
    catalog = {
        "catalog_id": catalog_id,
        "schema_version": "1.0",
        "catalog_status": "label_independent_reusable",
        "selection_rule": (
            f"All public, non-fork repositories returned by the GitHub {organization} "
            "organization repository directory at catalog construction time; archived "
            "repositories remain candidates. Repositories created after a case cutoff "
            "are retained in membership and resolved as not_created_by_cutoff."
        ),
        "membership_source": {
            "kind": "github_organization_directory",
            "organization": organization,
            "endpoint": snapshot["endpoint"],
            "catalog_cutoff": fetched_at,
            "snapshot": f"sources/{organization}-github-org-repositories.json",
            "historical_name_rewrites": definition.get(
                "historical_name_rewrites", {}
            ),
        },
        "membership_reads_e2_targets": False,
        "repository_host": "github.com",
        "repositories": repositories,
        "repository_created_at": repository_created_at,
    }
    assignments = [{
        "case_id": case_id,
        "candidate_repository_catalog": f"candidate-repositories.json#{catalog_id}",
        "observation_cutoff": case_cutoffs[case_id],
        "catalog_membership_cutoff": fetched_at,
        "input_spec_opening_cutoff_conformant": definition[
            "input_spec_opening_cutoff_conformant"
        ],
        "cutoff_policy": definition["cutoff_policy"],
        "assignment_basis": (
            f"The source repository belongs to the GitHub {organization} organization; "
            "assignment uses organization ownership and does not inspect target labels."
        ),
    } for case_id in sorted(case_cutoffs)]
    coverage_rows = []
    for case_id in sorted(case_cutoffs):
        case = case_by_id[case_id]
        targets = sorted(case["target_repositories"])
        missing_targets = sorted(set(targets) - membership)
        coverage_rows.append({
            "case_id": case_id,
            "source_repository": case["source_repository"],
            "target_repositories": targets,
            "source_covered": case["source_repository"] in membership,
            "targets_covered": not missing_targets,
            "missing_targets": missing_targets,
            "non_target_candidate_count": len(
                membership - set(targets) - {case["source_repository"]}
            ),
            "labels_read_after_membership_construction": True,
        })
    eligible = (
        len(case_cutoffs) > 1
        and all(row["source_covered"] for row in coverage_rows)
        and all(row["targets_covered"] for row in coverage_rows)
        and all(row["non_target_candidate_count"] > 0 for row in coverage_rows)
    )
    coverage = {
        "catalog_id": catalog_id,
        "case_count": len(case_cutoffs),
        "repository_count": len(repositories),
        "reused_across_cases": len(case_cutoffs) > 1,
        "all_sources_covered": all(row["source_covered"] for row in coverage_rows),
        "all_targets_covered": all(row["targets_covered"] for row in coverage_rows),
        "formal_catalog_eligible": eligible,
        "cases": coverage_rows,
        "boundary": (
            "Current organization membership is label-independent but retrospective: "
            "deleted or transferred repositories absent today cannot be recovered from "
            "this source. Cutoff snapshot resolution is still required."
        ),
    }
    return catalog, assignments, coverage


def build_h2_fse_catalog(
    cases: list[dict[str, Any]], family: str, frame_text: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    definition = H2_FSE_CATALOGS[family]
    repositories = parse_source_family_frame(
        frame_text, definition["repository_field"]
    )
    membership = set(repositories)
    case_by_id = {case["case_id"]: case for case in cases}
    case_cutoffs = definition["case_cutoffs"]
    missing_cases = sorted(set(case_cutoffs) - set(case_by_id))
    if missing_cases:
        raise ValueError(f"missing E2 cases: {missing_cases}")
    catalog_id = definition["catalog_id"]
    source_name = f"sources/{family}-fse-source-family-frame.jsonl"
    catalog = {
        "catalog_id": catalog_id,
        "schema_version": "1.0",
        "catalog_status": "label_independent_reusable_development",
        "selection_rule": definition["source_description"],
        "membership_source": {
            "kind": "external_source_transition_candidate_frame",
            "dataset": "FSE 2024",
            "source_transition": family,
            "snapshot": source_name,
            "catalog_cutoff": "2026-08-25T00:00:00Z",
        },
        "membership_reads_e2_targets": False,
        "source_selection_is_outcome_conditioned": True,
        "candidate_semantics": "downstream_consumer_roots",
        "repository_host": "github.com",
        "repositories": repositories,
    }
    assignments = [{
        "case_id": case_id,
        "candidate_repository_catalog": f"candidate-repositories.json#{catalog_id}",
        "observation_cutoff": case_cutoffs[case_id],
        "catalog_membership_cutoff": "2026-08-25T00:00:00Z",
        "input_spec_opening_cutoff_conformant": definition[
            "input_spec_opening_cutoff_conformant"
        ],
        "cutoff_policy": definition["cutoff_policy"],
        "assignment_basis": (
            f"The case uses the {family} source transition represented by the "
            "complete external source-family frame; final E2 target labels are not "
            "read while constructing membership."
        ),
    } for case_id in sorted(case_cutoffs)]
    coverage_rows = []
    for case_id in sorted(case_cutoffs):
        case = case_by_id[case_id]
        targets = sorted(case["target_repositories"])
        missing_targets = sorted(set(targets) - membership)
        coverage_rows.append({
            "case_id": case_id,
            "source_repository": case["source_repository"],
            "target_repositories": targets,
            "source_covered": None,
            "source_coverage_not_applicable": True,
            "targets_covered": not missing_targets,
            "missing_targets": missing_targets,
            "non_target_candidate_count": len(membership - set(targets)),
            "labels_read_after_membership_construction": True,
        })
    development_eligible = (
        len(case_cutoffs) > 1
        and all(row["targets_covered"] for row in coverage_rows)
        and all(row["non_target_candidate_count"] > 0 for row in coverage_rows)
    )
    coverage = {
        "catalog_id": catalog_id,
        "case_count": len(case_cutoffs),
        "repository_count": len(repositories),
        "reused_across_cases": len(case_cutoffs) > 1,
        "all_sources_covered": None,
        "all_targets_covered": all(row["targets_covered"] for row in coverage_rows),
        "formal_catalog_eligible": False,
        "development_catalog_eligible": development_eligible,
        "cases": coverage_rows,
        "boundary": (
            "Membership is independent of the final E2 target fields and reused, but "
            "the external frame was selected from observed source-transition failures. "
            "It is therefore valid only for development/diagnostic scoring, not a "
            "formal no-leak comparison."
        ),
    }
    return catalog, assignments, coverage


def build_bump_component_catalog(
    cases: list[dict[str, Any]], component: str, frame_text: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    definition = BUMP_COMPONENT_CATALOGS[component]
    repositories = parse_source_family_frame(
        frame_text, definition.get("repository_field", ("repository",))
    )
    membership = set(repositories)
    case_by_id = {case["case_id"]: case for case in cases}
    case_cutoffs = definition["case_cutoffs"]
    missing_cases = sorted(set(case_cutoffs) - set(case_by_id))
    if missing_cases:
        raise ValueError(f"missing E2 cases: {missing_cases}")
    catalog_id = definition["catalog_id"]
    catalog = {
        "catalog_id": catalog_id,
        "schema_version": "1.0",
        "catalog_status": "label_independent_reusable_development",
        "selection_rule": definition.get("selection_rule", (
            f"All {len(repositories)} unique consumer repositories in the complete "
            f"BUMP {component} "
            "candidate frame at revision 324d5513aa5ca40b5cb32de5b816a58fa60bd7bb, "
            "across benchmark and unsuccessful-reproduction records and without "
            "filtering on the final E2 targets."
        )),
        "membership_source": {
            "kind": definition.get(
                "membership_kind", "external_dependency_candidate_frame"
            ),
            "dataset": definition.get("dataset", "BUMP"),
            "source_component": definition["source_component"],
            "source_revision": definition.get(
                "source_revision", "324d5513aa5ca40b5cb32de5b816a58fa60bd7bb"
            ),
            "snapshot": definition.get(
                "snapshot", f"sources/{component}-bump-candidate-frame.jsonl"
            ),
            "catalog_cutoff": "2026-08-25T00:00:00Z",
        },
        "membership_reads_e2_targets": False,
        "source_selection_is_outcome_conditioned": True,
        "candidate_semantics": "downstream_consumer_roots",
        "repository_host": "github.com",
        "repositories": repositories,
    }
    if definition.get("known_unavailable_repositories"):
        catalog["known_unavailable_repositories"] = definition[
            "known_unavailable_repositories"
        ]
    assignments = [{
        "case_id": case_id,
        "candidate_repository_catalog": f"candidate-repositories.json#{catalog_id}",
        "observation_cutoff": case_cutoffs[case_id],
        "catalog_membership_cutoff": "2026-08-25T00:00:00Z",
        "input_spec_opening_cutoff_conformant": definition[
            "input_spec_opening_cutoff_conformant"
        ][case_id],
        "cutoff_policy": definition["cutoff_policy"][case_id],
        "assignment_basis": (
            f"The case uses the {component} source component represented by the "
            "complete external component frame; final E2 target labels are "
            "not read while constructing membership."
        ),
        **({
            "candidate_snapshot_overrides": definition[
                "case_snapshot_overrides"
            ][case_id]
        } if case_id in definition.get("case_snapshot_overrides", {}) else {}),
    } for case_id in sorted(case_cutoffs)]
    coverage_rows = []
    for case_id in sorted(case_cutoffs):
        case = case_by_id[case_id]
        targets = sorted(case["target_repositories"])
        missing_targets = sorted(set(targets) - membership)
        coverage_rows.append({
            "case_id": case_id,
            "source_repository": case["source_repository"],
            "target_repositories": targets,
            "source_covered": None,
            "source_coverage_not_applicable": True,
            "targets_covered": not missing_targets,
            "missing_targets": missing_targets,
            "non_target_candidate_count": len(membership - set(targets)),
            "labels_read_after_membership_construction": True,
        })
    development_eligible = (
        len(case_cutoffs) > 1
        and all(row["targets_covered"] for row in coverage_rows)
        and all(row["non_target_candidate_count"] > 0 for row in coverage_rows)
    )
    coverage = {
        "catalog_id": catalog_id,
        "case_count": len(case_cutoffs),
        "repository_count": len(repositories),
        "reused_across_cases": len(case_cutoffs) > 1,
        "all_sources_covered": None,
        "all_targets_covered": all(row["targets_covered"] for row in coverage_rows),
        "formal_catalog_eligible": False,
        "development_catalog_eligible": development_eligible,
        "cases": coverage_rows,
        "boundary": (
            "Membership does not read final E2 target fields and is reused across "
            "these cases, but BUMP assembled this component frame from attempted "
            "dependency-update outcomes. It is development-only, and the source "
            "input cutoff is audited separately per case."
        ),
    }
    return catalog, assignments, coverage


def build_checkstyle_bump_catalog(
    cases: list[dict[str, Any]], frame_text: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    return build_bump_component_catalog(cases, "checkstyle", frame_text)


def import_ecosystem_catalog_audit(
    cases: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    audit_dir: Path,
    ecosystem: str = "maven",
    identifier: str | None = None,
    snapshot_output_name: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], str]:
    catalog_bundle = json.loads(
        (audit_dir / "candidate-repositories.json").read_text(encoding="utf-8")
    )
    default_identifier = (
        f"ecosystems-{ecosystem}-dependent-package-slices-2026-08-26"
    )
    identifier = identifier or default_identifier
    catalog = dict(catalog_bundle["catalogs"][identifier])
    if catalog.get("membership_reads_e2_targets") is not False:
        raise ValueError(f"ecosystem catalog {identifier} reads E2 targets")
    if catalog.get("source_selection_is_outcome_conditioned") is not False:
        raise ValueError(f"ecosystem catalog {identifier} is outcome-conditioned")
    if catalog.get("query_failure_count"):
        raise ValueError(f"ecosystem catalog {identifier} has query failures")
    complete_query_audit = catalog.get("complete_query_audit")
    if (
        complete_query_audit is not None
        and complete_query_audit.get("complete_query_verified") is not True
    ):
        raise ValueError(f"ecosystem catalog {identifier} is not complete")
    repositories = set(catalog["repositories"])
    normalized_membership = {repository.lower() for repository in repositories}
    case_by_id = {case["case_id"]: case for case in cases}
    assignment_by_id = {row["case_id"]: row for row in assignments}
    coverage_source = read_jsonl(audit_dir / "coverage-audit.jsonl")
    covered_case_ids = sorted(
        row["case_id"]
        for row in coverage_source
        if row["ecosystem"] == ecosystem
        and row.get("catalog_id", default_identifier) == identifier
        and row["targets_covered"]
    )
    replacements = []
    coverage_rows = []
    for case_id in covered_case_ids:
        case = case_by_id[case_id]
        targets = sorted(case["target_repositories"])
        missing_targets = [
            target
            for target in targets
            if target.lower() not in normalized_membership
        ]
        if missing_targets:
            raise ValueError(
                f"ecosystem coverage audit incorrectly covers {case_id}: {missing_targets}"
            )
        original = assignment_by_id[case_id]
        replacements.append({
            **original,
            "candidate_repository_catalog": (
                f"candidate-repositories.json#{identifier}"
            ),
            "catalog_membership_cutoff": catalog["membership_source"][
                "catalog_cutoff"
            ],
            "assignment_basis": (
                f"The visible source component belongs to the evaluated {ecosystem} "
                "package set. Membership is the fixed ecosystem dependent-package "
                "union and was constructed before target coverage was read."
            ),
        })
        coverage_rows.append({
            "case_id": case_id,
            "source_repository": case["source_repository"],
            "target_repositories": targets,
            "source_covered": None,
            "source_coverage_not_applicable": True,
            "targets_covered": True,
            "missing_targets": [],
            "non_target_candidate_count": len(repositories - set(targets)),
            "labels_read_after_membership_construction": True,
        })
    if len(replacements) < 2:
        raise ValueError(f"ecosystem catalog {identifier} is not reused")
    catalog["catalog_status"] = "label_independent_reusable"
    catalog["membership_source"] = dict(catalog["membership_source"])
    catalog["membership_source"]["snapshot"] = snapshot_output_name or (
        f"sources/ecosystems-{ecosystem}-dependent-package-query-snapshots.jsonl"
    )
    coverage = {
        "catalog_id": identifier,
        "case_count": len(replacements),
        "repository_count": len(repositories),
        "reused_across_cases": True,
        "all_sources_covered": None,
        "all_targets_covered": True,
        "formal_catalog_eligible": True,
        "development_catalog_eligible": True,
        "cases": coverage_rows,
        "boundary": (
            "The catalog is current and retrospective. Deleted or transferred "
            "repositories absent from the package index remain a coverage limitation; "
            "only cases covered without changing membership are assigned."
        ),
    }
    source_packages = set(
        catalog["membership_source"].get("source_packages", [])
    )
    snapshot_rows = [
        row
        for row in read_jsonl(
            audit_dir / "sources" / "dependent-package-query-snapshots.jsonl"
        )
        if row["ecosystem"] == ecosystem
        and (not source_packages or row.get("package") in source_packages)
    ]
    snapshot_text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in snapshot_rows
    )
    return catalog, replacements, coverage, snapshot_text


def run(
    e2_index: Path,
    output_dir: Path,
    projects_file: Path | None,
    org_files: dict[str, Path] | None = None,
    include_github_orgs: bool = False,
    h2_frame_files: dict[str, Path] | None = None,
    include_h2_fse: bool = False,
    checkstyle_frame_file: Path | None = None,
    include_checkstyle_bump: bool = False,
    mockito_frame_file: Path | None = None,
    include_mockito_bump: bool = False,
    commons_io_frame_file: Path | None = None,
    include_commons_io_bump: bool = False,
    slf4j_frame_file: Path | None = None,
    include_slf4j_frame: bool = False,
    jackson_fse_frame_file: Path | None = None,
    include_jackson_fse_frame: bool = False,
    project_package_frame_files: dict[str, Path] | None = None,
    include_project_package_frames: bool = False,
    ecosystem_catalog_audit_dir: Path | None = None,
    component_catalog_audit_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    cases = read_jsonl(e2_index)
    projects_text = (
        projects_file.read_text(encoding="utf-8")
        if projects_file is not None
        else fetch_text(OPENSTACK_PROJECTS_URL)
    )
    catalog, assignments, coverage = build_openstack_catalog(cases, projects_text)
    catalogs = {catalog["catalog_id"]: catalog}
    coverages = {catalog["catalog_id"]: coverage}
    snapshots: dict[str, dict[str, Any]] = {}
    frame_snapshots: dict[str, str] = {}
    ecosystem_snapshot_files: dict[str, str] = {}
    if include_github_orgs:
        for organization in sorted(GITHUB_ORGANIZATIONS):
            source = (org_files or {}).get(organization)
            snapshot = (
                json.loads(source.read_text(encoding="utf-8"))
                if source is not None
                else fetch_github_org_snapshot(organization)
            )
            org_catalog, org_assignments, org_coverage = build_github_org_catalog(
                cases, organization, snapshot
            )
            catalogs[org_catalog["catalog_id"]] = org_catalog
            assignments.extend(org_assignments)
            coverages[org_catalog["catalog_id"]] = org_coverage
            snapshots[organization] = snapshot
    if include_h2_fse:
        for family in sorted(H2_FSE_CATALOGS):
            source = (h2_frame_files or {}).get(
                family, H2_FSE_CATALOGS[family]["default_source"]
            )
            frame_text = source.read_text(encoding="utf-8")
            family_catalog, family_assignments, family_coverage = build_h2_fse_catalog(
                cases, family, frame_text
            )
            catalogs[family_catalog["catalog_id"]] = family_catalog
            assignments.extend(family_assignments)
            coverages[family_catalog["catalog_id"]] = family_coverage
            frame_snapshots[family] = frame_text
    if include_checkstyle_bump:
        source = checkstyle_frame_file or BUMP_COMPONENT_CATALOGS["checkstyle"]["default_source"]
        frame_text = source.read_text(encoding="utf-8")
        family_catalog, family_assignments, family_coverage = (
            build_checkstyle_bump_catalog(cases, frame_text)
        )
        catalogs[family_catalog["catalog_id"]] = family_catalog
        assignments.extend(family_assignments)
        coverages[family_catalog["catalog_id"]] = family_coverage
        frame_snapshots["checkstyle-bump"] = frame_text
    if include_mockito_bump:
        source = mockito_frame_file or BUMP_COMPONENT_CATALOGS["mockito"]["default_source"]
        frame_text = source.read_text(encoding="utf-8")
        family_catalog, family_assignments, family_coverage = (
            build_bump_component_catalog(cases, "mockito", frame_text)
        )
        catalogs[family_catalog["catalog_id"]] = family_catalog
        assignments.extend(family_assignments)
        coverages[family_catalog["catalog_id"]] = family_coverage
        frame_snapshots["mockito-bump"] = frame_text
    if include_commons_io_bump:
        source = commons_io_frame_file or BUMP_COMPONENT_CATALOGS["commons-io"]["default_source"]
        frame_text = source.read_text(encoding="utf-8")
        family_catalog, family_assignments, family_coverage = (
            build_bump_component_catalog(cases, "commons-io", frame_text)
        )
        catalogs[family_catalog["catalog_id"]] = family_catalog
        assignments.extend(family_assignments)
        coverages[family_catalog["catalog_id"]] = family_coverage
        frame_snapshots["commons-io-bump"] = frame_text
    if include_slf4j_frame:
        source = slf4j_frame_file or BUMP_COMPONENT_CATALOGS["slf4j"]["default_source"]
        frame_text = source.read_text(encoding="utf-8")
        family_catalog, family_assignments, family_coverage = (
            build_bump_component_catalog(cases, "slf4j", frame_text)
        )
        catalogs[family_catalog["catalog_id"]] = family_catalog
        assignments.extend(family_assignments)
        coverages[family_catalog["catalog_id"]] = family_coverage
        frame_snapshots["slf4j-screening"] = frame_text
    if include_jackson_fse_frame:
        source = jackson_fse_frame_file or BUMP_COMPONENT_CATALOGS["jackson"]["default_source"]
        source_text = source.read_text(encoding="utf-8")
        repositories = parse_jackson_fse_component_frame(source_text)
        resolved_text = "".join(
            json.dumps({"repository": repository}) + "\n"
            for repository in repositories
        )
        family_catalog, family_assignments, family_coverage = (
            build_bump_component_catalog(cases, "jackson", resolved_text)
        )
        catalogs[family_catalog["catalog_id"]] = family_catalog
        assignments.extend(family_assignments)
        coverages[family_catalog["catalog_id"]] = family_coverage
        frame_snapshots["jackson-screening"] = source_text
    if include_project_package_frames:
        for component in (
            "crater-linked-fixes",
            "fse-assertj-derby",
            "fse-java-compat",
            "legacy-component-screening",
            "plexus-utils",
            "snakeyaml",
            "terser",
        ):
            source = (project_package_frame_files or {}).get(
                component, BUMP_COMPONENT_CATALOGS[component]["default_source"]
            )
            frame_text = source.read_text(encoding="utf-8")
            family_catalog, family_assignments, family_coverage = (
                build_bump_component_catalog(cases, component, frame_text)
            )
            catalogs[family_catalog["catalog_id"]] = family_catalog
            assignments.extend(family_assignments)
            coverages[family_catalog["catalog_id"]] = family_coverage
            frame_snapshots[f"{component}-screening"] = frame_text
    if ecosystem_catalog_audit_dir is not None:
        ecosystem_imports = [
            (
                "maven",
                "ecosystems-maven-dependent-package-slices-2026-08-26",
                "sources/ecosystems-maven-dependent-package-query-snapshots.jsonl",
            ),
            (
                "npm",
                "ecosystems-npm-complete-package-dependent-slices-2026-08-26",
                "sources/ecosystems-npm-complete-package-dependent-query-snapshots.jsonl",
            ),
        ]
        audit_catalogs = json.loads(
            (ecosystem_catalog_audit_dir / "candidate-repositories.json").read_text(
                encoding="utf-8"
            )
        )["catalogs"]
        for ecosystem, identifier, snapshot_output_name in ecosystem_imports:
            if identifier not in audit_catalogs:
                continue
            (
                ecosystem_catalog,
                ecosystem_assignments,
                ecosystem_coverage,
                ecosystem_snapshot_text,
            ) = import_ecosystem_catalog_audit(
                cases,
                assignments,
                ecosystem_catalog_audit_dir,
                ecosystem,
                identifier,
                snapshot_output_name,
            )
            replacement_ids = {row["case_id"] for row in ecosystem_assignments}
            assignments = [
                row for row in assignments if row["case_id"] not in replacement_ids
            ]
            assignments.extend(ecosystem_assignments)
            catalogs[ecosystem_catalog["catalog_id"]] = ecosystem_catalog
            coverages[ecosystem_catalog["catalog_id"]] = ecosystem_coverage
            ecosystem_snapshot_files[snapshot_output_name] = ecosystem_snapshot_text
    for component_audit_dir in component_catalog_audit_dirs or []:
        audit_catalogs = json.loads(
            (component_audit_dir / "candidate-repositories.json").read_text(
                encoding="utf-8"
            )
        )["catalogs"]
        if len(audit_catalogs) != 1:
            raise ValueError(
                f"component audit must contain one catalog: {component_audit_dir}"
            )
        identifier, source_catalog = next(iter(audit_catalogs.items()))
        coverage_source = read_jsonl(component_audit_dir / "coverage-audit.jsonl")
        ecosystems = {row["ecosystem"] for row in coverage_source}
        if len(ecosystems) != 1:
            raise ValueError(f"component audit has mixed ecosystems: {identifier}")
        ecosystem = next(iter(ecosystems))
        snapshot_output_name = (
            f"sources/{identifier}-dependent-package-query-snapshots.jsonl"
        )
        (
            component_catalog,
            component_assignments,
            component_coverage,
            component_snapshot_text,
        ) = import_ecosystem_catalog_audit(
            cases,
            assignments,
            component_audit_dir,
            ecosystem,
            identifier,
            snapshot_output_name,
        )
        replacement_ids = {row["case_id"] for row in component_assignments}
        assignments = [
            row for row in assignments if row["case_id"] not in replacement_ids
        ]
        assignments.extend(component_assignments)
        metadata_snapshot = source_catalog.get("membership_source", {}).get(
            "package_metadata_snapshot"
        )
        if metadata_snapshot:
            metadata_output_name = (
                f"sources/{identifier}-component-package-metadata.json"
            )
            component_catalog["membership_source"][
                "package_metadata_snapshot"
            ] = metadata_output_name
            ecosystem_snapshot_files[metadata_output_name] = (
                component_audit_dir / metadata_snapshot
            ).read_text(encoding="utf-8")
        catalogs[component_catalog["catalog_id"]] = component_catalog
        coverages[component_catalog["catalog_id"]] = component_coverage
        ecosystem_snapshot_files[snapshot_output_name] = component_snapshot_text
    assignments.sort(key=lambda row: row["case_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sources").mkdir(exist_ok=True)
    (output_dir / "sources" / "openstack-requirements-projects.txt").write_text(
        projects_text, encoding="utf-8"
    )
    for organization, snapshot in snapshots.items():
        write_json(
            output_dir / "sources" / f"{organization}-github-org-repositories.json",
            snapshot,
        )
    for family, frame_text in frame_snapshots.items():
        (output_dir / frame_snapshot_name(family)).write_text(
            frame_text, encoding="utf-8"
        )
    for relative_path, snapshot_text in ecosystem_snapshot_files.items():
        (output_dir / relative_path).write_text(snapshot_text, encoding="utf-8")
    write_json(output_dir / "candidate-repositories.json", {
        "schema_version": "1.0",
        "catalogs": catalogs,
    })
    write_jsonl(output_dir / "case-catalog-assignments.jsonl", assignments)
    write_json(output_dir / "coverage-audit.json", {
        "schema_version": "1.0",
        "catalogs": coverages,
        "all_catalogs_label_independent": all(
            not item["membership_reads_e2_targets"] for item in catalogs.values()
        ),
    })
    formal_catalog_ids = {
        identifier
        for identifier, item in coverages.items()
        if item["formal_catalog_eligible"]
    }
    eligible_cases = sum(
        row["candidate_repository_catalog"].split("#", 1)[1]
        in formal_catalog_ids
        for row in assignments
    )
    development_only_cases = len(assignments) - eligible_cases
    summary = {
        "schema_version": "1.0",
        "e2_case_count": len(cases),
        "catalog_count": len(catalogs),
        "assigned_case_count": len(assignments),
        "unassigned_case_count": len(cases) - len(assignments),
        "formal_catalog_eligible_case_count": eligible_cases,
        "development_only_catalog_case_count": development_only_cases,
        "snapshot_ready_case_count": 0,
        "input_materialization_ready_case_count": 0,
        "remaining_work": (
            f"Resolve cutoff-time commits for {len(assignments)} assigned cases and "
            f"construct independent catalogs for the remaining {len(cases) - len(assignments)} E2 cases."
        ),
    }
    write_json(output_dir / "metrics.json", summary)
    write_json(output_dir / "run-manifest.json", {
        "schema_version": "1.0",
        "membership_inputs": [OPENSTACK_PROJECTS_URL, str(e2_index)] + [
            catalogs[item]["membership_source"].get(
                "endpoint", catalogs[item]["membership_source"].get("snapshot", "")
            )
            for item in sorted(catalogs) if item != OPENSTACK_CATALOG_ID
        ],
        "membership_reads_e2_targets": False,
        "labels_read_after_membership_for_coverage_audit": True,
        "network_used": projects_file is None or (
            include_github_orgs and len(org_files or {}) < len(GITHUB_ORGANIZATIONS)
        ),
        "outputs": [
            "candidate-repositories.json",
            "case-catalog-assignments.jsonl",
            "coverage-audit.json",
            "metrics.json",
            "sources/openstack-requirements-projects.txt",
        ] + [
            f"sources/{organization}-github-org-repositories.json"
            for organization in sorted(snapshots)
        ] + [
            frame_snapshot_name(family)
            for family in sorted(frame_snapshots)
        ] + sorted(ecosystem_snapshot_files),
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2-index", type=Path, default=E2_INDEX)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--openstack-projects-file", type=Path)
    parser.add_argument("--include-github-orgs", action="store_true")
    parser.add_argument("--jcabi-repositories-file", type=Path)
    parser.add_argument("--assertj-repositories-file", type=Path)
    parser.add_argument("--include-h2-fse", action="store_true")
    parser.add_argument("--h2-1-4-200-frame", type=Path)
    parser.add_argument("--h2-2-0-202-frame", type=Path)
    parser.add_argument("--include-checkstyle-bump", action="store_true")
    parser.add_argument("--checkstyle-bump-frame", type=Path)
    parser.add_argument("--include-mockito-bump", action="store_true")
    parser.add_argument("--mockito-bump-frame", type=Path)
    parser.add_argument("--include-commons-io-bump", action="store_true")
    parser.add_argument("--commons-io-bump-frame", type=Path)
    parser.add_argument("--include-slf4j-frame", action="store_true")
    parser.add_argument("--slf4j-frame", type=Path)
    parser.add_argument("--include-jackson-fse-frame", action="store_true")
    parser.add_argument("--jackson-fse-frame", type=Path)
    parser.add_argument("--include-project-package-frames", action="store_true")
    parser.add_argument("--snakeyaml-frame", type=Path)
    parser.add_argument("--plexus-utils-frame", type=Path)
    parser.add_argument("--terser-frame", type=Path)
    parser.add_argument("--fse-assertj-derby-frame", type=Path)
    parser.add_argument("--fse-java-compat-frame", type=Path)
    parser.add_argument("--crater-linked-fixes-frame", type=Path)
    parser.add_argument("--legacy-component-screening-frame", type=Path)
    parser.add_argument("--ecosystem-catalog-audit-dir", type=Path)
    parser.add_argument(
        "--component-catalog-audit-dir", type=Path, action="append", default=[]
    )
    args = parser.parse_args()
    summary = run(
        args.e2_index.resolve(),
        args.output_dir.resolve(),
        args.openstack_projects_file.resolve() if args.openstack_projects_file else None,
        {
            organization: path.resolve()
            for organization, path in {
                "jcabi": args.jcabi_repositories_file,
                "assertj": args.assertj_repositories_file,
            }.items()
            if path is not None
        },
        args.include_github_orgs,
        {
            family: path.resolve()
            for family, path in {
                "h2-1.4.200": args.h2_1_4_200_frame,
                "h2-2.0.202": args.h2_2_0_202_frame,
            }.items()
            if path is not None
        },
        args.include_h2_fse,
        args.checkstyle_bump_frame.resolve() if args.checkstyle_bump_frame else None,
        args.include_checkstyle_bump,
        args.mockito_bump_frame.resolve() if args.mockito_bump_frame else None,
        args.include_mockito_bump,
        args.commons_io_bump_frame.resolve() if args.commons_io_bump_frame else None,
        args.include_commons_io_bump,
        args.slf4j_frame.resolve() if args.slf4j_frame else None,
        args.include_slf4j_frame,
        args.jackson_fse_frame.resolve() if args.jackson_fse_frame else None,
        args.include_jackson_fse_frame,
        {
            component: path.resolve()
            for component, path in {
                "snakeyaml": args.snakeyaml_frame,
                "plexus-utils": args.plexus_utils_frame,
                "terser": args.terser_frame,
                "fse-assertj-derby": args.fse_assertj_derby_frame,
                "fse-java-compat": args.fse_java_compat_frame,
                "crater-linked-fixes": args.crater_linked_fixes_frame,
                "legacy-component-screening": args.legacy_component_screening_frame,
            }.items()
            if path is not None
        },
        args.include_project_package_frames,
        args.ecosystem_catalog_audit_dir.resolve()
        if args.ecosystem_catalog_audit_dir
        else None,
        [path.resolve() for path in args.component_catalog_audit_dir],
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
