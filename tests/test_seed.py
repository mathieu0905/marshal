import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marshal_core.knowledge.models import Base, Meta
from marshal_core.knowledge.store import Store  # noqa: F401  # used by later tasks

ROOT = os.path.dirname(os.path.dirname(__file__))


def _session(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_meta_model_roundtrips(tmp_path):
    s = _session(tmp_path / "m.db")
    s.add(Meta(key="snapshot_version", value="1.2.3"))
    s.commit()
    got = s.get(Meta, "snapshot_version")
    assert got.value == "1.2.3"
