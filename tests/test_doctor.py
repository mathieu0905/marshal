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


def test_doctor_auto_installs_uv_via_stub(tmp_path):
    # 假 PATH:无 uv;stub installer 往 fakebin 放一个 uv,再确认 doctor 标记 fixed。
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    installer = tmp_path / "install_uv.sh"
    installer.write_text(
        "#!/usr/bin/env bash\n"
        f"cat > {fakebin}/uv <<'EOF'\n#!/usr/bin/env bash\necho 'uv 0.0-stub'\nEOF\n"
        f"chmod +x {fakebin}/uv\n")
    installer.chmod(0o755)

    env = {
        # 把 fakebin 放最前;真实系统目录在后(供 python3/bash)
        "PATH": f"{fakebin}:/usr/bin:/bin",
        "MARSHAL_UV_INSTALLER": f"bash {installer}",
        # 跳过 env/seed 两步(本测试只验 uv 这一步)
        "MARSHAL_DOCTOR_SKIP_ENV": "1",
        "MARSHAL_DOCTOR_SKIP_SEED": "1",
    }
    p = _run(env)
    out = json.loads(p.stdout)
    assert out["ok"] is True, p.stdout + p.stderr
    assert "uv" in out["fixed"]
