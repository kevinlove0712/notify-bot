#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const https = require('node:https');
const bot = require('../scripts/notify-send.js');
const FEISHU = 'https://open.feishu.cn/open-apis/bot/v2/hook/test-token';
const WECOM = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key';

async function mockTransport(replies, run) {
  const original = https.request;
  const calls = [];
  https.request = (url, options, receive) => {
    const request = new EventEmitter();
    request.destroy = error => request.emit('error', error);
    request.end = body => {
      calls.push({ url, options, body });
      queueMicrotask(() => {
        const reply = replies.shift();
        if (!reply) { request.emit('error', new Error('Unexpected request')); return; }
        if (reply.error) { request.emit('error', reply.error); return; }
        const response = new EventEmitter();
        response.statusCode = reply.status || 200;
        receive(response);
        if (reply.broken) { response.emit('error', new Error('private')); return; }
        response.emit('data', Buffer.from(reply.body === undefined ? JSON.stringify(reply.json) : reply.body));
        response.emit('end');
      });
    };
    return request;
  };
  try { return await run(calls); } finally { https.request = original; }
}

async function capturedMain(args) {
  let out = '';
  const original = console.log;
  const previousCode = process.exitCode;
  console.log = value => { out += value; };
  process.exitCode = 0;
  try { await bot.main(args); return { code: process.exitCode, value: out ? JSON.parse(out) : null }; }
  finally { console.log = original; process.exitCode = previousCode; }
}

