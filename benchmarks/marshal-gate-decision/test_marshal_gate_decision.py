import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_development_case_verifies():
    verify = _module("verify_case")
    case_dir = HERE / "cases" / "mgd-dev-001"
    result = verify.verify(
        case_dir / "public" / "case.json",
        case_dir / "private" / "gold.json",
        None,
    )
    assert result["status"] == "development_case_verified"
    assert result["arms"] == {"A0": 0, "A1": 1, "A2": 0}
    assert result["formal_benchmark"] is False


def test_current_marshal_exposes_cross_repo_execution_gap(tmp_path):
    runner = _module("run_current_marshal")
    scorer = _module("score_prediction")
    case_dir = HERE / "cases" / "mgd-dev-001"
    prediction = runner.run(case_dir / "public" / "case.json")
    gold = json.loads((case_dir / "private" / "gold.json").read_text())
    score = scorer.score(prediction, gold)
    assert score["checks"]["invariant_set"] is True
    assert score["checks"]["route_map"] is True
    assert score["checks"]["execution_result"] is False
    assert score["checks"]["verdict"] is False
    assert score["checks"]["end_to_end"] is False


def test_pool_keeps_rule_authoring_sources_out_of_evaluation():
    pool = _module("verify_pool").verify_pool(HERE / "cases")
    statuses = {row["case_id"]: row["status"] for row in pool["accepted"]}
    assert statuses["mgd-dev-001"] == "development_case_verified"
    assert statuses["mgd-cand-007"] == "development_case_verified"
    assert statuses["mgd-cand-009"] == "case_ready_for_pool"
    assert statuses["mgd-cand-011"] == "case_ready_for_pool"
    assert pool["rejected_count"] == 7
    assert pool["formal_benchmark"] is False
