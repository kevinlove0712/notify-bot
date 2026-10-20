"""First use, diagnostic privacy and shared installation; no real webhooks."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNTIMES = (["node", str(ROOT / "scripts/notify-send.js")],
            [sys.executable, str(ROOT / "scripts/notify-send")])
TOKEN = "private-test-token-never-print"
SECRET = "private-signing-secret-never-print"


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="notify-setup-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "用户 home"
        self.home.mkdir()
        self.config = self.home / ".config/notify-bot/config.json"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("NOTIFY_", "FEISHU_", "WECOM_"))}
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")

    def run_command(self, command, code=0, extra=None):
        result = subprocess.run(command, env={**self.env, **(extra or {})}, cwd=self.home,
                                capture_output=True, text=True, encoding="utf-8", timeout=25)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        return result

    def write_config(self, file=None):
        file = file or self.config
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps({"feishu": {"test": {
            "url": "https://open.feishu.cn/open-apis/bot/v2/hook/" + TOKEN,
            "secret": SECRET}}}), encoding="utf-8")
        file.chmod(0o600)

    def test_init_default_and_no_overwrite(self):
        example = json.loads((ROOT / "examples/config.example.json").read_text(encoding="utf-8"))
        for runtime in RUNTIMES:
            with self.subTest(runtime=runtime[0]):
                result = self.run_command([*runtime, "--init-config"])
                self.assertEqual(json.loads(result.stdout)["path"], str(self.config))
                self.assertEqual(json.loads(self.config.read_text(encoding="utf-8")), example)
                if os.name == "posix":
                    self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
                original = self.config.read_bytes()
                self.run_command([*runtime, "--init-config"], 2)
                self.assertEqual(self.config.read_bytes(), original)
                report = json.loads(self.run_command([*runtime, "--doctor"], 2).stdout)
                self.assertEqual(report["config"]["status"], "incomplete")
                self.run_command([*runtime, "--target", "feishu:工作群", "text", "hi"], 2)
                self.config.unlink()

    def test_diagnostic_missing_has_no_side_effect(self):
        for runtime in RUNTIMES:
            report = json.loads(self.run_command([*runtime, "--doctor"], 2).stdout)
            self.assertEqual(report["config"]["status"], "missing")
            self.assertEqual(report["config"]["path"], str(self.config))
            self.assertFalse(report["network_checked"])
            self.assertTrue(Path(report["runtime"]["executable"]).is_absolute())
            self.assertFalse(self.config.parent.exists())

    def test_config_precedence_and_privacy(self):
        alternate = self.home / "环境 config.json"
        explicit = self.home / "显式 config.json"
        for file in (self.config, alternate, explicit):
            self.write_config(file)
        for runtime in RUNTIMES:
            for args, extra, chosen, source in [
                ([], {}, self.config, "default"),
                ([], {"NOTIFY_CONFIG_FILE": str(alternate)}, alternate, "environment"),
                (["--config", str(explicit)], {"NOTIFY_CONFIG_FILE": str(alternate)}, explicit, "argument"),
            ]:
                report = json.loads(self.run_command([*runtime, "--doctor", *args], extra=extra).stdout)
                self.assertEqual(report["config"]["path"], str(chosen))
                self.assertEqual(report["config"]["source"], source)
                self.assertEqual(report["config"]["targets"], [{"name": "test", "platform": "feishu"}])
                self.assertFalse(report["network_checked"])
                self.assertNotIn("url", report["config"])

    def test_init_respects_explicit_and_environment(self):
        for i, runtime in enumerate(RUNTIMES):
            env_config = self.home / f"env-{i}.json"
            arg_config = self.home / f"arg-{i}.json"
            extra = {"NOTIFY_CONFIG_FILE": str(env_config)}
            self.run_command([*runtime, "--init-config", "--config", str(arg_config)], extra=extra)
            self.assertTrue(arg_config.exists())
            self.assertFalse(env_config.exists())
            self.run_command([*runtime, "--init-config"], extra=extra)
            self.assertTrue(env_config.exists())
            self.assertFalse(self.config.exists())

    def test_invalid_configuration_does_not_echo_input(self):
        self.config.parent.mkdir(parents=True)
        for content, status in [
            ('{"secret":"' + SECRET, "invalid_json"),
            (json.dumps({"feishu": {"test": {"url": TOKEN, "secret": SECRET}}}), "invalid_config"),
            (json.dumps({"targets": {}}), "invalid_config"),
            ("{}", "incomplete"),
        ]:
            self.config.write_text(content, encoding="utf-8")
            for runtime in RUNTIMES:
                report = json.loads(self.run_command([*runtime, "--doctor"], 2).stdout)
                self.assertEqual(report["config"]["status"], status)

    def test_management_modes_reject_send_arguments(self):
        for runtime in RUNTIMES:
            for args in [["--init-config", "--doctor"], ["--init-config", "text", "hello"],
                         ["--doctor", "--target", "test"], ["--doctor", "--dry-run"],
                         ["--init-config", "--url", TOKEN], ["--doctor", "--list-targets"]]:
                self.run_command([*runtime, *args], 2)
        self.assertFalse(self.config.exists())

    def test_curl_preparation_utf8_on_windows_without_sending(self):
        # Capture credential-bearing output privately; assert without echoing it.
        self.write_config()
        body = self.home / "正文.txt"
        body.write_text("中文 curl ✅\r\n下一行", encoding="utf-8", newline="")
        result = subprocess.run([sys.executable, str(ROOT / "examples/curl/prepare-request.py"),
                                 "feishu", "test", str(body)],
                                env={**self.env, "PYTHONIOENCODING": "ascii"}, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        request = result.stdout.decode("utf-8")
        self.assertIn("中文 curl ✅", request)
        self.assertNotIn(SECRET, request)
        self.assertIn('request = "POST"', request)

    def test_permission_errors_are_distinct_without_real_acl_changes(self):
        self.write_config()
        loader = importlib.machinery.SourceFileLoader("setup_bot", str(ROOT / "scripts/notify-send"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        bot = importlib.util.module_from_spec(spec)
        loader.exec_module(bot)
        output = io.StringIO()
        with patch("builtins.open", side_effect=PermissionError()), contextlib.redirect_stdout(output):
            self.assertEqual(bot.main(["--doctor", "--config", str(self.config)]), 2)
        self.assertEqual(json.loads(output.getvalue())["config"]["status"], "permission_denied")
        script = """const fs = require('fs');
