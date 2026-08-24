"""ロケーション単位のモード API（get/set）。

Ring Alarm ベースステーションが無い構成（カメラ/ドアベルのみ）を対象とする。
`python-ring-doorbell` の既定ベース URI は `api.ring.com` のため、
モード API 呼び出し時は `base_uri="https://app.ring.com"` を明示する。

将来 Ring Alarm 対応（WebSocket 経由の armAway/armHome/disarm）に差し替えられるよう、
`ModeService` をこのモジュールの唯一の公開インターフェースとして扱う（design.md 9章）。
"""

from __future__ import annotations

from ring_doorbell import Ring

APP_BASE_URI = "https://app.ring.com"
_MODE_PATH = "/api/v1/mode/location/{location_id}"


class ModeServiceError(RuntimeError):
    """location_id の解決やモード取得/設定に失敗した場合に送出する。"""


async def resolve_location_id(ring: Ring, configured_id: str | None) -> str:
    """対象ロケーション ID を解決する。

    `configured_id`（RING_LOCATION_ID）が指定されていればそれを使う。
    未指定の場合はデバイス一覧から自動検出し、複数拠点があればエラーにする。
    """
    if configured_id:
        return configured_id

    await ring.async_update_devices()
    location_ids = {
        device.location_id
        for device in ring.get_device_list()
        if device.location_id is not None
    }

    if not location_ids:
        raise ModeServiceError(
            "ロケーションが見つかりませんでした。RING_LOCATION_ID を設定してください。"
        )
    if len(location_ids) > 1:
        raise ModeServiceError(
            "複数のロケーションが検出されました。"
            f"RING_LOCATION_ID に一つを指定してください: {sorted(location_ids)}"
        )
    return next(iter(location_ids))


class ModeService:
    """location_id に紐づくモードの取得/設定を行う。"""

    def __init__(self, ring: Ring, location_id: str) -> None:
        self._ring = ring
        self._location_id = location_id

    async def get_mode(self) -> str:
        resp = await self._ring.async_query(
            _MODE_PATH.format(location_id=self._location_id),
            method="GET",
            base_uri=APP_BASE_URI,
        )
        data = resp.json()
        mode = data.get("mode")
        if not mode:
            raise ModeServiceError(f"モード取得のレスポンスが不正です: {data!r}")
        return mode

    async def set_mode(self, mode: str) -> None:
        await self._ring.async_query(
            _MODE_PATH.format(location_id=self._location_id),
            method="POST",
            json={"mode": mode},
            base_uri=APP_BASE_URI,
        )
