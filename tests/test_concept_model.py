from marshal_core.concept.model import ConceptPage, parse_concept_page

SAMPLE = """---
type: concept
concept_id: dual-gas-model
parent: execution
importance: constitutional
part_of: [economics]
depends_on: [basefee]
anchors:
  - {repo: node, path: execution/src/gas.rs, symbol: GasReport, kind: implements}
spec_refs: [CIP-3]
status: authoritative
last_updated: 2026-07-25
---

# 双计量 Gas 模型

正文定义。
"""


def test_parse_concept_page_fields():
    page = parse_concept_page(SAMPLE)
    assert isinstance(page, ConceptPage)
    assert page.concept_id == "dual-gas-model"
    assert page.parent == "execution"
    assert page.importance == "constitutional"
    assert page.part_of == ["economics"]
    assert page.depends_on == ["basefee"]
    assert page.spec_refs == ["CIP-3"]
    assert len(page.anchors) == 1
    assert page.anchors[0].symbol == "GasReport"
    assert page.anchors[0].repo == "node"
    assert "双计量" in page.definition


def test_parse_rejects_missing_concept_id():
    bad = "---\ntype: concept\nimportance: low\n---\nbody\n"
    try:
        parse_concept_page(bad)
        assert False, "should have raised"
    except ValueError as e:
        assert "concept_id" in str(e)


def test_malformed_anchor_raises_valueerror_not_keyerror():
    """深审 run 750 bug C: anchor 缺字段必须抛 ValueError (可被 derive 收集), 不是
    KeyError (会冒泡令整批 derive 崩)。"""
    bad = ("---\ntype: concept\nconcept_id: x\nimportance: low\n"
           "anchors:\n  - {repo: node, path: p}\n---\nbody\n")   # 缺 symbol
    try:
        parse_concept_page(bad)
        assert False, "should have raised"
    except KeyError:
        assert False, "must not raise KeyError (crashes derive batch)"
    except ValueError as e:
        assert "anchor" in str(e)
