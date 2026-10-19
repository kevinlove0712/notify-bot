# notify-bot

让 Agent 或命令行通过飞书、企业微信群机器人发送通知。按平台管理多个命名群，一次调用可向多个目标发送文本或 Markdown。

Node.js / Python 双实现，无需安装第三方运行依赖。两版通过 HTTPS 发送，接受相同的 CLI 参数，共用独立配置文件。

## 能做什么

- 通过 `--platform feishu --target 工作群` 精确选择一个群；跨平台使用多个 `--target 平台:名称`。
- 文本、Markdown，以及各平台支持的图片、文件、语音、图文、卡片和富文本；详见[平台差异](references/cli-reference.md#平台能力与限制)。
- 默认校验证书；仅对明确的限流响应执行显式启用的重试，结果未知时不自动重发。
- 返回逐目标 JSON 结果和分类退出码，支持不联网的 `--dry-run` 与 `--list-targets`。

本项目使用自定义群机器人 webhook，不能读取群消息、撤回消息，也不提供飞书应用机器人的文件上传能力。多目标调用仅支持 `text` / `md`；没有隐式群发或 `--platform all`。

## 环境与安装

运行时任选其一：Node.js 18+，或 Python 3.10+。建议使用仍受维护的运行时版本。完整测试需要同时安装 Node 和 Python。主要使用与验证环境为 macOS/Linux；Windows 尚未验证。

克隆仓库，或下载源码并解压为 `notify-bot` 目录。无需 `npm install` 或 `pip install`：

```bash
git clone https://github.com/kevinlove0712/notify-bot.git
cd notify-bot
```

在仓库根目录选择一个运行时：

```bash
# 两种运行方式，任选一种
node scripts/notify-send.js --help
python3 scripts/notify-send --help
```

作为 Agent Skill 使用时，将完整目录放入你的 Agent 支持的 skills 目录，保留 `SKILL.md`、`scripts/` 和文档的相对位置。安装位置由所用 Agent 决定。已有同名 skill 时先备份，避免覆盖本地修改；可先用命令行独立试用。

## 快速开始

以下命令在仓库根目录执行。

**1. 不配置凭证，先看输出。**

```bash
node scripts/notify-send.js --platform feishu text "任务已完成" --dry-run
python3 scripts/notify-send --platform wecom text "任务已完成" --dry-run
```

**2. 创建自己的配置。** 以下 macOS/Linux 命令不会覆盖已有配置：

```bash
mkdir -p "$HOME/.config/notify-bot"
if [ ! -e "$HOME/.config/notify-bot/config.json" ]; then
  (umask 077; cp examples/config.example.json "$HOME/.config/notify-bot/config.json")
fi
chmod 600 "$HOME/.config/notify-bot/config.json"
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
| [变更记录](CHANGELOG.md) | 待发布内容与后续版本变更 |

## 测试

在根目录执行：

```bash
python3 tests/run_tests.py
```

统一入口隔离用户配置、阻止测试进程的真实网络连接，运行 Node/Python CLI 对齐、模拟传输和安装包测试。无需 webhook、平台账号或第三方测试库。GitHub Actions 工作流覆盖 macOS/Linux 的不同运行时组合；工作流在首次上传并运行后才能验证云端结果。

## 许可证

[MIT](LICENSE)，版权署名为 notify-bot contributors。
