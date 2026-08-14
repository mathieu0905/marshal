from marshal_core import config


def test_db_url_env_override_always_wins(monkeypatch):
    monkeypatch.setenv("MARSHAL_DB", "sqlite:///explicit.db")
    assert config.db_url() == "sqlite:///explicit.db"


def test_db_url_prefers_live_workspace_db_when_present(monkeypatch, tmp_path):
    monkeypatch.delenv("MARSHAL_DB", raising=False)
    live = tmp_path / "workspace" / "marshal"
    live.mkdir(parents=True)
    (live / "marshal.db").write_text("")
    monkeypatch.setattr(config.Path, "home", staticmethod(lambda: tmp_path))
    assert config.db_url() == f"sqlite:///{live / 'marshal.db'}"


def test_db_url_falls_back_to_marshal_home_when_no_workspace_db(monkeypatch, tmp_path):
    monkeypatch.delenv("MARSHAL_DB", raising=False)
    monkeypatch.setattr(config.Path, "home", staticmethod(lambda: tmp_path))  # no workspace/marshal here
    monkeypatch.setenv("MARSHAL_HOME", str(tmp_path / "checkout"))
    assert config.db_url() == f"sqlite:///{tmp_path / 'checkout' / 'marshal.db'}"
