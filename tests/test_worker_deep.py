import json
import pytest
from marshal_core.worker import _parse_verdict, DeepReviewError, VERDICT_FILE


def _write(tmp_path, obj):
    p = tmp_path / VERDICT_FILE
    p.write_text(json.dumps(obj))
    return str(p)


def test_parse_verdict_valid(tmp_path):
    path = _write(tmp_path, {"verdict": "needs_human", "summary": "s",
                             "findings": ["f1"], "invariants_run": 5, "invariants_pass": 5})
    v = _parse_verdict(path)
    assert v["verdict"] == "needs_human"
    assert v["findings"] == ["f1"]


def test_parse_verdict_missing_file_raises(tmp_path):
    with pytest.raises(DeepReviewError, match="not written"):
        _parse_verdict(str(tmp_path / VERDICT_FILE))


def test_parse_verdict_bad_json_raises(tmp_path):
    p = tmp_path / VERDICT_FILE
    p.write_text("{not json")
    with pytest.raises(DeepReviewError, match="unparseable"):
        _parse_verdict(str(p))


def test_parse_verdict_invalid_verdict_value_raises(tmp_path):
    path = _write(tmp_path, {"verdict": "lgtm"})
    with pytest.raises(DeepReviewError, match="invalid verdict"):
        _parse_verdict(path)
