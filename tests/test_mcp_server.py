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


def _write_gas(tmp_path):
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    (concepts / "gas.md").write_text(
        '---\ntype: concept\nconcept_id: gas\nimportance: constitutional\n'
        'status: authoritative\nlast_updated: 2026-07-26\n---\ngas\n')
    return concepts


def test_call_tool_protocol_layer(tmp_path):
    """深审 #21: 前面的测试全是函数层直呼(绕过 FastMCP 的 schema 校验/调用/错误包装)。
    这条走**真正的 MCP 协议路径** `mcp.call_tool` —— 那才是 S3 的产品面。"""
    import asyncio

    from marshal_core import mcp_server
    concepts = _write_gas(tmp_path)

    async def run():
        # 合法调用经协议层(schema 校验 + 调用)→ 返回, 内含 cost-only
        res = await mcp_server.mcp.call_tool(
            "marshal_plan_review",
            {"concepts_dir": str(concepts), "domain_pack": "probe",
             "touches": [{"concept_id": "gas", "op": "redefine"}]})
        assert "cost-only" in str(res)
        # touch=非 list → FastMCP schema 校验拒绝(ToolError, 非 server crash)
        with pytest.raises(Exception):
            await mcp_server.mcp.call_tool(
                "marshal_plan_review",
                {"concepts_dir": str(concepts), "domain_pack": "probe",
                 "touches": {"not": "a list"}})
        # touch 缺 op → 业务 guard 的清晰错误经协议层冒出
        with pytest.raises(Exception) as ei:
            await mcp_server.mcp.call_tool(
                "marshal_plan_review",
                {"concepts_dir": str(concepts), "domain_pack": "probe",
                 "touches": [{"concept_id": "x"}]})
        assert "op" in str(ei.value)

    asyncio.run(run())
