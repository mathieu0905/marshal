import errno
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class NetworkOffLauncherTests(unittest.TestCase):
    def test_filter_is_inherited_by_exec(self):
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "probe.json"
            command = [
                sys.executable,
                "run_network_off.py",
                "--probe-output",
                str(probe),
                "--",
                sys.executable,
                "-c",
                (
                    "import errno,socket; "
                    "\ntry: socket.socket()"
                    "\nexcept OSError as e: raise SystemExit(0 if e.errno == errno.EPERM else 2)"
                    "\nraise SystemExit(3)"
                ),
            ]
            completed = subprocess.run(command, check=False)
            evidence = json.loads(probe.read_text(encoding="utf-8"))
        self.assertEqual(0, completed.returncode)
        self.assertTrue(evidence["socket_probe_blocked"])
        self.assertEqual(errno.EPERM, evidence["socket_probe_errno"])
