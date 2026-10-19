#!/usr/bin/env node
/** 飞书/企业微信群机器人 webhook 发送 CLI（Node.js >= 18，零依赖）。 */
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const os = require('os');
const https = require('https');

const KIB = 1024;
const MIB = 1024 * KIB;
const FEISHU_MAX_BODY = 20 * KIB;
const WECOM_TEXT_MAX = 2048;
const WECOM_MD_MAX = 4096;
const WECOM_IMAGE_MAX = 2 * MIB;
const WECOM_FILE_MAX = 20 * MIB;
const WECOM_VOICE_MAX = 2 * MIB;
const FEISHU_COLORS = new Set(['blue', 'green', 'grey', 'orange', 'red', 'turquoise', 'violet', 'wathet']);

const FEISHU_ERR = {
  19001: 'webhook token 无效', 9499: '请求体格式错误或超 20 KiB',
  19021: '签名不匹配或 timestamp 过期', 19022: 'IP 不在白名单',
  19024: '消息不含自定义关键词', 11232: '触发限流',
  11227: 'image_key 无效（飞书图片需先通过应用机器人上传）',
  11246: '卡片包含无效 image_key',
};

class NotifyError extends Error {
  constructor(message, exitCode = 2) { super(message.replace(/https?:\/\/[^\s"'<>]+/g, '[地址已隐藏]')); this.exitCode = exitCode; }
}

function fail(message, exitCode = 2) { throw new NotifyError(message, exitCode); }
function envValue(key) { return process.env[key] || ''; }
function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function readText(file) {
  try { return fs.readFileSync(file === '-' ? 0 : file, 'utf8'); }
  catch { fail('无法读取输入文件（路径及内容已隐藏）'); }
}
function parseJson(text, label) {
  try { return JSON.parse(text); }
  catch { fail(`JSON 解析失败：${label}（内容已隐藏）`); }
}

function readConfig(file) {
  const location = path.resolve(file);
  let source, stat;
  try {
    stat = fs.statSync(location);
    source = fs.readFileSync(location, 'utf8');
  } catch (error) {
    fail(`${error.code === 'ENOENT' ? '配置文件不存在' : '无法读取配置文件'}：${location}`);
  }
  if (process.platform !== 'win32' && (stat.mode & 0o077)) {
    console.error('警告：配置文件包含组/其他用户权限，建议 chmod 600；脚本未修改权限');
  }
  return parseJson(source, `配置文件 ${location}`);
}

function platformMessage(result, url, secret = '') {
  let message = result.msg || result.errmsg;
  if (typeof message !== 'string' || !message.trim()) return '';
  const parsed = new URL(url);
  const token = parsed.hostname === 'qyapi.weixin.qq.com' ? parsed.searchParams.get('key') : parsed.pathname.split('/').filter(Boolean).pop();
  for (const credential of [url, token, secret]) {
    if (!credential) continue;
    for (const value of [credential, encodeURIComponent(credential)]) message = message.split(value).join('[凭证已隐藏]');
  }
  message = message.replace(/https?:\/\/[^\s"'<>]+/g, '[地址已隐藏]').replace(/[\x00-\x1f\x7f]/g, ' ');
  return `；平台提示：${message.slice(0, 500)}`;
}

function resolveTargets(args) {
  if (args.target.length || args.listTargets) {
    if (args.url) fail('--target/--list-targets 不能与 --url 混用');
    const file = args.config || envValue('NOTIFY_CONFIG_FILE') || path.join(os.homedir(), '.config/notify-bot/config.json');
    const config = readConfig(file);
    if (!isObject(config)) fail('配置需要按 feishu/wecom 分组的对象');
    if (Object.hasOwn(config, 'targets')) fail('旧 targets 配置需要迁移为 feishu/wecom 分组');
    const catalog = [];
    for (const [platform, group] of Object.entries(config)) {
      if (!['feishu', 'wecom'].includes(platform) || !isObject(group)) fail('配置平台仅支持 feishu/wecom，且分组必须是对象');
      for (const [name, entry] of Object.entries(group)) {
        if (!name.trim() || /[:\x00-\x1f\x7f]/.test(name) || !isObject(entry)) fail('目标名称不能为空或含冒号/控制字符，目标配置必须是对象');
        catalog.push({ name, platform, entry });
      }
    }
    if (args.listTargets) {
      return catalog.filter(target => !args.platform || target.platform === args.platform)
        .map(({ name, platform }) => ({ name, platform }));
    }
    const targets = args.target.map(selector => {
      let name = selector;
      let platform = args.platform;
      if (selector.includes(':')) {
        const separator = selector.indexOf(':');
        const qualifiedPlatform = selector.slice(0, separator);
        name = selector.slice(separator + 1);
        if (!['feishu', 'wecom'].includes(qualifiedPlatform)) fail('目标前缀仅支持 feishu: 或 wecom:');
        if (platform && platform !== qualifiedPlatform) fail('--platform 与 --target 平台前缀不一致');
        platform = qualifiedPlatform;
      }
      const matches = catalog.filter(target => target.name === name && (!platform || target.platform === platform));
      if (!matches.length) fail('目标名称不存在，请使用 --list-targets 查看');
      if (matches.length > 1) fail('目标名称在多个平台存在，请指定 --platform 或使用 平台:名称');
      const selected = matches[0];
      const entry = selected.entry;
      if (typeof entry.url !== 'string') fail('目标必须包含 url 字符串');
      if (detectPlatform(entry.url) !== selected.platform) fail('目标 URL 与所在平台分组不匹配');
      if (entry.secret !== undefined && typeof entry.secret !== 'string') fail('目标 secret 必须是字符串');
      if (selected.platform !== 'feishu' && entry.secret) fail('secret 仅飞书支持');
      // Named targets never inherit another bot's global signing secret.
      return { name: selected.name, platform: selected.platform, url: entry.url, secret: entry.secret || '' };
    });
    if (new Set(targets.map(target => webhookIdentity(target.url))).size !== targets.length) fail('重复目标或多个名称指向同一个 webhook，请只选择一个');
    return targets;
  }
  if (args.config) fail('--config 需要同时指定 --target 或 --list-targets');
  const specific = args.platform === 'feishu' ? 'FEISHU_WEBHOOK_URL' : args.platform === 'wecom' ? 'WECOM_WEBHOOK_URL' : '';
  const url = args.url || (specific && envValue(specific)) || envValue('NOTIFY_WEBHOOK_URL');
  if (!url && !(args.dryRun && args.platform)) fail('缺少 webhook；请使用 --target、--url 或配置环境变量');
  const platform = url ? detectPlatform(url) : args.platform;
  if (args.platform && args.platform !== platform) fail('--platform 与 webhook 指向的平台不一致');
  return [{ name: platform, platform, url: url || '', secret: platform === 'feishu' ? envValue('FEISHU_WEBHOOK_SECRET') : '' }];
}

function webhookIdentity(url) {
  const parsed = new URL(url);
  return parsed.hostname === 'qyapi.weixin.qq.com' ? `wecom:${parsed.searchParams.get('key')}` : `feishu:${parsed.pathname.replace(/\/$/, '')}`;
}

function detectPlatform(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    fail('webhook 地址不是有效 URL（地址已隐藏）');
  }
  if (parsed.username || parsed.password || parsed.hash || (parsed.port && parsed.port !== '443')) fail('webhook 不允许用户信息、片段或非标准端口（地址已隐藏）');
  if (parsed.protocol !== 'https:') fail('webhook 必须使用 HTTPS（地址已隐藏）');

  if (parsed.hostname === 'open.feishu.cn' &&
      /^\/open-apis\/bot\/v2\/hook\/[^/]+\/?$/.test(parsed.pathname)) {
    return 'feishu';
  }
  if (parsed.hostname === 'qyapi.weixin.qq.com' &&
      parsed.pathname === '/cgi-bin/webhook/send' && parsed.searchParams.get('key')) {
    return 'wecom';
  }
  fail('webhook 域名或接口路径不受支持（地址已隐藏）');
}

function loadJsonArg(value) {
  const input = String(value).trim();
  const inline = input.startsWith('{') || input.startsWith('[');
  const label = inline ? '内联参数' : input === '-' ? 'stdin' : path.basename(input).replace(/https?:\/\/\S+/g, '[地址已隐藏]');
  const result = parseJson(inline ? input : readText(input), label);
  if (!isObject(result)) fail('JSON 顶层必须是对象');
  return result;
}

function byteLength(value) {
  return Buffer.byteLength(value, 'utf8');
}

function requireFile(filePath) {
  let stat;
  try {
    stat = fs.statSync(filePath);
  } catch {
    fail(`文件不存在：${filePath}`);
  }
  if (!stat.isFile()) fail(`不是普通文件：${filePath}`);
  return stat;
}

function validateUploadFile(command, filePath) {
  const stat = requireFile(filePath);
  if (stat.size <= 5) fail('企微上传文件必须大于 5 字节');
  const max = command === 'voice' ? WECOM_VOICE_MAX : WECOM_FILE_MAX;
  if (stat.size > max) fail(`${command === 'voice' ? '语音' : '文件'}超过 ${max / MIB} MiB 限制`);
  if (command === 'voice') {
    const header = fs.readFileSync(filePath).subarray(0, 6).toString('ascii');
    if (path.extname(filePath).toLowerCase() !== '.amr' || header !== '#!AMR\n') fail('企微语音仅支持带有效文件头的 AMR 文件');
  }
}

function readWecomImage(filePath) {
  const stat = requireFile(filePath);
  if (stat.size === 0 || stat.size > WECOM_IMAGE_MAX) fail('企微图片必须大于 0 且不超过 2 MiB');
  const buffer = fs.readFileSync(filePath);
  const png = buffer.length >= 8 && buffer.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex'));
  const jpeg = buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff;
  if (!png && !jpeg) fail('企微图片仅支持 JPG 或 PNG');
  return buffer;
}

function buildText(platform, args) {
  const content = args.positional.join(' ');
  if (platform === 'feishu') {
    let text = content;
    if (args.atAll) text = '<at user_id="all">所有人</at> ' + text;
    for (const userId of args.at) {
      if (!/^[A-Za-z0-9_-]+$/.test(userId)) fail(`飞书用户 ID 格式无效：${userId}`);
      text += ` <at user_id="${userId}"></at>`;
    }
    return { msg_type: 'text', content: { text } };
  }

  if (byteLength(content) > WECOM_TEXT_MAX) fail('企微文本正文超过 2048 字节');
  const text = { content };
  const userIds = [...args.at];
  if (args.atAll) userIds.push('@all');
  if (userIds.length) text.mentioned_list = userIds;
  if (args.atMobile.length) {
    for (const mobile of args.atMobile) {
      if (!/^\+?\d{5,20}$/.test(mobile)) fail(`手机号格式无效：${mobile}`);
    }
    text.mentioned_mobile_list = args.atAll ? [...args.atMobile, '@all'] : args.atMobile;
  }
  return { msgtype: 'text', text };
}

function buildMarkdown(platform, args) {
  let content = args.positional.join(' ');
  if (platform === 'feishu') {
    if (args.color && !FEISHU_COLORS.has(args.color)) fail(`不支持的飞书卡片颜色：${args.color}`);
    const card = {
      schema: '2.0',
      body: {
        direction: 'vertical', padding: '12px 12px 12px 12px',
        elements: [{ tag: 'markdown', content, text_align: 'left', text_size: 'normal_v2', margin: '0px 0px 8px 0px' }],
      },
    };
    if (args.title) card.header = {
      title: { tag: 'plain_text', content: args.title },
      template: args.color || 'blue', padding: '12px 12px 12px 12px',
    };
    return { msg_type: 'interactive', card };
  }

  if (args.title) content = `## ${args.title}\n${content}`;
  if (byteLength(content) > WECOM_MD_MAX) fail('企微 Markdown 正文超过 4096 字节');
  return { msgtype: 'markdown', markdown: { content } };
}

function buildImage(platform, value) {
  if (platform === 'feishu') return { msg_type: 'image', content: { image_key: value } };
  const buffer = readWecomImage(value);
  return {
    msgtype: 'image',
    image: {
      base64: buffer.toString('base64'),
      md5: crypto.createHash('md5').update(buffer).digest('hex'),
    },
  };
}

function requestJson(url, options, timeoutMs, insecure = false) {
  return new Promise((resolve, reject) => {
    const request = https.request(url, { ...options, rejectUnauthorized: !insecure }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('error', () => { clearTimeout(timer); reject(new NotifyError('响应中断，发送结果未知，请勿直接重试', 3)); });
      response.on('end', () => {
        clearTimeout(timer);
        try {
          const result = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (!isObject(result)) throw new Error();
          const field = new URL(url).hostname === 'open.feishu.cn' ? 'code' : 'errcode';
          if ((response.statusCode < 200 || response.statusCode >= 300) &&
              (!Number.isInteger(result[field]) || result[field] === 0)) throw new Error();
          resolve(result);
        } catch { reject(new NotifyError(`HTTP ${response.statusCode} 响应无法确认，发送结果未知，请勿直接重试`, 3)); }
      });
    });
    const timer = setTimeout(() => request.destroy(new Error('timeout')), timeoutMs);
    request.on('error', error => {
      clearTimeout(timer);
      const tlsErrors = ['CERT_HAS_EXPIRED', 'DEPTH_ZERO_SELF_SIGNED_CERT', 'SELF_SIGNED_CERT_IN_CHAIN', 'UNABLE_TO_VERIFY_LEAF_SIGNATURE', 'UNABLE_TO_GET_ISSUER_CERT_LOCALLY', 'ERR_TLS_CERT_ALTNAME_INVALID'];
      reject(tlsErrors.includes(error.code)
        ? new NotifyError('TLS 证书校验失败，请配置可信 CA；未降级重试', 1)
        : new NotifyError('网络异常或超时，发送结果未知，请勿直接重试', 3));
    });
    request.end(options.body);
  });
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function retryLimited(operation, platform, retries, wait = sleep) {
  const field = platform === 'feishu' ? 'code' : 'errcode';
  const rateCode = platform === 'feishu' ? 11232 : 45009;
  for (let attempt = 0; ; attempt++) {
    const result = await operation();
    const code = result[field];
    if (!Number.isInteger(code)) fail('响应缺少有效业务状态码，发送结果未知，请勿直接重试', 3);
    if (code !== rateCode) return result;
    if (attempt >= retries) fail(`限流 code=${code}，重试次数已耗尽`, 4);
    const delay = Math.min(60, (platform === 'feishu' ? 5 : 60) * 2 ** attempt);
    console.error(`限流，${delay} 秒后重试（${attempt + 1}/${retries}）`);
    await wait(delay * 1000);
  }
}

async function postJson(target, payload, args) {
  const result = await retryLimited(() => requestJson(target.url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(preparePayload(target, payload)),
  }, 15000, args.insecure), target.platform, args.retry);
  const code = result[target.platform === 'feishu' ? 'code' : 'errcode'];
  if (code !== 0) fail(`发送失败 code=${code}${FEISHU_ERR[code] ? '；' + FEISHU_ERR[code] : ''}${platformMessage(result, target.url, target.secret)}`, 1);
}

function feishuSign(timestamp, secret) {
  return crypto.createHmac('sha256', `${timestamp}\n${secret}`).update('').digest('base64');
}

function preparePayload(target, payload) {
  if (target.platform !== 'feishu') return payload;
  payload = { ...payload };
  if (target.secret) {
    const timestamp = String(Math.floor(Date.now() / 1000));
    payload = { ...payload, timestamp, sign: feishuSign(timestamp, target.secret) };
  }
  if (byteLength(JSON.stringify(payload)) > FEISHU_MAX_BODY) fail('飞书请求体超过 20 KiB');
  return payload;
}

async function wecomUpload(webhook, type, filePath, args) {
  const key = new URL(webhook).searchParams.get('key');
  if (!key) fail('企微 webhook 缺少 key（地址已隐藏）');

  const data = fs.readFileSync(filePath);
  const boundary = `----notifybot-${crypto.randomBytes(12).toString('hex')}`;
  const filename = path.basename(filePath).replace(/["\\\r\n]/g, '_');
  const contentType = type === 'voice' ? 'audio/amr' : 'application/octet-stream';
  const header = Buffer.from(
    `--${boundary}\r\nContent-Disposition: form-data; name="media"; filename="${filename}"; filelength=${data.length}\r\n` +
    `Content-Type: ${contentType}\r\n\r\n`);
  const footer = Buffer.from(`\r\n--${boundary}--\r\n`);
  const body = Buffer.concat([header, data, footer]);
  const uploadUrl = `https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key=${encodeURIComponent(key)}&type=${type}`;
  const result = await retryLimited(() => requestJson(uploadUrl, {
    method: 'POST',
    headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}`, 'Content-Length': String(body.length) },
    body,
  }, 60000, args.insecure), 'wecom', args.retry);
  if (result.errcode !== 0) fail(`上传失败 errcode=${result.errcode}${platformMessage(result, webhook)}`, 1);
  if (typeof result.media_id !== 'string' || !result.media_id) fail('上传成功响应缺少 media_id；消息尚未发送', 1);
  return result.media_id;
}

function parseArgs(argv) {
  const valueOptions = new Set(['--url', '--platform', '--at', '--at-mobile', '--title', '--color', '--target', '--config', '--retry', '--body-file']);
  const booleanOptions = new Set(['--at-all', '--dry-run', '--insecure', '--list-targets', '--help']);
  const args = {
    cmd: null, positional: [], at: [], atMobile: [], atAll: false,
    target: [], config: null, retry: 0, bodyFile: null, insecure: false, listTargets: false, help: false,
    dryRun: false, platform: null, url: null, title: null, color: null, used: new Set(),
  };
  let parseOptions = true;

  for (let index = 0; index < argv.length; index++) {
    const token = argv[index];
    if (parseOptions && token === '--') {
      parseOptions = false;
      continue;
    }
    if (parseOptions && token.startsWith('--')) {
      if (booleanOptions.has(token)) {
        args.used.add(token);
        if (token === '--at-all') args.atAll = true;
        else if (token === '--dry-run') args.dryRun = true;
        else if (token === '--list-targets') args.listTargets = true;
        else if (token === '--help') args.help = true;
        else args.insecure = true;
        continue;
      }
      if (!valueOptions.has(token)) fail('未知选项（参数已隐藏），请使用 --help');
      const value = argv[index + 1];
      if (value === undefined || value.startsWith('--')) fail(`选项 ${token} 缺少值`);
      index++;
      args.used.add(token);
      if (token === '--target') args.target.push(value);
      else if (token === '--body-file') args.bodyFile = value;
      else if (token === '--at') args.at.push(value);
      else if (token === '--at-mobile') args.atMobile.push(value);
      else args[token.slice(2)] = value;
      continue;
    }
    if (!args.cmd) args.cmd = token;
    else args.positional.push(token);
  }
  return args;
}

function validateArgs(args, platform) {
  if (args.platform && args.platform !== platform) fail('--platform 与 --url 指向的平台不一致');

  const allowed = {
    text: new Set(['--url', '--platform', '--dry-run', '--at-all', '--at', '--at-mobile']),
    md: new Set(['--url', '--platform', '--dry-run', '--title', '--color']),
    image: new Set(['--url', '--platform', '--dry-run']),
    file: new Set(['--url', '--platform', '--dry-run']),
    voice: new Set(['--url', '--platform', '--dry-run']),
    news: new Set(['--url', '--platform', '--dry-run']),
    card: new Set(['--url', '--platform', '--dry-run']),
    post: new Set(['--url', '--platform', '--dry-run']),
    raw: new Set(['--url', '--platform', '--dry-run']),
  }[args.cmd];
  for (const option of ['--target', '--config', '--retry', '--insecure', '--help']) allowed.add(option);
  if (['text', 'md'].includes(args.cmd)) allowed.add('--body-file');
  for (const option of args.used) if (!allowed.has(option)) fail(`${args.cmd} 不支持选项 ${option}`);

  if ((args.cmd === 'text' || args.cmd === 'md') && args.positional.length === 0) fail(`${args.cmd} 需要正文`);
  if (!['text', 'md'].includes(args.cmd) && args.positional.length !== 1) fail(`${args.cmd} 需要且只接受一个参数`);
  if (platform === 'feishu' && args.atMobile.length) fail('--at-mobile 仅企业微信支持');
  if (['file', 'voice', 'news'].includes(args.cmd) && platform !== 'wecom') fail(`${args.cmd} 仅企业微信支持`);
  if (args.cmd === 'post' && platform !== 'feishu') fail('post 仅飞书支持');
}

function buildPayload(platform, args) {
  let payload;
  switch (args.cmd) {
    case 'text': payload = buildText(platform, args); break;
    case 'md': payload = buildMarkdown(platform, args); break;
    case 'image': payload = buildImage(platform, args.positional[0]); break;
    case 'file': case 'voice': payload = {}; break;
    case 'news': {
      const news = loadJsonArg(args.positional[0]);
      if (!news || !Array.isArray(news.articles) || news.articles.length < 1 || news.articles.length > 8) {
        fail('news 需要包含 1–8 条 articles');
      }
      payload = { msgtype: 'news', news };
      break;
    }
    case 'post': payload = { msg_type: 'post', content: { post: loadJsonArg(args.positional[0]) } }; break;
    case 'card': payload = platform === 'feishu'
      ? { msg_type: 'interactive', card: loadJsonArg(args.positional[0]) }
      : { msgtype: 'template_card', template_card: loadJsonArg(args.positional[0]) };
      break;
    case 'raw':
      payload = loadJsonArg(args.positional[0]);
      if (typeof payload[platform === 'feishu' ? 'msg_type' : 'msgtype'] !== 'string' || !payload[platform === 'feishu' ? 'msg_type' : 'msgtype']) fail('raw 缺少对应平台的消息类型');
      break;
  }

  return payload;
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (args.help) {
    console.log('notify-send [--platform feishu/wecom] [--target 名称或平台:名称（可重复） | --url URL] <text/md/image/file/voice/news/card/post/raw> [正文]' +
      '\n选项：--config FILE --list-targets --dry-run --body-file FILE（- 表示 stdin） --retry 0..5 --insecure\n正文以 - 开头时可用 -- 分隔。');
    return;
  }
  if (!/^\d+$/.test(String(args.retry)) || Number(args.retry) > 5) fail('--retry 必须为 0–5 的整数（额外尝试次数）');
  args.retry = Number(args.retry);
  if (args.platform && !['feishu', 'wecom'].includes(args.platform)) fail('--platform 仅支持 feishu 或 wecom');
  if (args.listTargets) {
    if (args.cmd || args.target.length || [...args.used].some(x => !['--config', '--list-targets', '--platform'].includes(x))) fail('--list-targets 只接受 --config 和 --platform');
    console.log(JSON.stringify(resolveTargets(args), null, 2));
    return;
  }
  if (!['text', 'md', 'image', 'file', 'voice', 'news', 'card', 'post', 'raw'].includes(args.cmd)) fail('缺少或无效子命令；请使用 --help');
  if (args.bodyFile !== null) {
    if (!['text', 'md'].includes(args.cmd) || args.positional.length) fail('--body-file 仅用于 text/md，不能同时提供正文');
    args.positional = [readText(args.bodyFile)];
  }
  if (['text', 'md'].includes(args.cmd) && !args.positional.join(' ').trim()) fail('正文不能为空');
  const targets = resolveTargets(args);
  if (targets.length > 1 && !['text', 'md'].includes(args.cmd)) fail('多目标发送仅支持 text/md');
  if (args.at.length && new Set(targets.map(target => target.platform)).size > 1) fail('跨平台发送不能使用 --at，请按平台分别发送');
  const plans = targets.map(target => {
    validateArgs(args, target.platform);
    const payload = buildPayload(target.platform, args);
    if (['file', 'voice'].includes(args.cmd)) validateUploadFile(args.cmd, args.positional[0]);
    preparePayload(target, payload);
    return { target, payload };
  });
  if (args.dryRun) {
    const preview = plans.map(({ target, payload }) => ({ target: target.name, platform: target.platform,
      payload: ['file', 'voice'].includes(args.cmd) ? { upload_required: true, msgtype: args.cmd } : payload }));
    console.log(JSON.stringify(preview.length === 1 ? preview[0].payload : preview, null, 2));
    return;
  }
  if (args.insecure) console.error('警告：本次显式关闭 TLS 证书校验');
  const results = [];
  for (const { target, payload: initial } of plans) {
    try {
      let payload = initial;
      if (['file', 'voice'].includes(args.cmd)) {
        const mediaId = await wecomUpload(target.url, args.cmd, args.positional[0], args);
        payload = { msgtype: args.cmd, [args.cmd]: { media_id: mediaId } };
      }
      await postJson(target, payload, args);
      results.push({ target: target.name, platform: target.platform, status: 'sent', exit_code: 0 });
    } catch (error) {
      const code = error instanceof NotifyError ? error.exitCode : 3;
      results.push({ target: target.name, platform: target.platform, status: code === 3 ? 'unknown' : 'failed', exit_code: code,
        error: error instanceof NotifyError ? error.message : '执行异常，发送结果未知，请勿直接重试' });
    }
  }
  console.log(JSON.stringify({ results }, null, 2));
  const codes = results.map(result => result.exit_code);
  process.exitCode = codes.includes(3) ? 3 : codes.find(code => code !== 0) || 0;
}

if (require.main === module) main().catch(error => {
  console.error(`错误：${error instanceof NotifyError ? error.message : '本地输入或配置读取失败（详情已隐藏）'}`);
  process.exitCode = error instanceof NotifyError ? error.exitCode : 2;
});
module.exports = { main, NotifyError, requestJson, retryLimited, postJson, preparePayload, feishuSign };
