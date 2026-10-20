# notify-bot

[English](README.en.md) | 简体中文

[![Offline tests](https://github.com/kevinlove0712/notify-bot/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/kevinlove0712/notify-bot/actions/workflows/test.yml)
[![Install with skills.sh](https://img.shields.io/badge/skills.sh-install-blue)](https://skills.sh/kevinlove0712/notify-bot/notify-bot)

让 Agent 或命令行通过飞书、企业微信群机器人发送通知。按平台管理多个命名群，一次调用可向多个目标发送文本或 Markdown。

Node.js / Python 双实现，无需安装第三方运行依赖。两版通过 HTTPS 发送，接受相同的 CLI 参数，共用独立配置文件。

## 能做什么

- 通过 `--platform feishu --target 工作群` 精确选择一个群；跨平台使用多个 `--target 平台:名称`。
- 文本、Markdown，以及各平台支持的图片、文件、语音、图文、卡片和富文本；详见[平台差异](references/cli-reference.md#平台能力与限制)。
- 默认校验证书；仅对明确的限流响应执行显式启用的重试，结果未知时不自动重发。
- 返回逐目标 JSON 结果和分类退出码，支持不联网的 `--dry-run` 与 `--list-targets`。

本项目使用自定义群机器人 webhook，不能读取群消息、撤回消息，也不提供飞书应用机器人的文件上传能力。多目标调用仅支持 `text` / `md`；没有隐式群发或 `--platform all`。

## 环境与安装

运行时任选其一：Node.js 18+，或 Python 3.10+。建议使用仍受维护的运行时版本。Node/Python 主 CLI 支持 macOS、Linux 和 Windows，CI 覆盖这三个系统。完整测试需要同时安装 Node 和 Python；curl 示例仅在 macOS/Linux 的 Bash 环境验证。

克隆仓库，或下载源码并解压为 `notify-bot` 目录。无需 `npm install` 或 `pip install`：

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/kevinlove0712/notify-bot.git
cd notify-bot
```

上述命令固定使用 `v0.2.0`；也可下载 [v0.2.0 源码包](https://github.com/kevinlove0712/notify-bot/archive/refs/tags/v0.2.0.zip)。要跟随开发分支，克隆时省略 `--branch v0.2.0 --depth 1`。

在仓库根目录选择一个运行时：

```bash
# 两种运行方式，任选一种
node scripts/notify-send.js --help
python3 scripts/notify-send --help
```

### 通过 skills CLI 安装为 Agent Skill

在 [skills.sh 查看 notify-bot](https://skills.sh/kevinlove0712/notify-bot/notify-bot)，或使用下面的命令安装。

也可以在需要使用该 skill 的项目目录运行，按提示选择 Agent：

```bash
npx skills add kevinlove0712/notify-bot --skill notify-bot
```

[skills CLI](https://github.com/vercel-labs/skills#install-a-skill) 当前需要 Node.js 22.20+；这是安装器的要求，notify-bot 本身仍可使用 Node.js 18+ 或 Python 3.10+。默认安装到当前项目，添加 `-g` 可全局安装。此命令安装仓库默认分支的当前内容；需要固定 `v0.2.0` 时，使用上面的版本克隆方式。已有同名 skill 时先备份，避免覆盖本地修改。

手动安装时，将完整目录放入你的 Agent 支持的 skills 目录，保留 `SKILL.md`、`scripts/` 和文档的相对位置。安装位置由所用 Agent 决定；可先用命令行独立试用。

### 升级

已通过 skills CLI 安装的用户，按安装范围选择一条，仅更新 notify-bot：

```bash
npx skills update notify-bot --global
# 项目安装：在原项目目录执行
npx skills update notify-bot --project
```

先备份 skill 内的本地修改，外置 webhook 配置无需重建。默认分支安装会跟随默认分支更新；固定版本请使用上面的版本克隆方式。手动复制或 `install-shared.js` 安装的用户需先迁移，具体步骤和更新后检查见[升级与迁移](references/setup.md#升级与迁移)。

### 全局共享与首次配置

将当前完整源码安装为一份多 Agent 共享 skill：

```bash
node scripts/install-shared.js --claude
```

主目录为 `~/.agents/skills/notify-bot`，Claude 通过同源链接使用；已有目录不覆盖。初始化配置另用 `node scripts/notify-send.js --init-config`，固定存放于 `~/.config/notify-bot/config.json`，不放在 skill 目录内。填写 webhook 并删除不用的占位目标后运行 `node scripts/notify-send.js --doctor`，它仅诊断运行时和配置，不联网或输出凭证。也可用 Python 执行对应 CLI 参数。

WSL 共用 Windows 文件需显式链接，完整命令与环境区分见[环境与共享安装](references/setup.md)。这些功能自 `v0.2.0` 起提供。

### Windows / PowerShell

Windows Node/Python 支持自 `v0.2.0` 起提供，可使用上述版本克隆命令或 skills CLI 安装。若 PowerShell 阻止 `npx.ps1`，使用 `npx.cmd skills add kevinlove0712/notify-bot --skill notify-bot`，无需调整系统执行策略。

推荐 PowerShell 7。以下命令在仓库根目录运行，配置已存在时不会覆盖：

```powershell
node .\scripts\notify-send.js --init-config
node .\scripts\notify-send.js --list-targets
node .\scripts\notify-send.js --platform wecom text '预览 🙂' --dry-run
# Python 替代方式，选择其中一种运行时即可
python .\scripts\notify-send --platform wecom text '预览 🙂' --dry-run
```

若 Python 安装提供的是 `py` 启动器，可将 `python` 换成 `py -3`，先确认版本至少 3.10。配置默认位于 `%USERPROFILE%\.config\notify-bot\config.json`；Windows 使用文件 ACL，不执行 `chmod`。替换配置占位地址后才可真实发送。

配置、正文和 JSON 文件使用 UTF-8，允许文件开头的 BOM；不支持 UTF-16。中文、emoji 或多行正文优先使用 `--body-file`。Windows PowerShell 5.1 的 `>` 默认写入 UTF-16，管道编码也可能改变正文，详见[Windows 使用说明](USER_GUIDE.md#windows-与-powershell)。两版输出均为 UTF-8；调用程序应按 UTF-8 解码。

## 快速开始

以下命令在仓库根目录执行。

**1. 不配置凭证，先看输出。**

```bash
node scripts/notify-send.js --platform feishu text "任务已完成" --dry-run
python3 scripts/notify-send --platform wecom text "任务已完成" --dry-run
```

**2. 创建自己的配置。** 各系统使用相同初始化命令；已有配置会报错并保留，跳过此步即可：

```bash
node scripts/notify-send.js --init-config
```

用编辑器打开配置，将 `REPLACE_ME_*` 替换为你自己的 webhook。示例展示两个平台各两个命名群；不需要的条目或平台可以删除。飞书启用签名校验时，在对应目标中添加 `"secret": "你的签名密钥"`。配置必须保存在源码目录外，不随安装包或 Git 提交分发。

```json
{
  "feishu": {
    "工作群": {"url": "https://open.feishu.cn/open-apis/bot/v2/hook/REPLACE_ME_FEISHU_WORK"}
  },
  "wecom": {
    "工作群": {"url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=REPLACE_ME_WECOM_WORK"}
  }
}
```

**3. 列出名称并预览。**

```bash
node scripts/notify-send.js --list-targets
node scripts/notify-send.js --platform feishu --target 工作群 text "任务已完成" --dry-run
node scripts/notify-send.js --target feishu:工作群 --target wecom:工作群 text "任务已完成" --dry-run
```

**4. 确认目标后真实发送。** 选择需要的一条命令；最后一条会向两个平台各发一条消息。

```bash
node scripts/notify-send.js --platform feishu --target 工作群 text "任务已完成"
python3 scripts/notify-send --platform wecom --target 工作群 text "任务已完成"
node scripts/notify-send.js --target feishu:工作群 --target wecom:工作群 text "任务已完成"
```

两版是可选的本地实现，HTTPS 是它们使用的传输协议。不要为了“备用”将同一条消息用 Node、Python、curl 各发送一遍；超时后的运行时切换可能造成重复通知。另提供[飞书与企微 curl 示例](examples/curl/README.md)，Python 仅准备配置/签名，curl 发起请求。示例一次发一条文本，返回原始响应；日常自动通知推荐完整 CLI。

## 输出与排错

单目标真实发送成功时，stdout 示例：

```json
{"results":[{"target":"工作群","platform":"feishu","status":"sent","exit_code":0}]}
```

`sent` 表示接口确认成功，不表示成员已读。多目标可能部分成功，应检查每个目标。退出码 `3` 表示结果未知，不自动重试；其他状态见 [CLI 参考](references/cli-reference.md#响应重试与退出码)。警告写入 stderr，便于程序单独解析 stdout。

## 文档

| 文档 | 面向谁 / 何时阅读 |
|---|---|
| [SKILL.md](SKILL.md) | Agent：执行原则、选择目标、常用调用 |
| [使用指南](USER_GUIDE.md) | 使用者：配置、多群发送、Node/Python/HTTPS、排错 |
| [CLI 参考](references/cli-reference.md) | 按需查阅：参数、格式限制、退出码、TLS 与重试 |
| [curl 示例](examples/curl/README.md) | 手工联调：直接 HTTPS 请求、签名和响应判断 |
| [贡献说明](CONTRIBUTING.md) | 开发者：离线测试、两版对齐、提交流程 |
| [变更记录](CHANGELOG.md) | 已发布版本与后续版本变更 |
| [安全说明](SECURITY.md) | 安全问题私密报告、凭证保护与泄露处理 |

## 测试

在根目录执行：

```bash
python3 tests/run_tests.py
```

统一入口隔离用户配置、阻止测试进程的真实网络连接，运行 Node/Python CLI 对齐、模拟传输和安装包测试。无需 webhook、平台账号或第三方测试库。GitHub Actions 使用同一测试入口，覆盖 Linux 的 Node 18 / Python 3.10、Node 22 / Python 3.12、Node 24 / Python 3.14，以及 macOS 的 Node 24 / Python 3.13。运行结果见上方 CI 徽章或 [Actions](https://github.com/kevinlove0712/notify-bot/actions/workflows/test.yml)。

## 安全问题

发现漏洞请通过 [Security → Report a vulnerability](https://github.com/kevinlove0712/notify-bot/security/advisories) 私密报告，不要在公开 Issue 中贴 webhook、密钥或未修复漏洞的利用细节。报告要求与凭证泄露处理见 [SECURITY.md](SECURITY.md)。普通功能问题仍可提交 Issue，附脱敏后的复现信息。

## 许可证

[MIT](LICENSE)，版权署名为 notify-bot contributors。
