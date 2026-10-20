#!/usr/bin/env python3
"""Run the full suite with isolated user configuration and no real connections."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    node = shutil.which("node")
    if not node:
        print("Tests require both Node.js and Python.", file=sys.stderr)
        return 2
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("NOTIFY_", "FEISHU_", "WECOM_"))}
    env.update(
        PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
        PYTHONPATH=str(ROOT / "tests/offline"),
        NODE_OPTIONS="--require " + json.dumps((ROOT / "tests/offline/block-network.cjs").as_posix()),
    )
    with tempfile.TemporaryDirectory(prefix="notify-test-home-") as home_dir:
        env.update(HOME=home_dir, USERPROFILE=home_dir)
        commands = [
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
            [node, "tests/test_transport.js"],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, env=env, timeout=180)
            if result.returncode:
                return result.returncode
    print("All offline tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
