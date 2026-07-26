import pytest

pytest.importorskip("mcp")   # 无 mcp SDK 时跳过(与 zizmor/ci 降级同纪律)


def test_tool_registered_and_neutral():
    from marshal_core import mcp_server
    # 工具已注册, 名字对
    tools = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
    assert "marshal_plan_review" in tools
    # 描述必须中性: 不含 go/no-go 措辞
    desc = next(t.description for t in mcp_server.mcp._tool_manager.list_tools()
                if t.name == "marshal_plan_review").lower()
    for banned in ("should you", "recommend", "advise", "do it", "don't do"):
        assert banned not in desc


def test_tool_call_returns_cost_only(tmp_path):
    from marshal_core.mcp_server import marshal_plan_review
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "gas.md").write_text(
        '---\ntype: concept\nconcept_id: gas\nimportance: constitutional\n'
        'status: authoritative\nlast_updated: 2026-07-26\n---\ngas\n')
    out = marshal_plan_review(concepts_dir=str(concepts), domain_pack="probe",
                              touches=[{"concept_id": "gas", "op": "redefine"}])
    assert out["verdict"] == "cost-only"
