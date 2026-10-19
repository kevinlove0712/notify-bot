# Security policy / 安全说明

## 报告安全问题

请通过仓库的 [Security → Report a vulnerability](https://github.com/kevinlove0712/notify-bot/security/advisories) 提交私密报告。不要把未修复漏洞的利用细节或真实 webhook、签名密钥、访问令牌贴到公开 Issue、PR 或讨论中。

建议报告包含：受影响的版本或提交、Node/Python/curl 与操作系统版本、预期和实际行为、影响范围，以及使用虚拟凭证的最小复现步骤。日志、截图、配置和请求体应先脱敏；不要发送真实群聊天记录或成员信息。

普通功能问题可以提交公开 Issue，但同样不要附带凭证。

## 支持范围

当前发布系列为 `0.1.x`。维护重点是最新发布版本和 `main`；旧版本用户请优先升级。安全修复不承诺回移到所有历史版本，也不承诺固定响应或修复时限。

## 凭证保护与泄露处理

- Webhook 地址本身就是发送凭证。真实配置应放在仓库外；macOS/Linux 上建议权限为 `600`。`.gitignore` 不能替代提交前检查。
- 不要将凭证写进发布附件、示例、日志或命令历史。curl 示例的原始平台响应未经主 CLI 脱敏，分享前也需检查。
- 保持 TLS 校验开启。遇到 CA 问题应配置可信证书，不要把 `--insecure` 当成长期设置。
- 若凭证已经泄露，请立即在对应平台停用或重建相关机器人 webhook，并轮换相关签名密钥，更新本地配置。仅删除公开文件或 Git 提交不能使旧凭证失效。
- 超时或连接中断可能发生在平台已收到消息之后；先核实发送结果，不要无条件重试或切换运行时重发。

## Reporting a vulnerability

Use [Security → Report a vulnerability](https://github.com/kevinlove0712/notify-bot/security/advisories) to contact the maintainers privately. Do not post unresolved exploit details, real webhooks, signing secrets, or access tokens in public issues, pull requests, or discussions.

Include the affected version/commit, runtime and OS versions, expected and actual behavior, potential impact, and minimal reproduction steps using dummy credentials. Redact logs, screenshots, configuration, and payloads. Do not include private group conversations or member information. Ordinary bug reports may use public issues after redaction.

The current release series is `0.1.x`. Maintenance focuses on the latest release and `main`; update older installations when possible. Backports to every historical version and fixed response or remediation times are not guaranteed.

Treat webhook URLs as credentials. Keep real configuration outside the repository and restrict permissions to `600` on macOS/Linux. Keep TLS verification enabled and inspect logs and raw curl responses before sharing them. If credentials are exposed, disable or recreate the affected webhook and rotate related signing secrets at the platform, then update local configuration. Removing a file or commit does not revoke leaked credentials. Verify unknown delivery outcomes before resending.
