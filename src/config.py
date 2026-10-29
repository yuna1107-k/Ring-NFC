"""環境変数（.env）から設定を読み込み、検証する。"""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

VALID_MODES = {"home", "away", "disarmed"}
VALID_READER_TYPES = {"pn532", "rcs380"}

DEFAULT_TOKEN_CACHE = "./ring_token.cache"
DEFAULT_USER_AGENT = "RingNfcSwitch/1.0"
DEFAULT_PN532_CS_PIN = "D25"
DEFAULT_DEBOUNCE_SECONDS = 3.0
DEFAULT_TOGGLE_MODE_A = "home"
DEFAULT_TOGGLE_MODE_B = "away"
DEFAULT_NFC_READER_TYPE = "pn532"
DEFAULT_RCS380_DEVICE_PATH = "usb"
DEFAULT_PRESENCE_ABSENT_SECONDS = 600.0
DEFAULT_PRESENCE_CHECK_INTERVAL = 30.0
DEFAULT_PRESENCE_HOME_MODE = "home"
DEFAULT_PRESENCE_AWAY_MODE = "away"
DEFAULT_CONTROL_PORT = 8095

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})*\.?$")


class ConfigError(ValueError):
    """設定値が不正、または欠落している場合に送出する。"""


@dataclass(frozen=True)
class Config:
    ring_location_id: str | None
    ring_token_cache: str
    ring_user_agent: str
    nfc_reader_type: str
    pn532_cs_pin: str
    rcs380_device_path: str
    debounce_seconds: float
    card_uid: str | None
    toggle_mode_a: str
    toggle_mode_b: str
    nfc_enabled: bool
    presence_hosts: tuple[str, ...]
    presence_dns_server: str | None
    presence_absent_seconds: float
    presence_check_interval: float
    presence_home_mode: str
    presence_away_mode: str
    control_port: int

    @property
    def presence_enabled(self) -> bool:
        return bool(self.presence_hosts)


def _normalize_uid(raw: str) -> str:
    return raw.strip().upper().replace(":", "").replace("-", "").replace(" ", "")


def _parse_seconds(name: str, raw: str, *, allow_zero: bool) -> float:
    try:
        value = float(raw)
    except ValueError as ex:
        raise ConfigError(f"{name} は数値である必要があります: {raw!r}") from ex
    if value < 0 or (value == 0 and not allow_zero):
        bound = "0 以上の値" if allow_zero else "0 より大きい値"
        raise ConfigError(f"{name} は {bound}である必要があります")
    return value


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name} は true / false のいずれかである必要があります: {raw!r}")


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def parse_hosts(raw: str) -> tuple[str, ...]:
    hosts: list[str] = []
    for item in raw.split(","):
        host = item.strip()
        if not host:
            continue
        if not _is_ip(host) and not _HOSTNAME_RE.match(host):
            raise ConfigError(
                f"PRESENCE_HOSTS には IP アドレスかホスト名を指定してください: {host!r}"
            )
        if host not in hosts:
            hosts.append(host)
    return tuple(hosts)


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
    nfc_reader_type = (
        os.environ.get("NFC_READER_TYPE", "").strip().lower() or DEFAULT_NFC_READER_TYPE
    )
    if nfc_reader_type not in VALID_READER_TYPES:
        raise ConfigError(
            f"NFC_READER_TYPE は {sorted(VALID_READER_TYPES)} のいずれかである必要があります: "
            f"{nfc_reader_type!r}"
        )
    pn532_cs_pin = os.environ.get("PN532_CS_PIN", "").strip() or DEFAULT_PN532_CS_PIN
    rcs380_device_path = (
        os.environ.get("RCS380_DEVICE_PATH", "").strip() or DEFAULT_RCS380_DEVICE_PATH
    )
    debounce_seconds = _parse_seconds(
        "DEBOUNCE_SECONDS",
        os.environ.get("DEBOUNCE_SECONDS", "").strip() or str(DEFAULT_DEBOUNCE_SECONDS),
        allow_zero=True,
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

    nfc_enabled = _parse_bool("NFC_ENABLED", os.environ.get("NFC_ENABLED", ""))
    presence_hosts = parse_hosts(os.environ.get("PRESENCE_HOSTS", ""))
    presence_dns_server = os.environ.get("PRESENCE_DNS_SERVER", "").strip() or None
    if presence_dns_server is not None and not _is_ip(presence_dns_server):
        raise ConfigError(
            f"PRESENCE_DNS_SERVER には IP アドレスを指定してください: {presence_dns_server!r}"
        )
    presence_absent_seconds = _parse_seconds(
        "PRESENCE_ABSENT_SECONDS",
        os.environ.get("PRESENCE_ABSENT_SECONDS", "").strip()
        or str(DEFAULT_PRESENCE_ABSENT_SECONDS),
        allow_zero=False,
    )
    presence_check_interval = _parse_seconds(
        "PRESENCE_CHECK_INTERVAL",
        os.environ.get("PRESENCE_CHECK_INTERVAL", "").strip()
        or str(DEFAULT_PRESENCE_CHECK_INTERVAL),
        allow_zero=False,
    )
    presence_home_mode = _validate_mode(
        "PRESENCE_HOME_MODE",
        os.environ.get("PRESENCE_HOME_MODE", "").strip() or DEFAULT_PRESENCE_HOME_MODE,
    )
    presence_away_mode = _validate_mode(
        "PRESENCE_AWAY_MODE",
        os.environ.get("PRESENCE_AWAY_MODE", "").strip() or DEFAULT_PRESENCE_AWAY_MODE,
    )
    if presence_home_mode == presence_away_mode:
        raise ConfigError(
            "PRESENCE_HOME_MODE と PRESENCE_AWAY_MODE は異なるモードである必要があります"
        )

    control_port_raw = os.environ.get("CONTROL_PORT", "").strip()
    try:
        control_port = int(control_port_raw) if control_port_raw else DEFAULT_CONTROL_PORT
    except ValueError as ex:
        raise ConfigError(f"CONTROL_PORT は整数である必要があります: {control_port_raw!r}") from ex
    if not 0 <= control_port <= 65535:
        raise ConfigError("CONTROL_PORT は 0〜65535 である必要があります（0 で無効）")

    return Config(
        ring_location_id=ring_location_id,
        ring_token_cache=ring_token_cache,
        ring_user_agent=ring_user_agent,
        nfc_reader_type=nfc_reader_type,
        pn532_cs_pin=pn532_cs_pin,
        rcs380_device_path=rcs380_device_path,
        debounce_seconds=debounce_seconds,
        card_uid=card_uid,
        toggle_mode_a=toggle_mode_a,
        toggle_mode_b=toggle_mode_b,
        nfc_enabled=nfc_enabled,
        presence_hosts=presence_hosts,
        presence_dns_server=presence_dns_server,
        presence_absent_seconds=presence_absent_seconds,
        presence_check_interval=presence_check_interval,
        presence_home_mode=presence_home_mode,
        presence_away_mode=presence_away_mode,
        control_port=control_port,
    )
