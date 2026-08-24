"""NFC リーダー抽象。既定実装は PN532（SPI 接続）。

`NfcReader` インターフェースに従う限り、将来 USB リーダー等（ACR122U +
nfcpy/pyscard 等）へ差し替え可能（design.md 9章）。
"""

from __future__ import annotations

from typing import Protocol


class NfcReaderError(RuntimeError):
    """リーダーの初期化や読み取りに失敗した場合に送出する。"""


class NfcReader(Protocol):
    def read_uid(self, timeout: float) -> str | None:
        """カードの UID を大文字 HEX 文字列で返す。タイムアウト時は None。"""
        ...


class PN532Reader:
    """PN532（SPI 接続）から UID を読み取る。"""

    def __init__(self, cs_pin: str) -> None:
        try:
            import board
            import busio
            from adafruit_pn532.spi import PN532_SPI
            from digitalio import DigitalInOut
        except ImportError as ex:
            raise NfcReaderError(
                "PN532 用ライブラリの読み込みに失敗しました。"
                "`pip install -r requirements.txt` を実行し、"
                "Raspberry Pi 上で実行しているか確認してください。"
            ) from ex

        try:
            cs_board_pin = getattr(board, cs_pin)
        except AttributeError as ex:
            raise NfcReaderError(
                f"PN532_CS_PIN {cs_pin!r} は board モジュールに存在しません。"
                "GPIO 名（例: D25, D8）を確認してください。"
            ) from ex

        try:
            spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
            cs = DigitalInOut(cs_board_pin)
            self._pn532 = PN532_SPI(spi, cs, debug=False)
            self._pn532.SAM_configuration()
            ic, ver, rev, support = self._pn532.firmware_version
        except Exception as ex:
            raise NfcReaderError(
                "PN532 が検出できませんでした。SPI が有効になっているか"
                "（raspi-config）、配線と PN532_CS_PIN の設定を確認してください。"
            ) from ex

        self.firmware_version = (ic, ver, rev, support)

    def read_uid(self, timeout: float) -> str | None:
        uid = self._pn532.read_passive_target(timeout=timeout)
        if uid is None:
            return None
        return "".join(f"{byte:02X}" for byte in uid)
