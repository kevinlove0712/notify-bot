#!/usr/bin/env python3
"""Prepare a single text request for curl; this helper never sends HTTP requests.

stdout contains credentials: consume it through the example scripts, not a log.
Reuse the CLI's validation and signing instead of maintaining a third copy.
"""
import argparse
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys

loader = importlib.machinery.SourceFileLoader(
    "notify_send", str(Path(__file__).resolve().parents[2] / "scripts/notify-send"))
spec = importlib.util.spec_from_loader(loader.name, loader)
bot = importlib.util.module_from_spec(spec)
loader.exec_module(bot)


def main():
    parser = argparse.ArgumentParser(description="Prepare one named target's text request for curl")
    parser.add_argument("platform", choices=("feishu", "wecom"))
    parser.add_argument("target", help="Target name within the platform")
    parser.add_argument("body_file", help="UTF-8 text file, or - for stdin")
    parser.add_argument("--config", help="Defaults to NOTIFY_CONFIG_FILE or the CLI default")
    options = parser.parse_args()
    argv = ["--platform", options.platform, "--target", options.target, "text"]
    if options.config:
        argv += ["--config", options.config]
    args = bot.parse_args(argv)
    args.positional = [bot.read_text(options.body_file)]
    if not args.positional[0].strip():
        bot.fail("正文不能为空")
    target = bot.resolve_targets(args)[0]
    if any(ord(char) < 33 or ord(char) == 127 for char in target["url"]):
        bot.fail("webhook 不允许空白或控制字符（地址已隐藏）")
    bot.validate_args(args, target["platform"])
    payload = bot.prepare_payload(target, bot.build_payload(target["platform"], args))
    settings = {
        "url": target["url"], "request": "POST",
        "header": "Content-Type: application/json",
        "data-binary": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        "proto": "=https", "connect-timeout": "10", "max-time": "15",
        "write-out": "\nHTTP_STATUS=%{http_code}\n",
    }
    # Emit only after every input has passed validation. curl consumes stdin.
    print("\n".join(f"{key} = {json.dumps(value, ensure_ascii=False)}"
                    for key, value in settings.items()) + "\nsilent\ngloboff")


if __name__ == "__main__":
    # curl config passed through a binary pipe must stay UTF-8 on Windows too.
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    try:
        main()
    except bot.NotifyError as error:
        print(f"错误：{error}", file=sys.stderr)
        sys.exit(error.exit_code)
    except (OSError, UnicodeError, ValueError):
        print("错误：本地配置或正文读取失败（详情已隐藏）", file=sys.stderr)
        sys.exit(2)
