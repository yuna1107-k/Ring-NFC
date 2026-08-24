#!/usr/bin/env python3
"""初回のみ対話式で Ring にログインし、トークンをローカルにキャッシュする。

既存のトークンが有効ならそのまま利用し、失効している場合のみ再認証する。
認証後、デバイス一覧と検出された location_id を表示する。
"""

from __future__ import annotations

import asyncio
import sys

from config import load_config
from ring_client import (
    AuthorizationRequiredError,
    create_authenticated_ring,
    interactive_authorize,
)


async def _run() -> int:
    config = load_config()

    try:
        ring = await create_authenticated_ring(config)
        print("既存のトークンは有効です。再認証は不要です。")
        await ring.async_update_devices()
    except AuthorizationRequiredError:
        ring = await interactive_authorize(config)
        print(f"認証に成功しました。トークンを {config.ring_token_cache!r} に保存しました。")

    location_ids: set[str] = set()
    print("\n検出されたデバイス:")
    for device in ring.get_device_list():
        print(f"  - {device.name} (location_id={device.location_id})")
        if device.location_id is not None:
            location_ids.add(device.location_id)

    print("\n検出された location_id:")
    if not location_ids:
        print("  (なし)")
    elif len(location_ids) == 1:
        loc = next(iter(location_ids))
        print(f"  {loc} （単一拠点のため RING_LOCATION_ID は未設定のままで動作します）")
    else:
        print("  複数拠点が検出されました。RING_LOCATION_ID に一つを設定してください:")
        for loc in sorted(location_ids):
            print(f"  - {loc}")

    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
