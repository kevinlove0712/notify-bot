"""Cross-platform UTF-8 and path regressions; all commands are offline."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIMES = (["node", str(ROOT / "scripts/notify-send.js")],
            [sys.executable, str(ROOT / "scripts/notify-send")])


class EncodingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="notify-encoding-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "中文 folder"
        self.directory.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("NOTIFY_", "FEISHU_", "WECOM_"))}

    def run_cli(self, runtime, args, data=None, extra=None, expected=0):
        result = subprocess.run([*runtime, *args], input=data, capture_output=True,
                                env={**self.env, **(extra or {})}, timeout=15)
        self.assertEqual(result.returncode, expected, result.stderr.decode("utf-8"))
        return result

    def test_utf8_bom_configuration_and_unicode_path(self):
        config = self.directory / "群配置.json"
        settings = {"wecom": {"工作群 🙂": {
            "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"}}}
        config.write_bytes(json.dumps(settings, ensure_ascii=False).encode("utf-8-sig"))
        config.chmod(0o600)
        for runtime in RUNTIMES:
            result = self.run_cli(runtime, ["--config", str(config), "--list-targets"])
            self.assertEqual(json.loads(result.stdout), [{"name": "工作群 🙂", "platform": "wecom"}])

    def test_utf8_bom_json_file_and_stdin(self):
        payload = {"msgtype": "text", "text": {"content": "你好 🙂"}}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8-sig")
        file = self.directory / "消息.json"
        file.write_bytes(data)
        for runtime in RUNTIMES:
            for source in [str(file), "-"]:
                result = self.run_cli(runtime, ["--platform", "wecom", "raw", source, "--dry-run"], data)
                self.assertEqual(json.loads(result.stdout), payload)

    def test_body_preserves_line_endings_and_embedded_bom(self):
        body = "第一行 🙂\r\n第二行\n第三行\r末尾\ufeff\r\n"
        file = self.directory / "正文.txt"
        for encoding in ["utf-8", "utf-8-sig"]:
            data = body.encode(encoding)
            file.write_bytes(data)
            for runtime in RUNTIMES:
                for source in [str(file), "-"]:
                    result = self.run_cli(runtime, [
                        "--platform", "wecom", "text", "--body-file", source, "--dry-run"], data)
                    self.assertEqual(json.loads(result.stdout)["text"]["content"], body)

    def test_redirected_streams_ignore_legacy_python_encoding(self):
        # Simulate a legacy Windows pipe encoding without relying on the CI locale.
        extra = {"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
        for runtime in RUNTIMES:
            result = self.run_cli(runtime, [
                "--platform", "wecom", "text", "--body-file", "-", "--dry-run"],
                "你好 🙂\r\n".encode("utf-8"), extra)
            self.assertEqual(json.loads(result.stdout.decode("utf-8"))["text"]["content"], "你好 🙂\r\n")
            error = self.run_cli(runtime, ["--config", str(self.directory / "不存在.json"),
                                          "--list-targets"], extra=extra, expected=2)
            self.assertIn("配置文件不存在", error.stderr.decode("utf-8"))
            self.assertNotIn(b"Traceback", error.stderr)

    def test_attachment_with_unicode_and_spaces_in_path(self):
        attachment = self.directory / "附件 report.txt"
        attachment.write_bytes("附件内容".encode("utf-8"))
        for runtime in RUNTIMES:
            result = self.run_cli(runtime, ["--platform", "wecom", "file", str(attachment), "--dry-run"])
            self.assertEqual(json.loads(result.stdout), {"upload_required": True, "msgtype": "file"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
