# notify-bot 使用指南

这份文档面向使用者：配置哪些群、怎样指定目标、Node/Python 与 HTTPS 如何配合。AI 执行时使用精简的 [SKILL.md](SKILL.md)；格式限制、完整选项和退出码见 [CLI 参考](references/cli-reference.md)。

首次安装先看 [README](README.md#环境与安装)。使用 `node scripts/notify-send.js --init-config` 在固定全局位置创建模板（Python 可用 `python3 scripts/notify-send --init-config`，Windows 用 `python` 或 `py -3`），再填写自己的群地址。已有配置不覆盖；已有用户直接运行 `--doctor`。

多个 Agent 共用、Windows/Git Bash/WSL 的区别，以及权限与 TLS 排错，见[环境与共享安装](references/setup.md)。配置保存在 skill 目录外，更新 skill 时无需重新填写。

## 先配置收件群

默认读取 `~/.config/notify-bot/config.json`。文件位置优先级：`--config FILE` > `NOTIFY_CONFIG_FILE` > 默认路径。文件使用 JSON，不执行 shell 表达式或变量替换。

```json
{
  "feishu": {
    "工作群": {
      "url": "https://open.feishu.cn/open-apis/bot/v2/hook/REPLACE_ME"
    },
    "告警群": {
      "url": "https://open.feishu.cn/open-apis/bot/v2/hook/REPLACE_ME_TOO",
      "secret": "机器人启用签名校验时填写；否则删除此字段"
    }
  },
  "wecom": {
    "工作群": {
      "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=REPLACE_ME"
    }
  }
}
```

把占位地址替换为实际 webhook。每个平台下面都可以增加多个名称；同一个平台内不要重名，不同平台可以同名。名称支持中文和空格，不能含冒号或控制字符。飞书只有启用签名校验才填写 `secret`。修改地址而不改名称，调用命令就无需改变。

macOS/Linux 推荐将配置设为只有自己可读写：

```bash
chmod 600 ~/.config/notify-bot/config.json
```

脚本会在权限过宽时警告，但不会自动修改文件。配置中包含发送凭证，不要提交 Git 或公开分享。脚本不自行读取 `.zshenv`；只有显式 `--init-config` 才创建新模板，发送和诊断不创建、迁移或覆盖配置。已有的旧 `targets` 平铺文件需要先迁移，规则见 [配置参考](references/cli-reference.md)。

## 按平台和名称选择

- 单独发送：`--platform feishu --target 工作群`。
- 同平台多个群：`--platform feishu --target 工作群 --target 告警群`。
- 跨平台多个群：`--target feishu:工作群 --target wecom:工作群`。
- 查看所有名称：`--list-targets`；只看飞书：`--platform feishu --list-targets`。

只写 `--target 名称` 时，这个名称必须跨平台唯一；名称重名会报错。仅写 `--platform` 不会自动给该平台所有群发送，而是保留旧的环境变量用法。多目标发送目前只支持 `text` 和 `md`，没有 `--platform all`。

跨平台发送不能带 `--at`，因为飞书和企微的用户 ID 不通用；需要提醒指定成员时分平台发送。两平台的 Markdown 也不保证同样显示，复杂排版应分别准备。

## Windows 与 PowerShell

Node/Python 主 CLI 可在原生 Windows 运行，不需要 Bash。首次创建配置的 PowerShell 命令见 [README](README.md#windows--powershell)。默认路径为 `%USERPROFILE%\.config\notify-bot\config.json`；`--config` 和 `NOTIFY_CONFIG_FILE` 的优先级与其他系统相同。Windows 使用文件 ACL；请在文件安全属性中确认真实配置没有向其他用户开放，脚本不检查或自动修改 Windows ACL。

使用 `node .\scripts\notify-send.js` 或 `python .\scripts\notify-send`，也可用 `py -3 .\scripts\notify-send`（确认 Python 至少 3.10）。无需改文件扩展名，也不需要为主 CLI 新增 `.bat` 或 `.ps1`。路径包含空格时加引号。

推荐 PowerShell 7。下面使用显式 UTF-8 编码写入临时正文，兼容 PowerShell 5.1/7，且只做离线预览：

```powershell
$notifyBody = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName())
try {
    [IO.File]::WriteAllText($notifyBody, "第一行`r`n第二行 🙂", [Text.UTF8Encoding]::new($false))
    node .\scripts\notify-send.js --platform wecom text --body-file $notifyBody --dry-run
    # 或选择 Python：python .\scripts\notify-send --platform wecom text --body-file $notifyBody --dry-run
} finally {
    Remove-Item -LiteralPath $notifyBody
}
```

配置、正文、卡片等 JSON 文件均使用 UTF-8，可带一个开头的 BOM；正文内部字符及 CRLF/LF 换行原样保留。UTF-16 文件不支持。Windows PowerShell 5.1 的 `>` 默认生成 UTF-16，不要用它生成输入文件；若把含中文的 PowerShell 示例保存成 `.ps1` 后在 5.1 中执行，脚本文件本身应保存为 UTF-8 with BOM。

两版 CLI 的 stdout/stderr 均输出 UTF-8。AI、Python 或其他程序捕获输出时应显式按 UTF-8 解码。`--body-file -` 同样要求管道送入 UTF-8 字节；设置 Python UTF-8 模式不能修复上游 PowerShell 已破坏的文本，因此日常优先传文件。PowerShell 环境变量写法为 `$env:NOTIFY_CONFIG_FILE = 'C:\path\bots.json'`；进程退出码通过 `$LASTEXITCODE` 获取。

curl `.sh` 示例仍属于 Bash 使用方式，仅在 macOS/Linux 验证；不将 Git Bash 或 WSL 的成功视为原生 Windows 验证。

## Node、Python 与 HTTP 的使用逻辑

Node.js 和 Python 是两种可选的本地运行方式；HTTP 是通信协议，脚本使用其加密形式 HTTPS 调用机器人接口，不代表需要另起 HTTP 服务。另提供 curl 直接请求示例，方便手工验证接口。

1. **发送前选运行时**：优先 Node.js 18+；未安装或版本不足时使用 Python 3.10+。两版独立、零第三方依赖，读取同一配置，接受同样的命令选项。可先用 `node --version` / `python3 --version` 检查。
2. **只执行所选的一版**：Node 运行 `scripts/notify-send.js`，Python 运行无 `.py` 扩展名的 `scripts/notify-send`。选择由调用者/agent 完成，脚本不会自动调用另一版；无需两个版本都运行。两者都不可用时提示安装，不自行安装或改用 curl 绕过脚本。
3. **解析并预检**：读取平台分组配置，按平台与名称找地址，构造消息，校验全部目标及正文。`--list-targets` 仅列名称/平台；`--dry-run` 仅预览，两者都不联网。
4. **通过 HTTPS 发送**：Node 使用内置 `https.request`；Python 使用标准库 `urllib.request` 和 `ssl`。普通消息向选中的 webhook 执行 `POST`，请求体为 JSON，`Content-Type: application/json`；仅允许受支持的 HTTPS 域名和接口，拒绝明文 `http://` 与重定向。
5. **按平台返回值判断结果**：飞书需要业务字段 `code: 0`，企微需要 `errcode: 0`。HTTP 200 本身不代表消息发送成功。输出逐目标结果与退出码；限流仅按 `--retry` 规则处理。

**不能把运行时切换当成重试**：Node 已发起请求后遇到超时、断线或异常响应，不得再换 Python/curl 重发。Python 同理。应遵循结果分类，防止重复通知。只有确定尚未发起发送的运行时不可用问题，才在发送前换另一版。

```bash
# 两种等价调用，选择其中一条执行，不要先后都执行
node "<skill目录>/scripts/notify-send.js" --platform feishu --target 工作群 text "部署完成"
python3 "<skill目录>/scripts/notify-send" --platform feishu --target 工作群 text "部署完成"
```

企微 `file`/`voice` 分两步：先向 `webhook/upload_media` 用 `multipart/form-data` 上传文件，取得 `media_id` 后，再向该目标的 webhook 用 JSON 发送消息。消息重试复用已上传的 `media_id`。企微图片以 base64 和 MD5 放入 JSON；飞书图片使用已有 `image_key`。飞书签名由选中目标的 `secret` 生成。

单次消息请求设置 15 秒超时，上传请求设置 60 秒超时；Node 使用整次请求计时，Python 使用底层连接/读写超时，因此不是两版统一的总耗时上限。多目标与限流等待会增加命令总耗时。

## curl 直接请求示例

需要 Bash、curl 和 Python 3.10+，使用相同的命名配置。Python 只准备请求，实际 HTTPS 调用由 curl 完成。完整步骤见 [curl 使用说明](examples/curl/README.md)。在仓库根目录选择需要的一条命令执行，下面会真实发送：

```bash
bash examples/curl/feishu-text.sh 工作群 /tmp/message.txt
bash examples/curl/wecom-text.sh 工作群 /tmp/message.txt
```

每次一个目标、一条文本，无自动重试。stdout 为平台原始响应及 HTTP 状态，curl 退出码 0 不代表业务成功，也不使用主 CLI 的 0–4 分类。不要把 curl 当作超时后的备用重发通道。

## 常用命令

下面的 `SEND` 指 Node 脚本，也可替换为 Python 版本。

```bash
SEND="<skill目录>/scripts/notify-send.js"

node "$SEND" --list-targets
node "$SEND" --platform feishu --list-targets
node "$SEND" --platform feishu --target 工作群 text "发布完成 ✅"
node "$SEND" --target feishu:工作群 --target wecom:工作群 md --title "构建报告" --body-file /tmp/report.md --retry 2
node "$SEND" --config /path/to/bots.json --platform feishu --target 告警群 text --dry-run "预览"

node "$SEND" --platform feishu --target 工作群 text --at-all "全员周会"
node "$SEND" --platform feishu --target 工作群 text --at ou_xxx "请查看通知"
node "$SEND" --platform wecom --target 工作群 text --at example_user --at-mobile "<成员手机号>" "请处理"
node "$SEND" --platform feishu --target 工作群 md --title "构建报告" --color green "状态：**成功**"
node "$SEND" --platform wecom --target 工作群 image /tmp/chart.png
node "$SEND" --platform feishu --target 工作群 image img_example
node "$SEND" --platform wecom --target 工作群 file /tmp/report.pdf
node "$SEND" --platform wecom --target 工作群 voice /tmp/alert.amr
node "$SEND" --platform wecom --target 工作群 news '{"articles":[{"title":"周报","url":"https://example.com"}]}'
node "$SEND" --platform feishu --target 工作群 card card.json
node "$SEND" --platform feishu --target 工作群 post post.json
node "$SEND" --platform wecom --target 工作群 raw payload.json

node "$SEND" --platform wecom text --dry-run --body-file /tmp/message.txt
node "$SEND" --platform wecom --target 工作群 text -- "--status ok"
```

示例中的用户 ID、手机号和图片 key 均为占位值，使用前替换为对应平台的实际值。

长正文或包含引号、反引号、`$()` 的正文优先写入文件，再用 `--body-file FILE`；`--body-file -` 读取 stdin，保留换行，不能与位置正文并用。JSON 类命令支持内联对象、文件、`-`（stdin）。`--` 之后不再解析选项。

`--dry-run --platform ...` 可在没有 webhook 的情况下预览。命名目标预览仍检查配置；预览不上传、不联网、不输出自动生成的签名。文件/语音预览返回待上传标记；`raw`/`card`/`post` 仅做基础结构校验，不保证服务端接受。

## 看结果和排查问题

真实发送会返回每个目标的 JSON 结果。`status: sent` 表示平台接口确认成功，不代表成员已阅读。先看哪些目标成功，再处理失败目标；不要因为总退出码非零就重发全部目标。

常见情况：

- **配置文件不存在**：按报错里的路径创建配置，或用 `--config FILE` 指向已有文件。
- **权限警告**：检查文件后按需设为 `600`，不会影响名单或凭证内容。
- **跨平台 `--at` 被拒绝**：拆成飞书、企微两次调用，各用正确的用户 ID。
- **业务错误**：报错保留脱敏后的平台提示，例如关键词、签名、消息格式问题。HTTP 400 也可能包含明确错误；脚本会按业务码分类。
- **结果未知（退出码 3）**：不要自动重发或换另一种运行方式重发；无法确定上一条是否已送达。
- **限流**：可用 `--retry 2` 允许额外尝试两次；只有已识别的限流码会重试，次数耗尽停止。

完整退出码、TLS/CA 设置、退避时间、各平台格式差异和上传限制见 [CLI 参考](references/cli-reference.md)。

## 让其他 agent 使用

同一台机器共用这个 skill 和默认配置时，不用再配置地址；让已加载旧说明的 agent 重新读取 `SKILL.md`。另一台机器需要同步完整 skill 目录和那台机器自己的配置。配置文件独立于 skill，更新文档和脚本不会替换地址。
