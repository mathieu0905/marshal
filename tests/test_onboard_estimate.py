from marshal_core.onboard.estimate import estimate_cost


def _mk_repo(tmp_path, n_code=5, n_doc=2):
    repo = tmp_path / "r"
    (repo / "src").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)
    for i in range(n_code):
        (repo / "src" / f"m{i}.rs").write_text("pub struct S {}\n" * 50)
    for i in range(n_doc):
        (repo / "docs" / f"d{i}.md").write_text("# doc\n" + "word " * 200)
    return repo


def test_estimate_has_disclosed_method_and_caveat(tmp_path):
    est = estimate_cost(str(_mk_repo(tmp_path)))
    # 必含各字段
    for k in ("est_input_tokens", "est_output_tokens", "est_agent_calls",
              "est_usd_low", "est_usd_high", "method", "is_estimate"):
        assert k in est, f"missing {k}"
    # 必须显式披露"这是估算 + 方法",不谎报精度(§6.3 诚实纪律)
    assert est["is_estimate"] is True
    assert len(est["method"]) > 20            # 方法有实质描述
    assert est["est_usd_low"] <= est["est_usd_high"]


def test_bigger_repo_estimates_more(tmp_path):
    small = estimate_cost(str(_mk_repo(tmp_path / "a", n_code=2, n_doc=1)))
    big = estimate_cost(str(_mk_repo(tmp_path / "b", n_code=20, n_doc=10)))
    assert big["est_input_tokens"] > small["est_input_tokens"]


def test_vendored_dirs_excluded(tmp_path):
    """node/ 冒烟教训: 不排除 target/.venv/node_modules 会让估价虚高一个数量级。"""
    repo = _mk_repo(tmp_path, n_code=2, n_doc=1)
    base = estimate_cost(str(repo))
    # 往 vendored 目录塞大量代码, 估价不应变化
    (repo / "target" / "debug").mkdir(parents=True)
    for i in range(50):
        (repo / "target" / "debug" / f"junk{i}.rs").write_text("pub struct J {}\n" * 200)
    (repo / ".venv" / "lib").mkdir(parents=True)
    (repo / ".venv" / "lib" / "dep.py").write_text("x = 1\n" * 500)
    after = estimate_cost(str(repo))
    assert after["est_input_tokens"] == base["est_input_tokens"]   # vendored 被排除
    assert after["scanned"]["n_modules"] == base["scanned"]["n_modules"]
