# 直接通过 curl 请求群机器人

两份可运行的文本示例：[飞书](feishu-text.sh)、[企业微信](wecom-text.sh)。需要 Bash、curl 和 Python 3.10+。Python 只读取配置、校验输入、编码 JSON 及生成飞书签名，实际 HTTPS 请求由 curl 发出。准备过程复用现有 Python CLI 的函数，不调用它的网络发送函数。

它们用于理解接口与手工联调：每次只选择一个命名目标、发送一条文本，不提供完整 CLI 的多目标、附件、业务码分类或限流重试。日常自动通知仍优先使用 Node/Python CLI。

## 配置与运行

使用同一个 [分组配置](../config.example.json)，真实配置存放在仓库外。文件路径优先级为 `--config FILE` > `NOTIFY_CONFIG_FILE` > `~/.config/notify-bot/config.json`。飞书签名密钥放在对应目标的 `secret` 字段，无签名机器人则省略。

先准备一个 UTF-8 文本文件，例如 `/tmp/notify-message.txt`。以下命令在仓库根目录执行，**会真实发送**，只执行你需要的命令：

```bash
# 飞书：向 feishu 分组下的“工作群”发送一条文本
bash examples/curl/feishu-text.sh 工作群 /tmp/notify-message.txt

# 企业微信：向 wecom 分组下的“工作群”发送一条文本
bash examples/curl/wecom-text.sh 工作群 /tmp/notify-message.txt

# 自定义配置路径，正文也可使用 - 从 stdin 读取
bash examples/curl/feishu-text.sh 工作群 /tmp/notify-message.txt --config /path/to/bots.json
```

脚本不提供 `--dry-run`；不发送的预览使用主 CLI 的 `--dry-run`。配置或正文预检失败时不会启动 curl。地址、正文和飞书签名通过 stdin 的 curl 配置传入，避免进入 curl 的进程参数或 shell 历史；不要用 `bash -x`、`set -x` 或单独运行准备脚本打印含凭证的配置。

## 发出的请求

核心命令为 `curl -q --config -`：从 stdin 读取一份含 `url`、`request = "POST"`、`header = "Content-Type: application/json"` 和 `data-binary` 的配置。`-q` 必须放在首个选项，防止用户的 `.curlrc` 改变本次请求。显式限制 HTTPS，保持默认的证书校验，关闭 URL 展开，不跟随重定向、不重试。连接超时 10 秒、整次请求最长 15 秒。参数含义见 [curl 官方手册](https://curl.se/docs/manpage.html)。

飞书请求体：

```json
{"msg_type":"text","content":{"text":"任务已完成"}}
```

启用签名时还添加 `timestamp` 和 `sign`：以 `timestamp + "\n" + secret` 为 HMAC-SHA256 的 key，对空消息计算 HMAC，再做 Base64 编码。签名在每次执行时生成，勿缓存复用。企微请求体则为：

```json
{"msgtype":"text","text":{"content":"任务已完成"}}
```

企微自定义群机器人的凭证位于 webhook 的 `key` 参数，不使用飞书的签名字段。两个平台的字段不能互换。协议参考：[飞书](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)、[企业微信](https://developer.work.weixin.qq.com/document/path/99110)。

## 怎样判断结果

stdout 是平台原始响应，最后追加一行 `HTTP_STATUS=200` 这样的状态；不是主 CLI 的 `results` JSON。原始响应没有经过主 CLI 的脱敏，不要原样粘贴到公开日志或 Issues。

| 返回情况 | 含义与处理 |
|---|---|
| HTTP 2xx 且飞书 `code` 为整数 `0` | 平台确认成功 |
| HTTP 2xx 且企微 `errcode` 为整数 `0` | 平台确认成功 |
| 对应业务码为非零整数，包括 HTTP 400 中的业务错误 | 按平台错误处理；示例不自动重试 |
| HTTP 非 2xx 却声称业务成功、缺少正确业务码、响应不能解析 | 无法确认，不自动重发 |
| curl 超时（常见退出码 28）、断线 | 可能已经发送，不换运行时重发 |

**curl 退出码 0 只说明传输完成，不能当作发送成功。** 这两份示例没有启用 `--fail`，HTTP 400 的 JSON 会保留供排错。示例退出码采用 curl/本地准备过程的含义，不能套用主 CLI 的 0–4 分类。需要程序自动判定结果时使用主 CLI。

不要给这些示例加无条件重试、`--retry-all-errors` 或 `-k`。遇到 CA 问题配置可信证书；遇到结果未知先人工核实。正文仍受主 CLI 的文本长度与平台校验约束。