const bot = require(process.argv[1]);
fs.readFileSync = () => { const e = new Error('hidden'); e.code = 'EACCES'; throw e; };
bot.main(['--doctor', '--config', process.argv[2]]);"""
        result = self.run_command(["node", "-e", script, str(ROOT / "scripts/notify-send.js"), str(self.config)], 2)
        self.assertEqual(json.loads(result.stdout)["config"]["status"], "permission_denied")

    def test_shared_install_and_conflict_preflight(self):
        installer = ["node", str(ROOT / "scripts/install-shared.js"), "--home", str(self.home), "--claude"]
        root = self.home / ".agents/skills/notify-bot"
        claude = self.home / ".claude/skills/notify-bot"
        claude.mkdir(parents=True)
        sentinel = claude / "keep.txt"
        sentinel.write_text("keep")
        self.run_command(installer, 2)
        self.assertFalse(root.exists())
        self.assertEqual(sentinel.read_text(), "keep")
        sentinel.unlink()
        claude.rmdir()
        self.run_command(installer)
        self.assertTrue(root.joinpath("SKILL.md").is_file())
        self.assertTrue(os.path.samefile(root, claude))
        self.assertFalse(self.config.exists())
        self.run_command(installer, 2)  # Never replace an existing independent copy.

    def test_shared_install_excludes_private_files_and_remains_usable(self):
        source = self.home / "源码 source"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        private_files = [
            ".env", ".env.local", "config.json", "bots.json", "secrets/token.txt",
            ".idea/workspace.xml", "scripts/private.js", "references/notes.md",
            "examples/curl/config.json", "tests/offline/private.txt",
            "unlisted-file.txt",
        ]
        for name in private_files:
            file = source / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(TOKEN, encoding="utf-8")
        installer = ["node", str(source / "scripts/install-shared.js")]
        self.run_command([*installer, "--home", str(self.home), "--claude"])
        installed = self.home / ".agents/skills/notify-bot"
        for name in private_files:
            self.assertFalse((installed / name).exists(), name)
            self.assertEqual((source / name).read_text(encoding="utf-8"), TOKEN)
        for name in ["SKILL.md", "LICENSE", "README.md", "README.en.md",
                     "references/setup.md", "examples/curl/prepare-request.py",
                     "tests/run_tests.py", "tests/offline/block-network.cjs"]:
            self.assertEqual((installed / name).read_bytes(), (source / name).read_bytes())
        for script in [["node", str(installed / "scripts/notify-send.js")],
                       [sys.executable, str(installed / "scripts/notify-send")]]:
            report = self.run_command([*script, "--config", str(installed / "examples/config.example.json"),
                                       "--list-targets"])
            self.assertEqual(len(json.loads(report.stdout)), 4)
        # A copied bundle can be installed again without a Git checkout.
        second_home = self.home / "second home"
        self.run_command(["node", str(installed / "scripts/install-shared.js"),
                          "--home", str(second_home)])
        self.assertTrue((second_home / ".agents/skills/notify-bot/SKILL.md").is_file())

    @unittest.skipIf(os.name == "nt", "File symlinks may require Windows developer mode")
    def test_shared_copy_rejects_symlinked_release_files_and_directories(self):
        source = self.home / "source"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        external = self.home / "private"
        external.mkdir()
        (external / "setup.md").write_text(TOKEN, encoding="utf-8")
        for name in ["references/setup.md", "references"]:
            with self.subTest(name=name):
                entry = source / name
                saved = self.home / "saved"
                entry.rename(saved)
                entry.symlink_to(external if saved.is_dir() else external / "setup.md",
                                 target_is_directory=saved.is_dir())
                install_home = self.home / name.replace("/", "-")
                try:
                    self.run_command(["node", str(source / "scripts/install-shared.js"),
                                      "--home", str(install_home), "--claude"], 2)
                    self.assertFalse(install_home.exists())
                finally:
                    entry.unlink()
                    saved.rename(entry)

    @unittest.skipIf(os.name == "nt", "POSIX symlinks; Windows directory junction is tested above")
    def test_link_source_and_shared_config(self):
        source_config = self.home / "shared.json"
        self.write_config(source_config)
        args = ["node", str(ROOT / "scripts/install-shared.js"), "--home", str(self.home),
                "--link-source", str(ROOT), "--shared-config", str(source_config), "--claude"]
        self.run_command(args)
        self.run_command(args)  # Idempotent links.
        self.assertTrue(os.path.samefile(self.config, source_config))
        self.assertTrue(os.path.samefile(self.home / ".agents/skills/notify-bot", ROOT))
        for runtime in RUNTIMES:
            self.run_command([*runtime, "--doctor"])

    @unittest.skipIf(os.name == "nt", "Requires POSIX symlinks")
    def test_init_refuses_dangling_symlink(self):
        self.config.parent.mkdir(parents=True)
        missing = self.home / "do-not-create.json"
        self.config.symlink_to(missing)
        for runtime in RUNTIMES:
            self.run_command([*runtime, "--init-config"], 2)
        self.assertTrue(self.config.is_symlink())
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
