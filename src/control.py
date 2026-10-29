"""同じ Pi 上の別プロセス（ステータスページ等）向けのローカル操作 API。

127.0.0.1 にだけ待ち受ける。Ring の認証情報を使うのはこのプロセスだけにして、
トークン更新が複数プロセスで取り合いにならないようにする。

  GET  /status   現在のモード・在宅状態・Ring 機器（ファームウェア等）を返す
  POST /mode     {"mode": "home" | "away" | "disarmed"} でモードを変更
  POST /restart  プロセスを再起動する（終了コード 1 で抜け、systemd が再起動する）
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from importlib.metadata import PackageNotFoundError, version

from aiohttp import web
from ring_doorbell import Ring

from config import VALID_MODES
from mode_service import ModeService

_logger = logging.getLogger(__name__)

# Ring API を叩きすぎないよう、/status でのモード再取得はこの秒数ごとに留める
MODE_REFRESH_SECONDS = 60.0
# 機器情報（ファームウェア・電池など）の再取得間隔
DEVICES_REFRESH_SECONDS = 600.0


def _lib_version() -> str | None:
    try:
        return version("ring_doorbell")
    except PackageNotFoundError:
        return None


def _device_info(device) -> dict:
    def attr(name):
        try:
            return getattr(device, name)
        except Exception:  # noqa: BLE001 - 機種によって無い属性がある
            return None

    return {
        "name": attr("name"),
        "family": attr("family"),
        "model": attr("model"),
        "firmware": attr("firmware"),
        "battery": attr("battery_life"),
        "wifi_name": attr("wifi_name"),
        "wifi_signal": attr("wifi_signal_strength"),
    }


@dataclass
class RuntimeState:
    """各ループが更新し、/status で返す実行時の状態。"""

    mode: str | None = None
    mode_checked_at: float = 0.0  # time.time()
    present: bool | None = None
    present_since: float | None = None
    hosts: dict[str, str | None] = field(default_factory=dict)  # ホスト -> 解決した IP
    started_at: float = field(default_factory=time.time)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.mode_checked_at = time.time()

    def set_present(self, present: bool) -> None:
        if present != self.present:
            self.present_since = time.time()
        self.present = present


class ControlServer:
    def __init__(
        self,
        ring: Ring,
        state: RuntimeState,
        mode_service: ModeService,
        mode_lock: asyncio.Lock,
        restart_event: asyncio.Event,
        port: int,
    ) -> None:
        self._ring = ring
        self._devices: list[dict] = []
        self._devices_at = 0.0
        self._state = state
        self._mode_service = mode_service
        self._mode_lock = mode_lock
        self._restart_event = restart_event
        self._port = port
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = web.Application()
        app.add_routes([
            web.get("/status", self._status),
            web.post("/mode", self._set_mode),
            web.post("/restart", self._restart),
        ])
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, "127.0.0.1", self._port).start()
        _logger.info("操作 API を開始しました: http://127.0.0.1:%d", self._port)

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()

    async def _status(self, request: web.Request) -> web.Response:
        state = self._state
        error = None
        if time.time() - state.mode_checked_at > MODE_REFRESH_SECONDS:
            try:
                async with self._mode_lock:
                    state.set_mode(await self._mode_service.get_mode())
            except Exception as ex:  # noqa: BLE001 - 取得失敗は呼び出し元に伝える
                _logger.warning("モードの再取得に失敗しました: %s", ex)
                error = str(ex)
        if time.time() - self._devices_at > DEVICES_REFRESH_SECONDS:
            self._devices_at = time.time()
            try:
                await self._ring.async_update_devices()
                self._devices = [_device_info(d) for d in self._ring.get_device_list()]
            except Exception as ex:  # noqa: BLE001
                _logger.warning("Ring 機器情報の取得に失敗しました: %s", ex)
        return web.json_response({
            "devices": self._devices,
            "lib_version": _lib_version(),
            "mode": state.mode,
            "mode_checked_at": state.mode_checked_at or None,
            "mode_error": error,
            "present": state.present,
            "present_since": state.present_since,
            "hosts": state.hosts,
            "started_at": state.started_at,
        })

    async def _set_mode(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            mode = str(body.get("mode", "")).strip().lower()
        except Exception:  # noqa: BLE001
            return web.json_response({"error": "JSON が不正です"}, status=400)
        if mode not in VALID_MODES:
            return web.json_response(
                {"error": f"mode は {sorted(VALID_MODES)} のいずれかです"}, status=400
            )
        try:
            async with self._mode_lock:
                current = await self._mode_service.get_mode()
                if current != mode:
                    await self._mode_service.set_mode(mode)
                self._state.set_mode(mode)
        except Exception as ex:  # noqa: BLE001
            _logger.exception("操作 API からのモード変更に失敗しました")
            return web.json_response({"error": str(ex)}, status=502)
        _logger.info("操作 API: モードを切り替えました: %s -> %s", current, mode)
        return web.json_response({"mode": mode, "previous": current})

    async def _restart(self, request: web.Request) -> web.Response:
        _logger.info("操作 API: 再起動が要求されました")
        asyncio.get_running_loop().call_later(0.3, self._restart_event.set)
        return web.json_response({"restarting": True})
