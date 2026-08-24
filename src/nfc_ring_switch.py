#!/usr/bin/env python3
"""NFC カードをかざすたびに Ring のモードを home⇔away でトグルする常駐プロセス。"""

from __future__ import annotations

import asyncio
import logging
import signal
import time

from config import Config, load_config
from mode_service import ModeService, ModeServiceError, resolve_location_id
from nfc_reader import NfcReaderError, PN532Reader
from ring_client import AuthorizationRequiredError, create_authenticated_ring

_logger = logging.getLogger("ring_nfc_switch")

_READ_POLL_TIMEOUT = 0.5


def _target_mode(current: str, config: Config) -> str:
    if current == config.toggle_mode_a:
        return config.toggle_mode_b
    return config.toggle_mode_a


async def _read_loop(
    reader: PN532Reader, mode_service: ModeService, config: Config
) -> None:
    loop = asyncio.get_running_loop()
    last_uid: str | None = None
    last_read_at = 0.0

    while True:
        uid = await loop.run_in_executor(
            None, reader.read_uid, _READ_POLL_TIMEOUT
        )
        if uid is None:
            continue

        if config.card_uid is not None and uid != config.card_uid:
            _logger.debug("対象外のカードを無視しました: %s", uid)
            continue

        now = time.monotonic()
        if uid == last_uid and (now - last_read_at) < config.debounce_seconds:
            _logger.debug("デバウンスによりカードを無視しました: %s", uid)
            continue
        last_uid = uid
        last_read_at = now

        try:
            current_mode = await mode_service.get_mode()
            target_mode = _target_mode(current_mode, config)
            await mode_service.set_mode(target_mode)
            _logger.info(
                "モードを切り替えました: %s -> %s (uid=%s)",
                current_mode,
                target_mode,
                uid,
            )
        except Exception:
            _logger.exception("モード切替に失敗しました（次のタップで再試行します）")


async def _run() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    config = load_config()
    _logger.info(
        "設定: toggle=%s<->%s debounce=%ss card_uid=%s",
        config.toggle_mode_a,
        config.toggle_mode_b,
        config.debounce_seconds,
        config.card_uid or "(任意)",
    )

    try:
        ring = await create_authenticated_ring(config)
    except AuthorizationRequiredError as ex:
        _logger.error("%s", ex)
        return 1

    try:
        location_id = await resolve_location_id(ring, config.ring_location_id)
    except ModeServiceError as ex:
        _logger.error("%s", ex)
        return 1

    mode_service = ModeService(ring, location_id)
    current_mode = await mode_service.get_mode()
    _logger.info("現在のモード: %s (location_id=%s)", current_mode, location_id)

    try:
        reader = PN532Reader(config.pn532_cs_pin)
    except NfcReaderError as ex:
        _logger.error("%s", ex)
        return 1
    _logger.info("PN532 検出: firmware=%s", reader.firmware_version)

    _logger.info("読み取りループを開始しました。カードをかざしてください。")

    read_loop_task = asyncio.ensure_future(_read_loop(reader, mode_service, config))
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    read_loop_task.cancel()
    _logger.info("終了します。")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
