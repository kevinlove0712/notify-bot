# notify-bot

English | [简体中文](README.md)

[![Offline tests](https://github.com/kevinlove0712/notify-bot/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/kevinlove0712/notify-bot/actions/workflows/test.yml)
[![Install with skills.sh](https://img.shields.io/badge/skills.sh-install-blue)](https://skills.sh/kevinlove0712/notify-bot/notify-bot)

Send notifications to Feishu and WeCom group bots from an agent or the command line. Organize multiple named webhooks by platform and send text or Markdown to selected targets in one invocation.

Independent Node.js and Python clients share the same CLI and configuration format. Neither client requires third-party runtime packages.

## Features

- Select a single named target or multiple targets across platforms.
- Send text, Markdown, and platform-specific images, attachments, cards, or rich text; see the [platform reference (Chinese)](references/cli-reference.md#平台能力与限制).
- Verify TLS certificates by default. Retry only explicit rate-limit responses when requested; never automatically resend an unknown outcome.
- Preview payloads offline with `--dry-run` and list target names without exposing credentials.
- Return per-target JSON results and classified exit codes.

## Requirements and installation

Use Node.js 18+ **or** Python 3.10+; prefer a currently maintained runtime. The full test suite needs both. Tested on macOS and Linux; Windows is not yet verified.

```bash
git clone --branch v0.1.0 --depth 1 https://github.com/kevinlove0712/notify-bot.git
cd notify-bot
node scripts/notify-send.js --help
# Python alternative:
python3 scripts/notify-send --help
```

No `npm install` or `pip install` is needed. You can also download versioned source archives from [Releases](https://github.com/kevinlove0712/notify-bot/releases). Omit `--branch v0.1.0 --depth 1` to clone the development branch.

### Install as an agent skill with the skills CLI

View [notify-bot on skills.sh](https://skills.sh/kevinlove0712/notify-bot/notify-bot), or install it with the command below.

Run this from the project where you want to use the skill, then choose your agent when prompted:

```bash
npx skills add kevinlove0712/notify-bot --skill notify-bot
```

The [skills CLI](https://github.com/vercel-labs/skills#install-a-skill) currently requires Node.js 22.20+. This requirement applies to the installer; notify-bot itself still supports Node.js 18+ or Python 3.10+. Installation is project-local by default; add `-g` for a global installation. This command installs the current contents of the repository's default branch. Use the versioned clone above to pin `v0.1.0`. Back up an existing skill before replacing it.

For manual installation, place the complete directory in your agent's supported skills directory. Preserve the relative locations of `SKILL.md`, `scripts/`, and the documentation. The agent instructions and detailed reference are currently in Chinese.

## Quick start

Run the following commands from the repository root.

**1. Preview without credentials or network access.** Choose either runtime:

```bash
node scripts/notify-send.js --platform feishu text "Task complete" --dry-run
python3 scripts/notify-send --platform wecom text "Task complete" --dry-run
```

**2. Create a private configuration.** These macOS/Linux commands preserve an existing configuration:

```bash
mkdir -p "$HOME/.config/notify-bot"
if [ ! -e "$HOME/.config/notify-bot/config.json" ]; then
  (umask 077; cp examples/config.example.json "$HOME/.config/notify-bot/config.json")
fi
chmod 600 "$HOME/.config/notify-bot/config.json"
```

Open that file in your editor and replace `REPLACE_ME_*` with your own webhooks. The structure is **platform → target name → `url` / optional `secret`**. Remove unused targets or platforms. If a Feishu bot requires signing, add its signing key as `secret` on that target. Keep real configuration outside this repository.

The example uses the names `工作群` (work group) and `告警群` (alerts). You may rename them; commands must use the exact configured name. The commands below use the unchanged example names. Use `--config FILE` or `NOTIFY_CONFIG_FILE` to select a different configuration file; the CLI option takes precedence.

**3. Inspect targets and preview a message.**

```bash
node scripts/notify-send.js --list-targets
node scripts/notify-send.js --platform feishu --target 工作群 text "Task complete" --dry-run
node scripts/notify-send.js --target feishu:工作群 --target wecom:工作群 text "Task complete" --dry-run
```

**4. Send after checking the selected targets.** These commands send real messages; run only the one you need. The last command sends to both platforms.

```bash
node scripts/notify-send.js --platform feishu --target 工作群 text "Task complete"
python3 scripts/notify-send --platform wecom --target 工作群 text "Task complete"
node scripts/notify-send.js --target feishu:工作群 --target wecom:工作群 text "Task complete"
```

## Results and limits

Successful single-target output:

```json
{"results":[{"target":"工作群","platform":"feishu","status":"sent","exit_code":0}]}
```

`sent` means the platform accepted the message, not that someone read it. Multiple targets may have different outcomes; inspect every result before deciding what to do next. Warnings go to stderr.

| Exit code | Meaning |
|---|---|
| 0 | Success, including a successful preview or listing |
| 1 | Explicit platform rejection or TLS verification failure |
| 2 | Local arguments, configuration, or preflight error |
| 3 | Unknown delivery outcome; do not automatically resend |
| 4 | Rate limited with no retries remaining |

- Only `text` and `md` support multiple targets. There is no implicit broadcast or `--platform all`.
- Markdown becomes an interactive card on Feishu and a native Markdown message on WeCom. Formatting support differs; the clients do not translate Markdown dialects.
- Cross-platform `--at` is rejected because user IDs are platform-specific. Send mentions separately for each platform.
- These are custom webhook bots: they cannot read group messages or recall sent messages. Feishu images require an existing `image_key`; local file and voice uploads are supported only for WeCom.
- Node and Python are alternative clients using HTTPS. Do not resend through another runtime after a timeout. The [curl examples](examples/curl/README.md) use Python for configuration/signing and curl for the actual request; they send one text message and return raw responses rather than the full CLI's result format.

## Tests and documentation

```bash
python3 tests/run_tests.py
```

The suite isolates local configuration and blocks real network connections. It needs no webhook credentials or third-party test packages. GitHub Actions runs the same suite across four macOS/Linux runtime combinations.

- [User guide (Chinese)](USER_GUIDE.md): configuration, multiple targets, runtimes, and troubleshooting.
- [CLI reference (Chinese)](references/cli-reference.md): options, platform limits, TLS, retries, and results.
- [Contributing (Chinese)](CONTRIBUTING.md) and [Changelog](CHANGELOG.md).
- [Security policy](SECURITY.md): report vulnerabilities privately through [Security → Report a vulnerability](https://github.com/kevinlove0712/notify-bot/security/advisories). Do not disclose credentials or unresolved exploit details in public issues.

## License

[MIT](LICENSE), copyright notify-bot contributors.
