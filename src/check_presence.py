#!/usr/bin/env python3
"""PRESENCE_HOSTS の端末が検出できるかを確認するための設定用 CLI。

使い方:
  python3 src/check_presence.py                 # .env の PRESENCE_HOSTS を確認
  python3 src/check_presence.py 192.168.1.23    # 指定 IP を確認
Ctrl+C で終了するまで、確認間隔ごとに結果を表示し続ける。
"""

from __future__ import annotations

import asyncio
import sys
import time

from config import ConfigError, parse_hosts, load_config
from presence import PresenceDetector


async def _run(hosts: tuple[str, ...], interval: float) -> None:
    detector = PresenceDetector(hosts)
    while True:
        results = await detector.check()
        stamp = time.strftime("%H:%M:%S")
        line = "  ".join(f"{h}={'在' if ok else '不在'}" for h, ok in results.items())
        print(f"[{stamp}] {line}", flush=True)
        await asyncio.sleep(interval)


def main() -> int:
    config = load_config()
    try:
        hosts = parse_hosts(",".join(sys.argv[1:])) if sys.argv[1:] else config.presence_hosts
    except ConfigError as ex:
        print(f"エラー: {ex}", file=sys.stderr)
        return 1
    if not hosts:
        print("エラー: PRESENCE_HOSTS が未設定です（引数で IP を指定することもできます）", file=sys.stderr)
        return 1

    print(f"確認対象: {', '.join(hosts)}（{config.presence_check_interval:g} 秒ごと / Ctrl+C で終了）")
    try:
        asyncio.run(_run(hosts, config.presence_check_interval))
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
