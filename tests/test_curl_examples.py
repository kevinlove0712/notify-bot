"""Run shell examples against a fake curl; never contact a webhook."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Bash curl examples are tested on Linux/macOS only")
class CurlExamplesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='notify-curl-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.config = self.home / 'config.json'
        self.settings = {
            'feishu': {'work': {'url': 'https://open.feishu.cn/open-apis/bot/v2/hook/test-token', 'secret': 'test-secret'}},
            'wecom': {'work': {'url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key'}},
        }
        self.save()
        self.body = self.home / 'message with spaces.txt'
        self.body.write_text('你好\n"quotes" \\ `echo nope` $(nope)\n', encoding='utf-8')
        self.capture = self.home / 'capture.json'
        bin_dir = self.home / 'bin'
        bin_dir.mkdir()
        fake = bin_dir / 'curl'
        fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
path = pathlib.Path(os.environ['CURL_TEST_CAPTURE'])
calls = json.loads(path.read_text()) if path.exists() else []
calls.append({'argv': sys.argv[1:], 'config': sys.stdin.read()})
path.write_text(json.dumps(calls))
print(os.environ.get('CURL_TEST_RESPONSE', '{"code":0}\\nHTTP_STATUS=200'))
sys.exit(int(os.environ.get('CURL_TEST_EXIT', '0')))
''', encoding='utf-8')
        fake.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('NOTIFY_', 'FEISHU_', 'WECOM_'))}
        self.env.update(PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                        HOME=str(self.home), USERPROFILE=str(self.home),
                        CURL_TEST_CAPTURE=str(self.capture), PYTHONDONTWRITEBYTECODE='1')

    def save(self):
        self.config.write_text(json.dumps(self.settings), encoding='utf-8')
        self.config.chmod(0o600)

    def run_example(self, platform, extra=None):
        return subprocess.run(['bash', str(ROOT / 'examples/curl' / (platform + '-text.sh')),
                               'work', str(self.body), '--config', str(self.config)],
                              cwd=self.home, env={**self.env, **(extra or {})},
                              capture_output=True, text=True, timeout=15)

    def captured(self):
        calls = json.loads(self.capture.read_text())
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['argv'], ['-q', '--config', '-'])
        config = dict((key, json.loads(value)) for key, value in
                      (line.split(' = ', 1) for line in calls[0]['config'].splitlines() if ' = ' in line))
        return calls[0]['config'], config, json.loads(config['data-binary'])

    def test_feishu_text_and_signature(self):
        result = self.run_example('feishu')
        self.assertEqual(result.returncode, 0, result.stderr)
        raw, config, payload = self.captured()
        self.assertEqual(payload['content']['text'], self.body.read_text())
        key = (payload['timestamp'] + '\ntest-secret').encode()
        self.assertEqual(payload['sign'], base64.b64encode(hmac.new(key, b'', hashlib.sha256).digest()).decode())
        self.assertEqual(config['proto'], '=https')
        self.assertEqual(config['max-time'], '15')
        self.assertIn('\ngloboff\n', raw)
        self.assertNotIn('test-token', result.stdout + result.stderr)
        self.assertNotIn('test-secret', raw)

    def test_wecom_payload_without_feishu_signing(self):
        result = self.run_example('wecom', {'FEISHU_WEBHOOK_SECRET': 'unused-global-secret'})
        self.assertEqual(result.returncode, 0, result.stderr)
        _, _, payload = self.captured()
        self.assertEqual(payload, {'msgtype': 'text', 'text': {'content': self.body.read_text()}})

    def test_unsigned_feishu_has_no_signature(self):
        del self.settings['feishu']['work']['secret']
        self.save()
        self.assertEqual(self.run_example('feishu').returncode, 0)
        self.assertNotIn('sign', self.captured()[2])

    def test_invalid_config_and_empty_body_never_start_curl(self):
        self.settings['wecom']['work']['url'] = 'https://invalid.example/test-key'
        self.save()
        result = self.run_example('wecom')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.capture.exists())
        self.assertNotIn('test-key', result.stderr)
        self.body.write_text(' ')
        self.assertEqual(self.run_example('feishu').returncode, 2)
        self.assertFalse(self.capture.exists())

    def test_curl_timeout_preserved_without_retry(self):
        result = self.run_example('wecom', {'CURL_TEST_EXIT': '28', 'CURL_TEST_RESPONSE': 'HTTP_STATUS=000'})
        self.assertEqual(result.returncode, 28)
        self.assertIn('请勿自动重试', result.stderr)
        self.captured()  # Exactly one attempt.

    def test_business_failure_is_raw_not_cli_success(self):
        response = '{"errcode":45009,"errmsg":"rate limited"}\nHTTP_STATUS=400'
        result = self.run_example('wecom', {'CURL_TEST_RESPONSE': response})
        self.assertEqual(result.returncode, 0)  # curl semantics, documented explicitly.
        self.assertEqual(result.stdout.strip(), response)
        self.captured()

    def test_real_curl_accepts_config_syntax_without_network(self):
        curl = shutil.which('curl')
        if not curl:
            self.skipTest('curl not installed')
        self.assertEqual(self.run_example('feishu').returncode, 0)
        raw = self.captured()[0]
        result = subprocess.run([curl, '-q', '--config', '-', '--help'], input=raw,
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
