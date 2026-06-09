import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(__file__))
DOCTOR = os.path.join(ROOT, "plugins", "marshal", "scripts", "doctor.sh")


def _run(env_overrides, plugin_root=None):
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root or os.path.join(ROOT, "plugins", "marshal")
    env.update(env_overrides)
    p = subprocess.run(["bash", DOCTOR, "--fix"], capture_output=True, text=True, env=env)
    return p


def test_doctor_blocks_when_plugin_root_missing(tmp_path):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    p = subprocess.run(["bash", DOCTOR, "--fix"], capture_output=True, text=True, env=env)
    out = json.loads(p.stdout)
    assert out["ok"] is False
    assert "CLAUDE_PLUGIN_ROOT" in out["blocked"]
