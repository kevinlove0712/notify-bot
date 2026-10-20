# Changelog

## Unreleased

- 新增 Node/Python 对齐的 `--init-config` 与离线 `--doctor`：固定全局路径、拒绝覆盖、运行时与配置来源诊断、分类错误、凭证隐藏及占位地址发送保护。
- 新增 `scripts/install-shared.js`：一份源码安装到 `.agents/skills`，可选 Claude 入口和显式 WSL 共享配置链接，安装前检查冲突。
- 补充首次使用、多 Agent 共用、PowerShell/Git Bash/WSL、curl/TLS 排错说明及离线回归。
- 支持原生 Windows 的 Node/Python CLI，新增两组 Windows CI；curl 示例继续仅在 macOS/Linux Bash 环境验证。
- 接受带 BOM 的 UTF-8 配置与输入文件，正文保留原始换行，Python 标准输出/错误与 stdin 统一使用 UTF-8。
- 增加编码与中文路径回归测试，以及中英文 PowerShell 安装、配置与调用说明。

## [v0.1.0](https://github.com/kevinlove0712/notify-bot/releases/tag/v0.1.0) — 2026-10-19

首个公开版本 / First public release.

- Node.js / Python 独立实现，零必需第三方运行依赖。
- 飞书与企业微信按平台分组的多目标配置及命名路由。
- 文本 / Markdown 多目标预检和逐目标结果。
- 严格 TLS、限流重试、结果未知保护和错误提示脱敏。
- 分离 Agent 指令、使用指南、CLI 参考和开发说明。
- 增加占位配置、隔离安装测试、离线测试入口与 CI 工作流。
- 增加飞书 / 企微 curl 文本示例与离线回归；复用命名配置和签名校验，清晰区分 curl 与主 CLI 的结果语义。
- 补充简短英文 README、安全报告政策、私密漏洞报告入口和按版本安装说明。
