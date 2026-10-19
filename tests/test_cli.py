#!/usr/bin/env python3
"""Offline CLI parity, target routing and delivery tests. No real webhook calls."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNTIMES = (["node", str(ROOT / "scripts/notify-send.js")], [sys.executable, str(ROOT / "scripts/notify-send")])
FEISHU = "https://open.feishu.cn/open-apis/bot/v2/hook/test-token"
WECOM = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"
loader = importlib.machinery.SourceFileLoader("notify_send", str(ROOT / "scripts/notify-send"))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith(("NOTIFY_", "FEISHU_", "WECOM_"))}
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home), PYTHONDONTWRITEBYTECODE="1")
        self.config = self.home / "bots.json"
        self.targets = {"feishu": {"工作群": {"url": FEISHU},
                                   "second": {"url": FEISHU + "-second", "secret": "second-secret"}},
                        "wecom": {"alerts": {"url": WECOM}}}
        self.save_config()

    def save_config(self):
        self.config.write_text(json.dumps(self.targets), encoding="utf-8")
        self.config.chmod(0o600)

    def run_cli(self, runtime, args, stdin=None, extra=None):
        return subprocess.run([*runtime, *args], input=stdin, env={**self.env, **(extra or {})},
                              capture_output=True, text=True, timeout=15)

    def both(self, args, code=0, stdin=None, extra=None):
        results = [self.run_cli(runtime, args, stdin, extra) for runtime in RUNTIMES]
        for result in results:
            self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        if code == 0:
            self.assertEqual(json.loads(results[0].stdout), json.loads(results[1].stdout))
        return results

    def test_payload_parity(self):
        for args in [
            ["--platform", "wecom", "text", "--at-all", "你好"],
            ["--platform", "feishu", "text", "--at", "ou_test", "你好"],
            ["--platform", "feishu", "md", "--title", "报告", "--color", "green", "**成功**"],
            ["--platform", "wecom", "md", "--title", "告警", "内容"],
            ["--platform", "wecom", "text", "-hello"],
            ["--platform", "wecom", "text", "--", "--status ok"],
        ]:
            self.both(["--dry-run", *args])

    def test_named_selection(self):
        for name, field in [("工作群", "msg_type"), ("alerts", "msgtype"), ("second", "msg_type")]:
            result = self.both(["--config", str(self.config), "--target", name, "text", "--dry-run", "hello"])[0]
            self.assertIn(field, json.loads(result.stdout))
            self.assertNotIn("second-secret", result.stdout)
            self.assertNotIn("sign", json.loads(result.stdout))

    def test_multi_preview(self):
        result = self.both(["--config", str(self.config), "--target", "工作群", "text", "--target", "alerts", "--dry-run", "hello"])[0]
        self.assertEqual([x["target"] for x in json.loads(result.stdout)], ["工作群", "alerts"])

    def test_default_and_environment_config(self):
        default = self.home / ".config/notify-bot/config.json"
        default.parent.mkdir(parents=True)
        default.write_bytes(self.config.read_bytes())
        self.both(["--target", "alerts", "text", "--dry-run", "hi"])
        self.both(["--target", "alerts", "text", "--dry-run", "hi"], extra={"NOTIFY_CONFIG_FILE": str(self.config)})
        self.both(["text", "hi"], code=2)  # Never auto-select a target.

    def test_list_without_credentials(self):
        result = self.both(["--config", str(self.config), "--list-targets"])[0]
        self.assertNotIn("test-token", result.stdout)
        self.assertNotIn("second-secret", result.stdout)
        self.assertEqual(len(json.loads(result.stdout)), 3)

    def test_configuration_failures(self):
        prefix = ["--config", str(self.config), "--target", "alerts"]
        for tail in [["--url", WECOM], ["--platform", "feishu"], ["--target", "alerts"], ["--target", "missing"]]:
            self.both([*prefix, *tail, "text", "--dry-run", "hi"], code=2)
        self.targets["wecom"]["alias"] = dict(self.targets["wecom"]["alerts"])
        self.save_config()
        self.both([*prefix, "--target", "alias", "text", "--dry-run", "hi"], code=2)
        self.targets["wecom"]["alerts"]["url"] = FEISHU
        self.save_config()
        self.both([*prefix, "text", "--dry-run", "hi"], code=2)

    def test_platform_scoped_names(self):
        self.targets["wecom"]["工作群"] = {"url": WECOM + "-work"}
        self.save_config()
        for platform, field in [("feishu", "msg_type"), ("wecom", "msgtype")]:
            result = self.both(["--config", str(self.config), "--platform", platform, "--target", "工作群", "text", "--dry-run", "hi"])[0]
            self.assertIn(field, json.loads(result.stdout))
            qualified = self.both(["--config", str(self.config), "--target", platform + ":工作群", "text", "--dry-run", "hi"])[0]
            self.assertEqual(json.loads(result.stdout), json.loads(qualified.stdout))
        self.both(["--config", str(self.config), "--target", "工作群", "text", "--dry-run", "hi"], code=2)

    def test_qualified_multi_and_conflicts(self):
        self.targets["wecom"]["工作群"] = {"url": WECOM + "-work"}
        self.save_config()
        prefix = ["--config", str(self.config)]
        result = self.both([*prefix, "--target", "feishu:工作群", "--target", "wecom:工作群", "text", "--dry-run", "hi"])[0]
        self.assertEqual([item["platform"] for item in json.loads(result.stdout)], ["feishu", "wecom"])
        self.both([*prefix, "--platform", "feishu", "--target", "wecom:工作群", "text", "--dry-run", "hi"], code=2)
        self.both([*prefix, "--platform", "feishu", "--target", "工作群", "--target", "feishu:工作群", "text", "--dry-run", "hi"], code=2)
        self.both([*prefix, "--target", "other:工作群", "text", "--dry-run", "hi"], code=2)

    def test_group_listing_and_same_platform_multi(self):
        prefix = ["--config", str(self.config), "--platform", "feishu"]
        result = self.both([*prefix, "--list-targets"])[0]
        self.assertEqual([item["name"] for item in json.loads(result.stdout)], ["工作群", "second"])
        result = self.both([*prefix, "--target", "工作群", "--target", "second", "md", "--dry-run", "hi"])[0]
        self.assertEqual([item["platform"] for item in json.loads(result.stdout)], ["feishu", "feishu"])

    def test_scoped_send_uses_only_selected_link(self):
        self.targets["wecom"]["工作群"] = {"url": WECOM + "-work"}
        self.save_config()
        for platform, name, url, reply in [("feishu", "second", FEISHU + "-second", {"code": 0}),
                                           ("wecom", "工作群", WECOM + "-work", {"errcode": 0})]:
            with patch.object(module, "request_json", return_value=reply) as request, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(["--config", str(self.config), "--platform", platform, "--target", name, "text", "hi"]), 0)
                self.assertEqual(request.call_count, 1)
                self.assertEqual(request.call_args.args[0].full_url, url)

    def test_group_schema_validation(self):
        for config in [{"targets": {}}, {"other": {}}, {"feishu": []}, {"feishu": {"bad:name": {"url": FEISHU}}}]:
            self.config.write_text(json.dumps(config))
            self.both(["--config", str(self.config), "--list-targets"], code=2)

    def test_cross_platform_mentions_rejected(self):
        prefix = ["--config", str(self.config), "--target", "feishu:工作群", "--target", "wecom:alerts", "text"]
        self.both([*prefix, "--at", "ou_test", "--dry-run", "hi"], code=2)
        self.both([*prefix, "--at-all", "--dry-run", "hi"])
        self.both(["--config", str(self.config), "--platform", "feishu", "--target", "工作群", "--target", "second", "text", "--at", "ou_test", "--dry-run", "hi"])
        with patch.object(module, "request_json", side_effect=AssertionError("must not send")) as send:
            with self.assertRaises(module.NotifyError) as caught:
                module.main([*prefix, "--at", "ou_test", "hi"])
            self.assertEqual(caught.exception.exit_code, 2)
            send.assert_not_called()

    def test_config_missing_message_and_permissions(self):
        missing = self.home / "missing.json"
        for result in self.both(["--config", str(missing), "--list-targets"], code=2):
            self.assertIn("配置文件不存在", result.stderr)
            self.assertIn(str(missing), result.stderr)
        for result in self.both(["--list-targets"], code=2):
            self.assertIn(str(self.home / ".config/notify-bot/config.json"), result.stderr)
        if os.name == "posix":
            self.config.chmod(0o644)
            for result in self.both(["--config", str(self.config), "--list-targets"]):
                self.assertIn("600", result.stderr)
                self.assertIn("警告", result.stderr)
            self.config.chmod(0o600)
            for result in self.both(["--config", str(self.config), "--list-targets"]):
                self.assertEqual(result.stderr, "")

    def test_environment_fallback_and_no_shell_read(self):
        self.both(["--platform", "wecom", "text", "--dry-run", "hi"], extra={"NOTIFY_WEBHOOK_URL": WECOM})
        self.both(["--platform", "feishu", "text", "--dry-run", "hi"], code=2, extra={"NOTIFY_WEBHOOK_URL": WECOM})
        (self.home / ".zshenv").write_text('export WECOM_WEBHOOK_URL="' + WECOM + '"\n')
        self.both(["--platform", "wecom", "text", "hi"], code=2)

    def test_body_file_and_stdin(self):
        body = "多行\n`echo no` $(do-not-run) $HOME \' \\\"\n"
        file = self.home / "body.txt"
        file.write_text(body)
        for source in [str(file), "-"]:
            result = self.both(["--platform", "wecom", "text", "--dry-run", "--body-file", source], stdin=body)[0]
            self.assertEqual(json.loads(result.stdout)["text"]["content"], body)
        self.both(["--platform", "wecom", "text", "--dry-run", "--body-file", str(file), "extra"], code=2)

    def test_json_validation(self):
        for command, value in [("raw", "[]"), ("raw", "{}"), ("card", "[]"), ("news", '{"articles":[]}')]:
            self.both(["--platform", "wecom", command, "--dry-run", value], code=2)
        bad = self.home / "card.json"
        bad.write_text('{"secret":"test-sensitive",bad}')
        for result in self.both(["--platform", "wecom", "card", "--dry-run", str(bad)], code=2):
            self.assertIn("card.json", result.stderr)
            self.assertNotIn("test-sensitive", result.stderr)
        self.both(["--platform", "wecom", "raw", "--dry-run", "-"], stdin='{"msgtype":"text","text":{"content":"hi"}}')

    def test_url_validation_and_redaction(self):
        for url in ["https://evil.example/?open.feishu.cn&token=private", FEISHU.replace("https://", "http://"),
                    FEISHU.replace("https://", "https://user:private@"), FEISHU.replace(".cn/", ".cn:9999/"),
                    FEISHU + "#private"]:
            for result in self.both(["--url", url, "text", "--dry-run", "hi"], code=2):
                self.assertNotIn("private", result.stderr)
                self.assertNotIn(url, result.stderr)

    def test_limits(self):
        self.both(["--platform", "wecom", "text", "--dry-run", "中" * 682])
        self.both(["--platform", "wecom", "text", "--dry-run", "中" * 683], code=2)
        self.both(["--platform", "feishu", "text", "--dry-run", "x" * 20438])
        self.both(["--platform", "feishu", "text", "--dry-run", "x" * 20480], code=2)
        self.both(["--platform", "wecom", "text", "--dry-run", ""], code=2)
        self.both(["--platform", "wecom", "text", "hi", "--at", "--dry-run"], code=2)
        for retry in ["-1", "6", "1.5"]:
            self.both(["--platform", "wecom", "text", "--dry-run", "hi", "--retry", retry], code=2)

    def test_upload_preflight(self):
        file = self.home / "file.bin"
        file.write_bytes(b"12345")
        self.both(["--platform", "wecom", "file", "--dry-run", str(file)], code=2)
        file.write_bytes(b"123456")
        self.both(["--platform", "wecom", "file", "--dry-run", str(file)])
        amr = self.home / "voice.amr"
        amr.write_bytes(b"not audio")
        self.both(["--platform", "wecom", "voice", "--dry-run", str(amr)], code=2)
        amr.write_bytes(b"#!AMR\n\x00")
        self.both(["--platform", "wecom", "voice", "--dry-run", str(amr)])
        png = self.home / "image.png"
        png.write_bytes(bytes.fromhex("89504e470d0a1a0a") + b"test")
        self.both(["--platform", "wecom", "image", "--dry-run", str(png)])

    def test_multi_preflight_no_send(self):
        args = ["--config", str(self.config), "--target", "工作群", "--target", "alerts", "text", "x" * 2049]
        with patch.object(module, "request_json", side_effect=AssertionError("must not send")) as send:
            with self.assertRaises(module.NotifyError):
                module.main(args)
            send.assert_not_called()

    def test_target_secrets_and_partial_results(self):
        calls = []
        def request(req, timeout, insecure=False):
            calls.append((req.full_url, json.loads(req.data)))
            return {"code": 0} if len(calls) == 1 else {"errcode": 45009}
        args = ["--config", str(self.config), "--target", "second", "--target", "alerts", "text", "hi"]
        with patch.object(module, "request_json", side_effect=request), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(module.main(args), 4)
        results = json.loads(out.getvalue())["results"]
        self.assertEqual([x["exit_code"] for x in results], [0, 4])
        self.assertEqual(calls[0][0], FEISHU + "-second")
        self.assertEqual(calls[0][1]["sign"], module.feishu_sign(calls[0][1]["timestamp"], "second-secret"))
        self.assertNotIn("sign", calls[1][1])

    def test_upload_reuses_media_and_message_retry(self):
        file = self.home / "report.txt"
        file.write_text("123456")
        calls = []
        replies = iter([{"errcode": 0, "media_id": "media-test"}, {"errcode": 45009}, {"errcode": 0}])
        def request(req, timeout, insecure=False):
            calls.append(req)
            return next(replies)
        original = module.retry_limited
        def fast_retry(operation, platform, retries):
            return original(operation, platform, retries, lambda _: None)
        with patch.object(module, "request_json", side_effect=request), patch.object(module, "retry_limited", side_effect=fast_retry), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(module.main(["--url", WECOM, "--retry", "1", "file", str(file)]), 0)
        self.assertEqual(sum("upload_media" in req.full_url for req in calls), 1)
        self.assertEqual(calls[1].data, calls[2].data)
        self.assertEqual(json.loads(calls[1].data)["file"]["media_id"], "media-test")

    def test_signatures_refresh_on_retry(self):
        bodies = []
        replies = iter([{"code": 11232}, {"code": 0}])
        def request(req, timeout, insecure=False):
            bodies.append(json.loads(req.data))
            return next(replies)
        original = module.retry_limited
        with patch.object(module, "request_json", side_effect=request), patch.object(module.time, "time", side_effect=[100, 101, 102]), patch.object(module, "retry_limited", side_effect=lambda op, platform, retries: original(op, platform, retries, lambda _: None)), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(module.main(["--config", str(self.config), "--target", "second", "--retry", "1", "text", "hi"]), 0)
        self.assertEqual([body["timestamp"] for body in bodies], ["101", "102"])
        self.assertNotEqual(bodies[0]["sign"], bodies[1]["sign"])

    def test_named_target_never_inherits_global_secret(self):
        with patch.dict(os.environ, {"FEISHU_WEBHOOK_SECRET": "wrong-global-secret"}), patch.object(module, "request_json", return_value={"code": 0}) as request, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(["--config", str(self.config), "--target", "工作群", "text", "hi"]), 0)
            self.assertNotIn("sign", json.loads(request.call_args.args[0].data))


class DeliveryTests(unittest.TestCase):
    def test_retry_only_explicit_rate_limit(self):
        for platform, field, code in [("feishu", "code", 11232), ("wecom", "errcode", 45009)]:
            replies = iter([{field: code}, {field: code}, {field: 0}])
            waits = []
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.retry_limited(lambda: next(replies), platform, 2, waits.append), {field: 0})
            self.assertEqual(waits, [5, 10] if platform == "feishu" else [60, 60])
            with self.assertRaises(module.NotifyError) as caught:
                module.retry_limited(lambda: {field: code}, platform, 0)
            self.assertEqual(caught.exception.exit_code, 4)
        with self.assertRaises(module.NotifyError) as caught:
            module.retry_limited(lambda: {}, "feishu", 3)
        self.assertEqual(caught.exception.exit_code, 3)
        self.assertEqual(module.retry_limited(lambda: {"code": 19021}, "feishu", 3), {"code": 19021})

    def test_non_2xx_business_errors_and_redacted_messages(self):
        cases = [("feishu", FEISHU, {"code": 9499}, 1),
                 ("wecom", WECOM, {"errcode": 40013}, 1),
                 ("feishu", FEISHU, {"code": 11232}, 4),
                 ("feishu", FEISHU, {"code": 0}, 3),
                 ("feishu", FEISHU, {"errcode": 9499}, 3)]
        for platform, url, data, expected in cases:
            data = {**data, "msg" if platform == "feishu" else "errmsg":
                    "keyword missing: abc " + url + " bare test-token test-key private-secret"}
            response = module.urllib.error.HTTPError(url, 400, "ignored", {}, io.BytesIO(json.dumps(data).encode()))
            with patch.object(module.urllib.request, "build_opener") as build:
                build.return_value.open.side_effect = response
                with self.assertRaises(module.NotifyError) as caught:
                    module.post_json({"platform": platform, "url": url, "secret": "private-secret"}, {}, module.SimpleNamespace(retry=0, insecure=False))
                self.assertEqual(caught.exception.exit_code, expected)
                self.assertEqual(build.return_value.open.call_count, 1)
                if expected == 1:
                    self.assertIn("keyword missing: abc", str(caught.exception))
                    self.assertNotIn(url, str(caught.exception))
                    self.assertNotIn("test-token" if platform == "feishu" else "test-key", str(caught.exception))
                    self.assertNotIn("private-secret", str(caught.exception))

    def test_http_error_body_read_failure_is_unknown(self):
        class BrokenBody(io.BytesIO):
            def read(self, *_args):
                raise TimeoutError()
        response = module.urllib.error.HTTPError(FEISHU, 400, "ignored", {}, BrokenBody())
        with patch.object(module.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = response
            with self.assertRaises(module.NotifyError) as caught:
                module.request_json(module.urllib.request.Request(FEISHU), 1)
            self.assertEqual(caught.exception.exit_code, 3)

    def test_unknown_not_retried(self):
        with patch.object(module, "request_json", side_effect=module.NotifyError("unknown", 3)) as request:
            target = {"platform": "feishu", "url": FEISHU, "secret": ""}
            with self.assertRaises(module.NotifyError):
                module.post_json(target, {}, module.SimpleNamespace(retry=5, insecure=False))
            self.assertEqual(request.call_count, 1)

    def test_strict_tls_no_fallback(self):
        reason = module.ssl.SSLCertVerificationError(1, "private")
        with patch.object(module.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = module.urllib.error.URLError(reason)
            with self.assertRaises(module.NotifyError) as caught:
                module.request_json(module.urllib.request.Request(FEISHU), 1)
            self.assertEqual(caught.exception.exit_code, 1)
            self.assertEqual(build.return_value.open.call_count, 1)
            handler = build.call_args.args[1]
            self.assertEqual(handler._context.verify_mode, module.ssl.CERT_REQUIRED)
            with self.assertRaises(module.NotifyError):
                module.request_json(module.urllib.request.Request(FEISHU), 1, True)
            self.assertEqual(build.call_args.args[1]._context.verify_mode, module.ssl.CERT_NONE)

    def test_transport_errors_and_redirect(self):
        for error in [TimeoutError(), module.http.client.IncompleteRead(b"partial"),
                      module.urllib.error.HTTPError(FEISHU, 502, "private", {}, None)]:
            with patch.object(module.urllib.request, "build_opener") as build:
                build.return_value.open.side_effect = error
                with self.assertRaises(module.NotifyError) as caught:
                    module.request_json(module.urllib.request.Request(FEISHU), 1)
                self.assertEqual(caught.exception.exit_code, 3)
                self.assertNotIn("private", str(caught.exception))
        self.assertIsNone(module.NoRedirect().redirect_request(None, None, 307, "", {}, "https://evil.example"))

    def test_response_parse(self):
        for body in [b"invalid", b"[]", b"null"]:
            with patch.object(module.urllib.request, "build_opener") as build:
                response = build.return_value.open.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = body
                with self.assertRaises(module.NotifyError) as caught:
                    module.request_json(module.urllib.request.Request(FEISHU), 1)
                self.assertEqual(caught.exception.exit_code, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
