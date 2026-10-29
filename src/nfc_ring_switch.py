#!/usr/bin/env python3
"""Ring のモードを自動で切り替える常駐プロセス。

- 端末検出（PRESENCE_HOSTS）: 指定端末が一定時間ネットワークから消えたら不在（away）、
  再び接続したら在宅（home）に切り替える。
- NFC（NFC_ENABLED=true のとき）: カードをかざすたびに home⇔away をトグルする。
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time

from config import Config, load_config
from mode_service import ModeService, ModeServiceError, resolve_location_id
from nfc_reader import NfcReader, NfcReaderError, create_reader
from presence import PRESENT, PresenceDetector, PresenceTracker
from ring_client import AuthorizationRequiredError, create_authenticated_ring

_logger = logging.getLogger("ring_nfc_switch")

_READ_POLL_TIMEOUT = 0.5


def _target_mode(current: str, config: Config) -> str:
    if current == config.toggle_mode_a:
        return config.toggle_mode_b
    return config.toggle_mode_a


async def _read_loop(
    reader: NfcReader,
    mode_service: ModeService,
    config: Config,
    mode_lock: asyncio.Lock,
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
            async with mode_lock:
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


async def _apply_mode(
    mode_service: ModeService, target_mode: str, reason: str, mode_lock: asyncio.Lock
) -> None:
    async with mode_lock:
        current_mode = await mode_service.get_mode()
        if current_mode == target_mode:
            _logger.info("%s: 既に %s のため変更しません", reason, target_mode)
            return
        await mode_service.set_mode(target_mode)
    _logger.info("%s: モードを切り替えました: %s -> %s", reason, current_mode, target_mode)


async def _presence_loop(
    detector: PresenceDetector,
    mode_service: ModeService,
    config: Config,
    mode_lock: asyncio.Lock,
) -> None:
    tracker = PresenceTracker(
        absent_seconds=config.presence_absent_seconds,
        last_seen_at=time.monotonic(),
    )
    was_seen: bool | None = None

    while True:
        results = await detector.check()
        present = any(results.values())
        now = time.monotonic()

        if present != was_seen:
            if present:
                seen = [h for h, ok in results.items() if ok]
                _logger.info("端末を検出しました: %s", ", ".join(seen))
            else:
                _logger.info(
                    "端末が見えなくなりました（%d 秒続いたら不在にします）",
                    config.presence_absent_seconds,
                )
            was_seen = present

        desired = tracker.desired_state(present, now)
        if desired is not None and desired != tracker.state:
            if desired == PRESENT:
                target, reason = config.presence_home_mode, "端末が接続"
            else:
                target = config.presence_away_mode
                reason = f"端末が {int(tracker.unseen_seconds(now))} 秒間未接続"
            try:
                await _apply_mode(mode_service, target, reason, mode_lock)
                tracker.state = desired
            except Exception:
                _logger.exception(
                    "モード切替に失敗しました（%d 秒後に再試行します）",
                    config.presence_check_interval,
                )

        await asyncio.sleep(config.presence_check_interval)


async def _run() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    config = load_config()
    if not config.presence_enabled and not config.nfc_enabled:
        _logger.error(
            "PRESENCE_HOSTS が未設定で、NFC_ENABLED も false です。"
            "どちらか（または両方）を .env で有効にしてください。"
        )
        return 1

    if config.presence_enabled:
        _logger.info(
            "端末検出: hosts=%s 不在判定=%ss 確認間隔=%ss mode=%s/%s",
            ",".join(config.presence_hosts),
            config.presence_absent_seconds,
            config.presence_check_interval,
            config.presence_home_mode,
            config.presence_away_mode,
        )
    if config.nfc_enabled:
        _logger.info(
            "NFC: toggle=%s<->%s debounce=%ss card_uid=%s",
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

    mode_lock = asyncio.Lock()
    tasks: list[asyncio.Future] = []
    reader: NfcReader | None = None

    if config.nfc_enabled:
        try:
            reader = create_reader(config)
        except NfcReaderError as ex:
            _logger.error("%s", ex)
            return 1
        _logger.info(
            "NFCリーダー検出: type=%s firmware=%s",
            config.nfc_reader_type,
            getattr(reader, "firmware_version", "N/A"),
        )
        tasks.append(
            asyncio.ensure_future(_read_loop(reader, mode_service, config, mode_lock))
        )
        _logger.info("NFC 読み取りループを開始しました。カードをかざしてください。")

    if config.presence_enabled:
        detector = PresenceDetector(
            config.presence_hosts, config.presence_dns_server
        )
        tasks.append(
            asyncio.ensure_future(
                _presence_loop(detector, mode_service, config, mode_lock)
            )
        )
        _logger.info("端末検出ループを開始しました。")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    stop_task = asyncio.ensure_future(stop_event.wait())
    done, _ = await asyncio.wait(
        [stop_task, *tasks], return_when=asyncio.FIRST_COMPLETED
    )

    exit_code = 0
    for task in tasks:
        if task in done and not task.cancelled() and task.exception() is not None:
            _logger.error("ループが異常終了しました", exc_info=task.exception())
            exit_code = 1
        task.cancel()
    stop_task.cancel()

    close = getattr(reader, "close", None)
    if close is not None:
        close()
    _logger.info("終了します。")
    return exit_code


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
