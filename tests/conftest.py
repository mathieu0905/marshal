import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session():
    # 单元测试用内存 SQLite;集成测试单独用 Postgres。
    engine = create_engine("sqlite:///:memory:")
    from marshal_core.knowledge.models import Base
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _isolate_marshal_db(tmp_path, monkeypatch):
    """防御:任何没显式设 MARSHAL_DB 的测试,默认落到 per-test 临时 db,
    绝不写仓库根 marshal.db(曾因此清零真实 db)。已显式设 MARSHAL_DB 的测试不受影响。"""
    if not os.environ.get("MARSHAL_DB"):
        monkeypatch.setenv("MARSHAL_DB", f"sqlite:///{tmp_path}/_isolated.db")
    yield
