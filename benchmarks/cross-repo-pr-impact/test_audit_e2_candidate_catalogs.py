import tempfile
import unittest
from pathlib import Path

from audit_e2_candidate_catalogs import (
    ROOT,
    DEFAULT_E2_INDEX,
    audit_cases,
    catalog_facts,
    read_json,
    read_jsonl,
    run,
)


class E2CandidateCatalogAuditTests(unittest.TestCase):
    def setUp(self):
        self.cases = read_jsonl(DEFAULT_E2_INDEX)
        catalogs = read_json(ROOT / "candidate-repositories.json")["catalogs"]
        provenance = read_json(ROOT / "candidate-catalog-provenance.json")
        snapshots = read_json(ROOT / "catalog-source-snapshots.json")
        self.facts = catalog_facts(catalogs, provenance, snapshots)

    def test_all_50_cases_are_audited_once(self):
        rows = audit_cases(self.cases, self.facts)
        self.assertEqual(50, len(rows))
        self.assertEqual(50, len({row["case_id"] for row in rows}))

    def test_current_catalogs_do_not_make_e2_formal_input_ready(self):
        rows = audit_cases(self.cases, self.facts)
        counts = {}
        for row in rows:
            counts[row["disposition"]] = counts.get(row["disposition"], 0) + 1
        self.assertEqual({"missing_catalog_reference": 50}, counts)
        self.assertFalse(any(row["formal_input_eligible"] for row in rows))

    def test_rust_catalog_is_independent_but_does_not_cover_crater_targets(self):
        rows = audit_cases(self.cases, self.facts)
        rust_rows = [row for row in rows if row["source_repository"] == "rust-lang/rust"]
        self.assertEqual(4, len(rust_rows))
        for row in rust_rows:
            self.assertEqual("missing_catalog_reference", row["disposition"])
            match = next(item for item in row["potential_catalogs_by_source_membership"] if item["catalog_id"] == "rust")
            self.assertTrue(match["label_independent_membership"])
            self.assertFalse(match["target_coverage"])

    def test_openstack_target_coverage_does_not_override_bad_provenance(self):
        rows = audit_cases(self.cases, self.facts)
        openstack_rows = [row for row in rows if row["source_repository"].startswith("openstack/")]
        self.assertEqual(2, len(openstack_rows))
        requirements = next(row for row in openstack_rows if row["case_id"] == "e2-001")
        match = next(item for item in requirements["potential_catalogs_by_source_membership"] if item["catalog_id"] == "openstack")
        self.assertTrue(match["target_coverage"])
        self.assertFalse(match["label_independent_membership"])
        ipa = next(row for row in openstack_rows if row["case_id"] == "e2-006")
        self.assertFalse(ipa["potential_catalogs_by_source_membership"])

    def test_run_materializes_parseable_audit_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit"
            summary = run(ROOT, DEFAULT_E2_INDEX, output)
            self.assertEqual(0, summary["formal_input_eligible_case_count"])
            self.assertFalse(summary["inputs_materialization_ready"])
            self.assertEqual(50, len(read_jsonl(output / "case-audit.jsonl")))
            manifest = read_json(output / "run-manifest.json")
            self.assertFalse(manifest["network_used"])
            self.assertFalse(manifest["membership_selection_reads_e2_targets"])


if __name__ == "__main__":
    unittest.main()
