# 贡献说明

Node 和 Python 实现保持相同的参数、消息结构与退出码语义。修改发送行为时同时更新两版，并给实际故障或新行为补充回归测试；不要只断言实现细节。

## 本地验证

需要 Node.js 18+ 和 Python 3.10+，没有第三方测试依赖。在仓库根目录运行：

```bash
python3 tests/run_tests.py
```

测试入口使用临时 HOME，清除继承的机器人配置变量，对 Python socket 与 Node Socket 连接加上禁止真实联网的保护。传输测试仍通过 mock 覆盖成功、限流、业务错误、证书错误、超时与部分成功；它们不能证明平台实际可用或群内渲染正确。

测试保护依赖 Python 加载 `PYTHONPATH` 中的 `sitecustomize`。Windows 的嵌入式/隔离 Python 可能通过 `._pth` 忽略它；使用正常 Python 运行完整测试，或仅在临时测试运行时副本中显式加载 `tests/offline` 和 `site`，不要为测试修改用户的 Python 安装。网络保护测试必须通过，不得跳过后宣称完整离线验证通过。

Windows 使用 `python tests/run_tests.py`（或 `py -3 tests/run_tests.py`），无需 Bash。CI 包含两组原生 Windows Node/Python 组合；Windows 显式跳过 7 个 Bash/curl 示例测试，这些仍由 Linux/macOS 执行。编码回归覆盖带 BOM 的 UTF-8 配置/JSON、中文与空格路径、emoji、CRLF/LF 正文、stdin 和非 UTF-8 默认编码下的重定向输出。修改运行时或输入输出行为时，须保持两版结果一致。

- `tests/test_cli.py`：CLI 参数、配置路由、预检、载荷对齐及 Python 传输行为。
- `tests/test_setup.py`：首次初始化、拒绝覆盖、诊断与凭证隐藏、权限错误、配置优先级、共享安装冲突和链接，以及私有文件排除与发布文件链接拒绝。Windows 跳过 POSIX 文件链接测试，目录 junction 在 Windows 实测。
- `tests/test_transport.js`：Node 传输、错误分类、脱敏与重试行为。
- `tests/test_distribution.py`：复制到含空格目录、示例配置、隔离安装、配置优先级与文档链接。
- `tests/test_curl_examples.py`：使用假的 curl 验证签名、JSON 转义、预检、超时不重试；真实 curl 仅解析配置并显示帮助，不联网。
- `tests/offline/`：仅用于测试的网络保护，不是运行依赖。

新增发布文件时同步更新 `scripts/install-shared.js` 的 `RELEASE_FILES` 清单。复制安装只包含这些具体文件；不要用整个目录或 Git 跟踪状态代替清单，也不要把真实凭证写入发布文件。

GitHub Actions 使用同一入口，不需要设置任何仓库 Secret。CI 运行在常规 `pull_request` / `push` 事件，权限仅为读取源码。

## 提交内容

- 说明问题、可复现的输入、修改后的行为与测试结果。
- 平台协议或格式变化附官方文档链接，更新相关指南。
- 使用 `test-token`、`test-key` 或 `REPLACE_ME_*` 等明显虚拟值，勿提交真实 webhook、密钥、成员 ID、手机号、聊天记录或本机用户路径。
- 真实配置保存在仓库外；`.gitignore` 是辅助防护，不能替代检查改动内容。
- 不在自动测试中真实发群消息。确需手工联调时使用自己的专用测试群，仅分享脱敏后的结果。

发布前运行全部测试、检查待提交文件、更新 `CHANGELOG.md`，再创建版本标签。本地离线验证不需要登录 GitHub。
