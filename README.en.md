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

Use Node.js 18+ **or** Python 3.10+; prefer a currently maintained runtime. The Node/Python CLI supports macOS, Linux, and Windows, with CI coverage for all three. The full test suite needs both runtimes. The Bash curl examples are tested only on macOS/Linux.

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/kevinlove0712/notify-bot.git
cd notify-bot
node scripts/notify-send.js --help
# Python alternative:
python3 scripts/notify-send --help
```

No `npm install` or `pip install` is needed. You can also download the [v0.2.0 source archive](https://github.com/kevinlove0712/notify-bot/archive/refs/tags/v0.2.0.zip). Omit `--branch v0.2.0 --depth 1` to clone the development branch.

### Install as an agent skill with the skills CLI

View [notify-bot on skills.sh](https://skills.sh/kevinlove0712/notify-bot/notify-bot), or install it with the command below.

Run this from the project where you want to use the skill, then choose your agent when prompted:

```bash
npx skills add kevinlove0712/notify-bot --skill notify-bot
```

The [skills CLI](https://github.com/vercel-labs/skills#install-a-skill) currently requires Node.js 22.20+. This requirement applies to the installer; notify-bot itself still supports Node.js 18+ or Python 3.10+. Installation is project-local by default; add `-g` for a global installation. This command installs the current contents of the repository's default branch. Use the versioned clone above to pin `v0.2.0`. Back up an existing skill before replacing it.

For manual installation, place the complete directory in your agent's supported skills directory. Preserve the relative locations of `SKILL.md`, `scripts/`, and the documentation. The agent instructions and detailed reference are currently in Chinese.

### Updating

For installations managed by the skills CLI, choose the matching scope to update only notify-bot:

```bash
npx skills update notify-bot --global
# Project installation: run from the original project directory
npx skills update notify-bot --project
```

Back up local edits inside the skill first; updates may replace them. Keep webhook configuration outside the skill directory and do not reinitialize it. Default-branch installations follow that branch, rather than a pinned Release; use the versioned clone above to pin a version. On PowerShell, use `npx.cmd` if `npx.ps1` is blocked.

Manual copies and `install-shared.js` installs lack skills CLI tracking. To migrate, back up and move the old skill outside all skills directories, remove only its agent links, and run `npx skills add kevinlove0712/notify-bot --skill notify-bot --global`, selecting your agents. For `--link-source` installs, remove the installation links and keep the source checkout. Omit `--global` for project installations. Run `node scripts/notify-send.js --doctor` from the installed directory afterward and reload the skill in your agent. See [migration details (Chinese)](references/setup.md#升级与迁移).

### Shared global installation and first use

Install this local bundle once for multiple agents:

```bash
node scripts/install-shared.js --claude
```

Copy installs use an explicit release-file list, excluding extra local files such as `.env`, private configurations, and IDE metadata. Listed files and their subdirectories must not be symlinks. Keep the release files and example configuration free of real credentials. Explicit `--link-source` installs share the entire source directory without filtering.

The primary copy lives at `~/.agents/skills/notify-bot`; the optional Claude entry links to it. Existing conflicting destinations are refused. Run `node scripts/notify-send.js --init-config` separately to create a UTF-8 template at `~/.config/notify-bot/config.json` (under the Windows user profile for native runtimes). Existing files and symlinks are never overwritten. Replace placeholder webhooks in your editor and remove unused targets, then run `node scripts/notify-send.js --doctor`. The Python CLI accepts the same options.

Doctor reports the actual runtime, executable, home, selected configuration path/source, and target names without network requests or webhook/secrets. Status `ok` exits 0; missing/unreadable/invalid/incomplete configuration exits 2. It does not validate remote credentials. A real named-target send refuses `REPLACE_ME` addresses. These management modes accept only an optional `--config FILE`; precedence remains argument > `NOTIFY_CONFIG_FILE` > default.

Git Bash can run Windows executables, and WSL can launch Windows `.exe` files: use the reported runtime rather than guessing from the shell name. To share Windows files from WSL, run the installer in WSL with explicit `--link-source /mnt/c/.../notify-bot --shared-config /mnt/c/.../config.json --claude`; it creates links instead of duplicating credentials. See [setup details (Chinese)](references/setup.md). These features are available starting with `v0.2.0`.

### Windows / PowerShell

Windows Node/Python support is available starting with `v0.2.0`. Use the versioned clone command or the skills CLI above. If PowerShell blocks `npx.ps1`, run `npx.cmd skills add kevinlove0712/notify-bot --skill notify-bot`; no execution-policy change is needed.

PowerShell 7 is recommended. Run these commands from the repository root; an existing configuration is preserved:

```powershell
node .\scripts\notify-send.js --init-config
node .\scripts\notify-send.js --list-targets
node .\scripts\notify-send.js --platform wecom text 'Preview' --dry-run
# Python alternative; choose one runtime
python .\scripts\notify-send --platform wecom text 'Preview' --dry-run
```

If your Python installation provides the `py` launcher, use `py -3` instead of `python` and check that it selects Python 3.10+. The default configuration is `%USERPROFILE%\.config\notify-bot\config.json`. Windows uses file ACLs rather than `chmod`; keep credentials private and outside the repository.

Configuration, body, and JSON files must be UTF-8; a leading BOM is accepted. UTF-16 is not supported. Both clients preserve body line endings and emit UTF-8 output, which callers must decode as UTF-8. Prefer `--body-file` for Unicode or multiline text. In Windows PowerShell 5.1, `>` writes UTF-16 and pipelines may alter Unicode text; save files with an explicit UTF-8 encoding instead. The bundled `.sh` curl examples require Bash and are not native PowerShell scripts.

## Quick start

Run the following commands from the repository root.

**1. Preview without credentials or network access.** Choose either runtime:

```bash
node scripts/notify-send.js --platform feishu text "Task complete" --dry-run
python3 scripts/notify-send --platform wecom text "Task complete" --dry-run
```

**2. Create a private configuration.** The same command works across platforms. An existing file is preserved and returns an error; existing users can skip initialization:

```bash
node scripts/notify-send.js --init-config
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
