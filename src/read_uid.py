#!/usr/bin/env python3
"""カードをかざして UID を確認するための設定用 CLI。

`.env` の CARD_UID に設定する値を確認するときに使う。
"""

from __future__ import annotations

import sys

from config import load_config
from nfc_reader import NfcReaderError, PN532Reader


def main() -> int:
    config = load_config()

    try:
        reader = PN532Reader(config.pn532_cs_pin)
    except NfcReaderError as ex:
        print(f"エラー: {ex}", file=sys.stderr)
        return 1

    print(f"PN532 検出: firmware={reader.firmware_version}")
    print("カードをリーダーにかざしてください（Ctrl+C で終了）")

    last_uid: str | None = None
    try:
        while True:
            uid = reader.read_uid(timeout=0.5)
            if uid is not None and uid != last_uid:
                print(f"UID: {uid}")
                last_uid = uid
            elif uid is None:
                last_uid = None
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
