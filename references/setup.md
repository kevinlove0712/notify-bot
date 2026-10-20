# 首次配置、环境诊断与共享安装

## 固定全局配置

默认配置与 skill 安装目录分离，同一操作系统用户的所有 Agent 共用：

| 运行时 | 默认位置 |
|---|---|
| macOS / Linux | `~/.config/notify-bot/config.json` |
| Windows 原生 Node/Python | `%USERPROFILE%\.config\notify-bot\config.json` |
| WSL Linux Node/Python | Linux 用户的 `~/.config/notify-bot/config.json`；共享 Windows 文件见下文 |

准确路径由运行时 home 决定，用 `--doctor` 查看。优先级始终为 `--config FILE` > `NOTIFY_CONFIG_FILE` > 默认路径；相对 `--config` 路径按当前工作目录解析。CLI 不解释参数里的 `~` 或变量表达式，需由 shell 展开或使用绝对路径。

在完整源码/skill 目录执行，选择一种运行时：

```bash
node scripts/notify-send.js --init-config
# Python 替代：python3 scripts/notify-send --init-config
```

Windows 可用 `python` 或 `py -3`。初始化仅生成含 `REPLACE_ME_*` 的 UTF-8 模板，不联网、不发送，不读取其他 Agent 的凭证。已有文件、目录或断开的符号链接都拒绝覆盖。POSIX 新文件模式为 `600`；Windows 采用目录继承的 ACL。发生写盘错误时检查所报路径；CLI 不自动删除可能部分写入的文件。

用编辑器填写目标 webhook，删除不用的占位目标。飞书启用签名时增加对应目标的 `secret`，无需把凭证粘贴到聊天中。然后运行：

```bash
node scripts/notify-send.js --doctor
node scripts/notify-send.js --list-targets
node scripts/notify-send.js --target feishu:工作群 text "离线预览 ✅" --dry-run
```

已有配置的用户直接运行 `--doctor`。诊断会检查所有目标的本地格式；占位地址或空配置返回 `incomplete`。列表和预览可查看模板，真实命名目标发送拒绝占位地址。诊断不验证 webhook 是否有效、平台权限、网络或群内渲染。

## 一份 skill，多个 Agent 共用

本地安装辅助工具需要 Node.js 18+；它不下载任何内容。从当前完整源码目录运行：

```bash
node scripts/install-shared.js --claude
```

默认将源码复制到 `~/.agents/skills/notify-bot`，供支持此目录的 Codex/pi 使用；`--claude` 在 `~/.claude/skills/notify-bot` 创建同源目录链接。Windows 使用目录 junction，macOS/Linux 使用符号链接。其他 Agent 是否支持该目录应查看其实际版本；本工具不自动修改它们的设置。重新加载或重启 Agent 后使用。

该命令不创建机器人配置，也不复制凭证。所有目标先检查冲突；不同内容的既有目录、文件、断开的链接都拒绝覆盖。不提供强制覆盖开关。对已指向同一源的链接可重复执行。磁盘或权限错误可能留下部分安装，检查输出后处理，不盲目重跑。

可用 `--source DIR` 指定完整源码目录，`--home DIR` 指定要安装的用户目录；普通使用无需指定。更新时先备份现有 skill，再替换主目录中的代码和文档，保留目录链接及目录外的全局配置。

## WSL 与 Windows 共用

WSL 是独立的 Linux 用户环境，不会自动使用 Windows home。用户选择共用后，在目标 WSL 用户下运行：

```bash
node /mnt/c/Users/WINDOWS_USER/.agents/skills/notify-bot/scripts/install-shared.js \
  --link-source /mnt/c/Users/WINDOWS_USER/.agents/skills/notify-bot \
  --shared-config /mnt/c/Users/WINDOWS_USER/.config/notify-bot/config.json \
  --claude
```

把 `WINDOWS_USER` 换成已经确认的 Windows 用户目录名。命令显式创建两个 skill 入口和一个配置文件链接，保持单一物理副本；源必须存在且可访问，不搜索其他用户，不覆盖现有 Linux 配置。已有独立配置时先决定保留哪份，可暂用 `--config` 指定 Windows 文件；不要自动合并或复制凭证。

`--shared-config FILE` 也可用于其他 POSIX 环境的显式文件共享。Windows 文件符号链接可能需要开发者模式或对应权限；工具会报告失败，不修改系统策略。WSL 挂载的 NTFS 文件可能表现为宽松 POSIX 模式，警告不等于 Windows ACL 已向其他用户开放；检查宿主文件的安全属性，不对共享文件盲目执行 chmod。

## 区分 shell 与运行时

在 Agent **自己的执行工具**里运行 `--doctor`，不要拿另一个终端的结果代替。报告包含运行时版本、可执行文件、home、配置来源及状态，仅输出目标名称/平台；不枚举完整环境或读取 Agent token。

| 现象 | 判断与做法 |
|---|---|
| PowerShell，运行时 `win32` | Windows 路径，显式使用 node/python/py 启动脚本 |
| Git Bash 有 `MSYSTEM`，运行时 `win32` | shell 是 Bash，运行时仍是 Windows；诊断里的 home 和配置路径为准 |
| `wsl_kernel: true`，运行时 `linux` | Linux 运行时，使用 Linux 路径或已建立的共享链接 |
| 从 WSL 启动 node.exe/python.exe，报告 `win32` | 使用 Windows 配置和 Windows 路径；必要时显式转换路径 |

`wsl_environment`、`msystem` 是继承的环境线索，不证明完整进程链；Windows exe 从 WSL 启动时也可能没有这些标记。需要进一步确认时，Bash 执行 `uname -sr`、`command -v node python python3`，仅读取 `WSL_DISTRO_NAME`/`MSYSTEM`。PowerShell 可用 `Get-Command node,python,py,curl.exe` 查看命令解析。

## 文件权限与 curl/TLS

- `missing`：核对诊断路径，首次使用再初始化。`permission_denied`：核对 ACL/目录访问与 Agent 沙箱授权，不因读不到文件而新建另一份配置。
- `invalid_json`：使用 UTF-8、修正 JSON 语法；不打印原始配置。`invalid_config`：修正分组、目标及 URL 格式。
- Windows 可能已有 `curl.exe`。用 `curl.exe --version` 确认可执行文件和 TLS 后端；PowerShell 的 `curl` 可能解析成其他命令。
- `.sh` 示例需要 Bash，不能直接粘贴到 PowerShell。主 CLI 不需要 curl 或 Bash；直接请求的细节见 [curl 说明](../examples/curl/README.md)。
- Schannel 的 `SEC_E_NO_CREDENTIALS` 与终端身份/安全上下文有关，不能据此判定平台不可用。对公开域名的 TLS 探测与真实 webhook POST 分开；HTTP 404 也说明该次 HTTPS 请求收到响应，但不能证明 webhook 发送成功。
- 若同一命令仅在受限 Agent 终端失败，核对其权限和宿主终端表现，不关闭 TLS 校验、不改系统执行策略、不自动下载安装替代工具。Node/Python 与 curl 的证书/TLS 后端可能不同；已发出的请求结果未知时，不切换方式重发。
