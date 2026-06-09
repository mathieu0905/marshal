from marshal_pack_cowboy.pack import CowboyPack


def test_execution_path_is_high_with_reason():
    pack = CowboyPack()
    d = pack.classify_detailed({"repo": "node",
                                "diff_paths": ["execution/src/execution/engine.rs"]})
    assert d["tier"] == "high"
    assert any("execution" in r for r in d["reasons"])


def test_system_address_change_is_high():
    pack = CowboyPack()
    d = pack.classify_detailed({"repo": "node",
                                "diff_paths": ["execution/src/runner/registry.rs"],
                                "diff_text": "Address::from_low_u64(0x91)"})
    assert d["tier"] == "high"


def test_contract_hit_forces_high():
    pack = CowboyPack()
    d = pack.classify_detailed({"repo": "wallet",
                                "diff_paths": ["src/lib/cbor.js"]})
    assert d["tier"] == "high"
    assert "tx-encoding" in d["contracts_hit"]
    assert any("cross_repo_contract" in r for r in d["reasons"])


def test_docs_only_is_low():
    pack = CowboyPack()
    d = pack.classify_detailed({"repo": "node", "diff_paths": ["README.md"]})
    assert d["tier"] == "low"


def test_rpc_handler_is_mid():
    pack = CowboyPack()
    d = pack.classify_detailed({"repo": "node", "diff_paths": ["rpc/src/handlers.rs"]})
    assert d["tier"] == "mid"


def test_classify_str_still_returns_tier():
    pack = CowboyPack()
    assert pack.classify({"repo": "node",
                          "diff_paths": ["execution/src/execution/engine.rs"]}) == "high"


# Ratchet esc-20260609-classifier-ci-workflow-blindspot (node PR #649):
# .github/workflows files must classify as CI/infra, never the "ordinary actor /
# RPC handler" default, and privileged workflow constructs must escalate to high.
def test_ci_workflow_benign_is_low_not_default_mid():
    pack = CowboyPack()
    d = pack.classify_detailed({
        "repo": "node",
        "diff_paths": [".github/workflows/coverage.yml"],
        "diff_text": "-    runs-on: ubuntu-latest\n+    runs-on: ubuntu-latest-l",
    })
    assert d["tier"] == "low"
    assert not any("ordinary actor" in r for r in d["reasons"])
    assert any("CI/infra workflow" in r for r in d["reasons"])


def test_ci_workflow_privileged_is_high_via_threat_model():
    # Escalation now comes from the CI threat model (whole-file, combination), surfaced
    # through security_hazards — not a flat token scan. A pull_request job on a custom
    # runner with a token must classify high with a ci.* hazard reason.
    pack = CowboyPack()
    wf = ("name: c\non:\n  pull_request:\njobs:\n  j:\n    runs-on: ubuntu-latest-lx\n"
          "    env:\n      TOK: ${{ secrets.X }}\n    steps:\n      - run: x\n")
    d = pack.classify_detailed({
        "repo": "node",
        "diff_paths": [".github/workflows/coverage.yml"],
        "workflow_files": {".github/workflows/coverage.yml": wf},
    })
    assert d["tier"] == "high"
    assert any(r.startswith("security-hazard:ci.") for r in d["reasons"])


def test_ci_plus_product_code_not_dragged_to_low():
    # A workflow path must not let real product code ride in under a low tier.
    pack = CowboyPack()
    d = pack.classify_detailed({
        "repo": "node",
        "diff_paths": [".github/workflows/coverage.yml",
                       "execution/src/execution/engine.rs"],
    })
    assert d["tier"] == "high"


def test_review_plan_scales_with_tier():
    pack = CowboyPack()
    assert len(pack.review_plan("high")) == 6
    assert len(pack.review_plan("mid")) == 3
    assert len(pack.review_plan("low")) == 1
