"""環境変数（.env）から設定を読み込み、検証する。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

VALID_MODES = {"home", "away", "disarmed"}

DEFAULT_TOKEN_CACHE = "./ring_token.cache"
DEFAULT_USER_AGENT = "RingNfcSwitch/1.0"
DEFAULT_PN532_CS_PIN = "D25"
DEFAULT_DEBOUNCE_SECONDS = 3.0
DEFAULT_TOGGLE_MODE_A = "home"
DEFAULT_TOGGLE_MODE_B = "away"


class ConfigError(ValueError):
    """設定値が不正、または欠落している場合に送出する。"""


@dataclass(frozen=True)
class Config:
    ring_location_id: str | None
    ring_token_cache: str
    ring_user_agent: str
    pn532_cs_pin: str
    debounce_seconds: float
    card_uid: str | None
    toggle_mode_a: str
    toggle_mode_b: str


def _normalize_uid(raw: str) -> str:
    return raw.strip().upper().replace(":", "").replace("-", "").replace(" ", "")


def _parse_debounce(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as ex:
        raise ConfigError(
            f"DEBOUNCE_SECONDS は数値である必要があります: {raw!r}"
        ) from ex
    if value < 0:
        raise ConfigError("DEBOUNCE_SECONDS は 0 以上である必要があります")
    return value


def _validate_mode(name: str, value: str) -> str:
    mode = value.strip().lower()
    if mode not in VALID_MODES:
        raise ConfigError(
            f"{name} は {sorted(VALID_MODES)} のいずれかである必要があります: {value!r}"
        )
    return mode


def load_config(env_path: str | None = None) -> Config:
    """`.env` を読み込み、既定値の補完と検証を行った `Config` を返す。"""
    load_dotenv(dotenv_path=env_path, override=False)

    ring_location_id = os.environ.get("RING_LOCATION_ID", "").strip() or None
    ring_token_cache = os.environ.get("RING_TOKEN_CACHE", "").strip() or DEFAULT_TOKEN_CACHE
    ring_user_agent = os.environ.get("RING_USER_AGENT", "").strip() or DEFAULT_USER_AGENT
    pn532_cs_pin = os.environ.get("PN532_CS_PIN", "").strip() or DEFAULT_PN532_CS_PIN
    debounce_seconds = _parse_debounce(
        os.environ.get("DEBOUNCE_SECONDS", "").strip() or str(DEFAULT_DEBOUNCE_SECONDS)
    )
    card_uid_raw = os.environ.get("CARD_UID", "").strip()
    card_uid = _normalize_uid(card_uid_raw) if card_uid_raw else None
    toggle_mode_a = _validate_mode(
        "TOGGLE_MODE_A", os.environ.get("TOGGLE_MODE_A", "").strip() or DEFAULT_TOGGLE_MODE_A
    )
    toggle_mode_b = _validate_mode(
        "TOGGLE_MODE_B", os.environ.get("TOGGLE_MODE_B", "").strip() or DEFAULT_TOGGLE_MODE_B
    )
    if toggle_mode_a == toggle_mode_b:
        raise ConfigError(
            "TOGGLE_MODE_A と TOGGLE_MODE_B は異なるモードである必要があります"
        )

    return Config(
        ring_location_id=ring_location_id,
        ring_token_cache=ring_token_cache,
        ring_user_agent=ring_user_agent,
        pn532_cs_pin=pn532_cs_pin,
        debounce_seconds=debounce_seconds,
        card_uid=card_uid,
        toggle_mode_a=toggle_mode_a,
        toggle_mode_b=toggle_mode_b,
    )