async function main() {
  let count = 0;
  async function test(name, run) { await run(); console.log(`PASS ${name}`); count++; }
  await test('TLS strict default and explicit insecure', async () => {
    await mockTransport([{ json: { code: 0 } }, { json: { code: 0 } }], async calls => {
      await bot.requestJson(FEISHU, { method: 'POST', body: '{}' }, 100);
      await bot.requestJson(FEISHU, { method: 'POST', body: '{}' }, 100, true);
      assert.equal(calls[0].options.rejectUnauthorized, true);
      assert.equal(calls[1].options.rejectUnauthorized, false);
    });
    await mockTransport([{ error: Object.assign(new Error('private'), { code: 'CERT_HAS_EXPIRED' }) }], async calls => {
      await assert.rejects(bot.requestJson(FEISHU, {}, 100), e => e.exitCode === 1 && !e.message.includes('private'));
      assert.equal(calls.length, 1);
    });
  });
  await test('Unknown outcomes, HTTP errors and redirects never retried', async () => {
    for (const reply of [{ error: new Error('private') }, { broken: true }, { body: 'invalid' }, { body: '[]' }, { status: 502, body: '' }, { status: 307, body: '' }]) {
      await mockTransport([reply], async calls => {
        await assert.rejects(bot.postJson({ url: FEISHU, platform: 'feishu', secret: '' }, {}, { retry: 5, insecure: false }), e => e.exitCode === 3 && !e.message.includes('private'));
        assert.equal(calls.length, 1);
      });
    }
  });
  await test('HTTP business errors are classified and diagnostic messages redacted', async () => {
    for (const [platform, url, data, expected] of [
      ['feishu', FEISHU, { code: 9499 }, 1], ['wecom', WECOM, { errcode: 40013 }, 1],
      ['feishu', FEISHU, { code: 11232 }, 4], ['feishu', FEISHU, { code: 0 }, 3],
      ['feishu', FEISHU, { errcode: 9499 }, 3],
    ]) {
      const reply = { ...data, [platform === 'feishu' ? 'msg' : 'errmsg']: `keyword missing: abc ${url} bare test-token test-key private-secret` };
      await mockTransport([{ status: 400, json: reply }], async calls => {
        await assert.rejects(bot.postJson({ url, platform, secret: 'private-secret' }, {}, { retry: 0, insecure: false }), error => {
          assert.equal(error.exitCode, expected);
          if (expected === 1) {
            assert.ok(error.message.includes('keyword missing: abc'));
            assert.ok(!error.message.includes(url));
            assert.ok(!error.message.includes(platform === 'feishu' ? 'test-token' : 'test-key'));
            assert.ok(!error.message.includes('private-secret'));
          }
          return true;
        });
        assert.equal(calls.length, 1);
      });
    }
  });
  await test('Only explicit rate-limit codes trigger bounded backoff', async () => {
    for (const [platform, field, rate, expected] of [['feishu', 'code', 11232, [5000, 10000]], ['wecom', 'errcode', 45009, [60000, 60000]]]) {
      const replies = [{ [field]: rate }, { [field]: rate }, { [field]: 0 }];
      const delays = [];
      assert.deepEqual(await bot.retryLimited(async () => replies.shift(), platform, 2, async ms => delays.push(ms)), { [field]: 0 });
      assert.deepEqual(delays, expected);
      await assert.rejects(bot.retryLimited(async () => ({ [field]: rate }), platform, 0), e => e.exitCode === 4);
    }
    await assert.rejects(bot.retryLimited(async () => ({}), 'feishu', 5), e => e.exitCode === 3);
    assert.deepEqual(await bot.retryLimited(async () => ({ code: 19021 }), 'feishu', 5), { code: 19021 });
  });
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'notify-tests-'));
  try {
    const config = path.join(dir, 'bots.json');
    fs.writeFileSync(config, JSON.stringify({
      feishu: { a: { url: FEISHU, secret: 'target-secret' } },
      wecom: { b: { url: WECOM } },
    }));
    fs.chmodSync(config, 0o600);
    await test('Scoped name routes to exactly one selected link', async () => {
      const scopedConfig = path.join(dir, 'scoped.json');
      fs.writeFileSync(scopedConfig, JSON.stringify({
        feishu: { work: { url: FEISHU }, other: { url: FEISHU + '-other' } },
        wecom: { work: { url: WECOM } },
      }));
      fs.chmodSync(scopedConfig, 0o600);
      for (const [platform, name, url, reply] of [['feishu', 'other', FEISHU + '-other', { code: 0 }], ['wecom', 'work', WECOM, { errcode: 0 }]]) {
        await mockTransport([{ json: reply }], async calls => {
          const result = await capturedMain(['--config', scopedConfig, '--platform', platform, '--target', name, 'text', 'hello']);
          assert.equal(result.code, 0);
          assert.equal(calls.length, 1);
          assert.equal(calls[0].url, url);
        });
      }
    });
    await test('Cross-platform mention fails before any request', async () => {
      await mockTransport([], async calls => {
        await assert.rejects(capturedMain(['--config', config, '--target', 'a', '--target', 'b', 'text', '--at', 'ou_test', 'hello']), e => e.exitCode === 2);
        assert.equal(calls.length, 0);
      });
    });
    await test('All selected targets preflight before the first send', async () => {
      await mockTransport([], async calls => {
        await assert.rejects(capturedMain(['--config', config, '--target', 'a', '--target', 'b', 'text', 'x'.repeat(2049)]), e => e.exitCode === 2);
        assert.equal(calls.length, 0);
      });
    });
    await test('Named target secret and independent partial results', async () => {
      await mockTransport([{ json: { code: 0 } }, { json: { errcode: 45009 } }], async calls => {
        const result = await capturedMain(['--config', config, '--target', 'a', '--target', 'b', 'text', 'hello']);
        assert.equal(result.code, 4);
        assert.deepEqual(result.value.results.map(x => x.exit_code), [0, 4]);
        const first = JSON.parse(calls[0].body);
        assert.equal(first.sign, bot.feishuSign(first.timestamp, 'target-secret'));
        assert.equal(JSON.parse(calls[1].body).sign, undefined);
      });
    });
    await test('First target failure still allows second target to send', async () => {
      await mockTransport([{ error: new Error('timeout') }, { json: { errcode: 0 } }], async calls => {
        const result = await capturedMain(['--config', config, '--target', 'a', '--target', 'b', 'text', 'hello']);
        assert.equal(result.code, 3);
        assert.deepEqual(result.value.results.map(x => x.exit_code), [3, 0]);
        assert.equal(calls.length, 2);
      });
    });
    await test('Uploaded media reused when message is rate limited', async () => {
      const file = path.join(dir, 'report.txt');
      fs.writeFileSync(file, '123456');
      // Accelerate retry waits only; transport deadlines remain unchanged.
      const originalTimeout = global.setTimeout;
      global.setTimeout = (callback, ms, ...args) => originalTimeout(callback, ms === 60000 && args.length === 0 ? 1 : ms, ...args);
      try {
        await mockTransport([{ json: { errcode: 0, media_id: 'media-test' } }, { json: { errcode: 45009 } }, { json: { errcode: 0 } }], async calls => {
          const result = await capturedMain(['--url', WECOM, '--retry', '1', 'file', file]);
          assert.equal(result.code, 0);
          assert.equal(calls.filter(x => x.url.includes('upload_media')).length, 1);
          assert.equal(JSON.parse(calls[1].body).file.media_id, 'media-test');
          assert.equal(calls[1].body, calls[2].body);
        });
      } finally { global.setTimeout = originalTimeout; }
    });
    await test('Raw signing fields cannot override the selected target signature', async () => {
      const payload = bot.preparePayload({ platform: 'feishu', secret: 'correct' }, { timestamp: 'old', sign: 'old', msg_type: 'text' });
      assert.notEqual(payload.timestamp, 'old');
      assert.equal(payload.sign, bot.feishuSign(payload.timestamp, 'correct'));
    });
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  console.log(`PASS ${count} transport groups`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
