#!/usr/bin/env bash
# Usage: bash feishu-text.sh TARGET BODY_FILE [--config FILE]
set -euo pipefail
example_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
request_config="$(python3 "$example_dir/prepare-request.py" feishu "$@")"
# Credentials enter curl through stdin, never through its argument list.
if printf '%s\n' "$request_config" | curl -q --config -; then
  exit 0
else
  result=$?
  printf 'curl 请求未正常完成（退出码 %s），发送结果需人工确认，请勿自动重试。\n' "$result" >&2
  exit "$result"
fi
