from marshal_core.concept.model import ConceptPage, ConceptAnchor
from marshal_core.concept.anchor import verify_anchors


def _page(anchors):
    return ConceptPage(concept_id="c", importance="high", anchors=anchors)


def test_verified_when_symbol_exists(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct GasReport { x: u64 }\n")
    page = _page([ConceptAnchor(repo="node", path="execution/src/gas.rs", symbol="GasReport")])

    report = verify_anchors(page, {"node": str(repo)})
    assert report.verified_count == 1
    assert report.doc_only is False
    assert report.confidence >= 0.8


def test_doc_only_when_symbol_missing(tmp_path):
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text("pub struct Something { x: u64 }\n")
    page = _page([ConceptAnchor(repo="node", path="execution/src/gas.rs", symbol="GasReport")])

    report = verify_anchors(page, {"node": str(repo)})
    assert report.verified_count == 0
    assert report.doc_only is True
    assert report.confidence <= 0.3   # H1: 无代码锚定 → confidence 封顶低


def test_no_anchors_is_doc_only(tmp_path):
    report = verify_anchors(_page([]), {"node": str(tmp_path)})
    assert report.doc_only is True
    assert report.confidence <= 0.3


def test_comment_only_mention_is_doc_only(tmp_path):
    """深审 run 750(H1-weak): 符号只在注释里提及、代码没实现 → 必须 doc_only,
    不能因文本出现就判高置信锚定(否则 H1 沦为文本存在检查, 就是它要防的 sim≠prod)。"""
    repo = tmp_path / "node"
    (repo / "execution" / "src").mkdir(parents=True)
    (repo / "execution" / "src" / "gas.rs").write_text(
        "// TODO: someday implement GasReport here\npub struct Foo {}\n")
    page = _page([ConceptAnchor(repo="node", path="execution/src/gas.rs", symbol="GasReport")])

    report = verify_anchors(page, {"node": str(repo)})
    assert report.verified_count == 0     # 注释提及不算定义
    assert report.doc_only is True


def test_defined_but_semantically_wrong_still_passes_anchor(tmp_path):
    """边界(非 bug): 挂羊头(名 GasReport 实为 UI widget)的**定义**仍通过 verify_anchors
    —— 语义名副其实由 S4 concept-consistency lens 判, 不是 H1 锚定的职责。此测锁定该边界,
    防有人误以为锚定率门=无挂羊头。"""
    repo = tmp_path / "node"
    (repo / "ui").mkdir(parents=True)
    (repo / "ui" / "gas.rs").write_text("pub struct GasReport { pixel_color: u8 }\n")
    page = _page([ConceptAnchor(repo="node", path="ui/gas.rs", symbol="GasReport")])

    report = verify_anchors(page, {"node": str(repo)})
    assert report.verified_count == 1     # 定义存在 → 锚定通过 (语义对错不在此判)
    assert report.doc_only is False
