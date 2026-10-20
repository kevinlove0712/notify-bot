"""Exercise the public bundle from a new location without personal configuration."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle_tmp = tempfile.TemporaryDirectory(prefix="notify-distribution-")
        cls.addClassCleanup(cls.bundle_tmp.cleanup)
        cls.bundle = Path(cls.bundle_tmp.name) / "skill with spaces"
        shutil.copytree(ROOT, cls.bundle, ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="notify-clean-home-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("NOTIFY_", "FEISHU_", "WECOM_"))}
        self.env.update(
            HOME=str(self.home), USERPROFILE=str(self.home), PYTHONUTF8="1",
            PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(self.bundle / "tests/offline"),
            NODE_OPTIONS="--require " + json.dumps((self.bundle / "tests/offline/block-network.cjs").as_posix()),
        )
        self.runtimes = (["node", str(self.bundle / "scripts/notify-send.js")],
                         [sys.executable, str(self.bundle / "scripts/notify-send")])

    def run_cli(self, runtime, args, expected=0, extra=None):
        result = subprocess.run([*runtime, *args], cwd=self.home, env={**self.env, **(extra or {})},
                                capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def install_example(self):
        config = self.home / ".config/notify-bot/config.json"
        config.parent.mkdir(parents=True)
        shutil.copyfile(self.bundle / "examples/config.example.json", config)
        config.chmod(0o600)
        return config

    def test_clean_home_preview_needs_no_credentials(self):
        for runtime in self.runtimes:
            for platform, field in [("feishu", "msg_type"), ("wecom", "msgtype")]:
                result = self.run_cli(runtime, ["--platform", platform, "text", "hello", "--dry-run"])
                self.assertEqual(json.loads(result.stdout)[field], "text")
            self.run_cli(runtime, ["--list-targets"], expected=2)
        self.assertFalse((self.home / ".config").exists())

    def test_installed_example_lists_and_previews_both_platforms(self):
        config = self.install_example()
        original = config.read_bytes()
        for runtime in self.runtimes:
            result = self.run_cli(runtime, ["--list-targets"])
            self.assertEqual({(x["platform"], x["name"]) for x in json.loads(result.stdout)},
                             {(p, n) for p in ("feishu", "wecom") for n in ("工作群", "告警群")})
            self.assertNotIn("REPLACE_ME", result.stdout)
            result = self.run_cli(runtime, ["--target", "feishu:工作群", "--target", "wecom:工作群",
                                            "text", "hello", "--dry-run"])
            self.assertEqual([x["platform"] for x in json.loads(result.stdout)], ["feishu", "wecom"])
            self.run_cli(runtime, ["--target", "工作群", "text", "hello", "--dry-run"], expected=2)
        self.assertEqual(config.read_bytes(), original)

    def test_explicit_config_wins_over_environment_and_default(self):
        self.install_example()
        alternate = self.home / "alternate.json"
        alternate.write_text(json.dumps({"wecom": {"alternate": {
            "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"}}}), encoding="utf-8")
        alternate.chmod(0o600)
        sample = self.bundle / "examples/config.example.json"
        for runtime in self.runtimes:
            extra = {"NOTIFY_CONFIG_FILE": str(alternate)}
            result = self.run_cli(runtime, ["--list-targets"], extra=extra)
            self.assertEqual(json.loads(result.stdout), [{"name": "alternate", "platform": "wecom"}])
            result = self.run_cli(runtime, ["--config", str(sample), "--list-targets"], extra=extra)
            self.assertEqual(len(json.loads(result.stdout)), 4)

    def test_examples_use_obvious_placeholder_credentials(self):
        config = json.loads((self.bundle / "examples/config.example.json").read_text(encoding="utf-8"))
        for group in config.values():
            for entry in group.values():
                self.assertRegex(entry["url"], r"REPLACE_ME_[A-Z_]+$")
                self.assertNotIn("secret", entry)

    def test_network_guards_are_active_in_child_processes(self):
        snippets = [
            [sys.executable, "-c", "import socket; socket.create_connection(('127.0.0.1', 9))"],
            ["node", "-e", "require('node:net').connect(9, '127.0.0.1')"],
        ]
        for command in snippets:
            result = subprocess.run(command, cwd=self.home, env=self.env, capture_output=True,
                                    text=True, encoding="utf-8", timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Real network connections are disabled in tests", result.stderr)

    def test_document_links_resolve_inside_bundle(self):
        for doc in self.bundle.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
                if link.startswith(("https://", "http://", "#", "mailto:")):
                    continue
                target = (doc.parent / unquote(link.split("#", 1)[0])).resolve()
                self.assertTrue(target.is_relative_to(self.bundle.resolve()), (doc.name, link))
                self.assertTrue(target.is_file(), (doc.name, link))


if __name__ == "__main__":
    unittest.main(verbosity=2)
