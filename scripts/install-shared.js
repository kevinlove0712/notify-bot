#!/usr/bin/env node
/** Install a local bundle once, with optional Claude/WSL links. No downloads or sends. */
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

function exists(file) {
  try { fs.lstatSync(file); return true; }
  catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}
function same(a, b) {
  try { return fs.realpathSync(a) === fs.realpathSync(b); }
  catch { return false; }
}
function main(argv) {
  const options = { home: os.homedir(), source: path.resolve(__dirname, '..'), claude: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--help') {
      console.log('node scripts/install-shared.js [--source DIR | --link-source DIR] [--claude] [--shared-config FILE] [--home DIR]\n' +
        '默认复制到 ~/.agents/skills/notify-bot；--claude 添加同源入口。\n' +
        'WSL 可显式 --link-source /mnt/c/.../notify-bot --shared-config /mnt/c/.../config.json。\n' +
        '不下载、不发送、不覆盖已有内容、不修改 shell 配置；--home 指定安装用户目录。');
      return;
    }
    if (argv[i] === '--claude') { options.claude = true; continue; }
    if (!['--source', '--link-source', '--shared-config', '--home'].includes(argv[i]) ||
        !argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error('参数无效，请使用 --help');
    const key = argv[i].slice(2);
    if (Object.hasOwn(options, `seen-${key}`)) throw new Error('请勿重复提供同一选项');
    options[`seen-${key}`] = true;
    options[key] = path.resolve(argv[++i]);
  }
  if (options['seen-source'] && options['link-source']) throw new Error('--source 与 --link-source 不能并用');
  const source = options['link-source'] || options.source;
  for (const file of ['SKILL.md', 'scripts/notify-send.js', 'scripts/notify-send']) {
    if (!fs.statSync(path.join(source, file)).isFile()) throw new Error('源目录不是完整 notify-bot bundle');
  }
  const root = path.join(options.home, '.agents/skills/notify-bot');
  if (!options['link-source'] && !same(root, source) &&
      (root.startsWith(source + path.sep) || source.startsWith(root + path.sep))) {
    throw new Error('源目录与目标目录不能相互嵌套');
  }
  const plan = [{ destination: root, source, kind: options['link-source'] ? 'directory-link' : 'copy' }];
  if (options.claude) plan.push({ destination: path.join(options.home, '.claude/skills/notify-bot'), source: root, kind: 'directory-link' });
  if (options['shared-config']) {
    if (!fs.statSync(options['shared-config']).isFile()) throw new Error('共享配置源必须是已有文件');
    plan.push({ destination: path.join(options.home, '.config/notify-bot/config.json'),
      source: options['shared-config'], kind: 'file-link' });
  }
  // Preflight all destinations before creating any files.
  for (const item of plan) {
    item.reuse = same(item.destination, item.source);
    if (exists(item.destination) && !item.reuse) throw new Error(`目标已存在，未覆盖：${item.destination}`);
  }
  for (const item of plan) {
    if (!item.reuse) {
      fs.mkdirSync(path.dirname(item.destination), { recursive: true, mode: 0o700 });
      if (item.kind === 'copy') {
        // Reserve the destination so a concurrent installer cannot merge files.
        fs.mkdirSync(item.destination);
        fs.cpSync(item.source, item.destination, { recursive: true, force: false, errorOnExist: true,
          filter: file => !['.git', '__pycache__', '.DS_Store'].includes(path.basename(file)) });
      } else {
        fs.symlinkSync(item.source, item.destination,
          item.kind === 'file-link' ? 'file' : process.platform === 'win32' ? 'junction' : 'dir');
      }
    }
  }
  console.log(JSON.stringify({ status: 'installed', entries: plan.map(({ destination, kind, reuse }) =>
    ({ path: destination, kind, reused: reuse })), config_created: false }, null, 2));
}

try { main(process.argv.slice(2)); }
catch (error) {
  const message = error.code ? `安装失败（${error.code}）；请检查路径、目录权限或链接权限。已有文件未自动删除；若部分创建，请检查后再运行。` : error.message;
  console.error(message);
  process.exitCode = 2;
}
