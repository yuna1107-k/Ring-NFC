"""LAN 上の端末の在/不在を検出し、在宅/不在の判定を行う。

検出方法（Linux / Raspberry Pi OS 前提、root 不要）:
1. `ping` を1回送る。応答があれば「在」。
2. 応答が無くても、スマホはスリープ中に ICMP を無視して ARP にだけ応答することが多い。
   そこで `ip neigh` で ARP エントリを数秒間監視し、REACHABLE になれば「在」とみなす。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

_logger = logging.getLogger(__name__)

_PING_TIMEOUT_SECONDS = 2
# STALE な ARP エントリは送信後 約5秒（delay_first_probe_time）経ってから再確認されるため、
# それより少し長く待つ。
_ARP_WAIT_SECONDS = 7.0
_ARP_POLL_SECONDS = 0.5

PRESENT = "present"
ABSENT = "absent"


async def _run(*args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode, stdout.decode(errors="replace")


class PresenceDetector:
    """指定 IP の端末がネットワーク上に居るかを確認する。"""

    def __init__(self, hosts: tuple[str, ...]) -> None:
        self._hosts = hosts
        self._ip_command_available = True

    async def _ping(self, host: str) -> bool:
        try:
            code, _ = await _run(
                "ping", "-c", "1", "-W", str(_PING_TIMEOUT_SECONDS), "-q", host
            )
        except FileNotFoundError:
            _logger.error("ping コマンドが見つかりません（iputils-ping をインストールしてください）")
            return False
        return code == 0

    async def _neigh_state(self, host: str) -> str | None:
        if not self._ip_command_available:
            return None
        try:
            code, out = await _run("ip", "neigh", "show", host)
        except FileNotFoundError:
            _logger.warning("ip コマンドが見つからないため ARP 判定を無効化します（iproute2）")
            self._ip_command_available = False
            return None
        if code != 0 or not out.strip():
            return None
        # 例: "192.168.1.10 dev wlan0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
        return out.split()[-1].upper()

    async def _arp_reachable(self, host: str) -> bool:
        deadline = time.monotonic() + _ARP_WAIT_SECONDS
        while True:
            state = await self._neigh_state(host)
            if state == "REACHABLE":
                return True
            if not self._ip_command_available:
                return False
            if state == "FAILED" or time.monotonic() >= deadline:
                return False
            await asyncio.sleep(_ARP_POLL_SECONDS)

    async def is_present(self, host: str) -> bool:
        if await self._ping(host):
            return True
        return await self._arp_reachable(host)

    async def check(self) -> dict[str, bool]:
        """各ホストの在/不在を並列に確認して返す。"""
        results = await asyncio.gather(*(self.is_present(h) for h in self._hosts))
        return dict(zip(self._hosts, results))


@dataclass
class PresenceTracker:
    """検出結果の時系列から「在宅 / 不在」を判定する（I/O を持たない純粋なロジック）。

    - いずれかの端末が見えたら即座に PRESENT。
    - 全端末が `absent_seconds` 以上続けて見えなければ ABSENT。
    - それより短い切断（スリープ等による一時的な不検出）は無視する。
    """

    absent_seconds: float
    last_seen_at: float
    state: str | None = None

    def desired_state(self, present: bool, now: float) -> str | None:
        if present:
            self.last_seen_at = now
            return PRESENT
        if now - self.last_seen_at >= self.absent_seconds:
            return ABSENT
        return self.state

    def unseen_seconds(self, now: float) -> float:
        return now - self.last_seen_at
