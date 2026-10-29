"""LAN 上の端末の在/不在を検出し、在宅/不在の判定を行う。

検出方法（Linux / Raspberry Pi OS 前提、root 不要）:
1. `ping` を1回送る。応答があれば「在」。
2. 応答が無くても、スマホはスリープ中に ICMP を無視して ARP にだけ応答することが多い。
   そこで `ip neigh` で ARP エントリを数秒間監視し、REACHABLE になれば「在」とみなす。

ホスト名を指定した場合は、確認のたびに IP を引き直してから上記を行う
（スマホの MAC ランダム化で IP が変わっても追従できる）。名前が引けなければ「不在」。
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import random
import socket
import struct
import time
from dataclasses import dataclass

_logger = logging.getLogger(__name__)

_PING_TIMEOUT_SECONDS = 2
# STALE な ARP エントリは送信後 約5秒（delay_first_probe_time）経ってから再確認されるため、
# それより少し長く待つ。
_ARP_WAIT_SECONDS = 7.0
_ARP_POLL_SECONDS = 0.5
_DNS_TIMEOUT_SECONDS = 2.0

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


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _skip_dns_name(data: bytes, pos: int) -> int:
    while True:
        length = data[pos]
        if length == 0:
            return pos + 1
        if length & 0xC0 == 0xC0:  # 圧縮ポインタ
            return pos + 2
        pos += 1 + length


def _dns_query_a(name: str, server: str) -> str | None:
    """DNS サーバーに A レコードを直接問い合わせる（失敗・該当なしは None）。

    systemd-resolved はドットを含まない名前（例: スマホのホスト名）を
    ルーターの DNS に転送しないため、ルーターに直接聞くために使う。
    """
    query_id = random.getrandbits(16)
    qname = b"".join(
        bytes([len(label)]) + label.encode("ascii")
        for label in name.rstrip(".").split(".")
    ) + b"\0"
    packet = struct.pack(">HHHHHH", query_id, 0x0100, 1, 0, 0, 0) + qname
    packet += struct.pack(">HH", 1, 1)  # QTYPE=A, QCLASS=IN

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(_DNS_TIMEOUT_SECONDS)
            sock.sendto(packet, (server, 53))
            data, _ = sock.recvfrom(512)
        resp_id, flags, qdcount, ancount, _, _ = struct.unpack(">HHHHHH", data[:12])
        if resp_id != query_id or flags & 0x000F:  # ID 不一致 / RCODE がエラー
            return None
        pos = 12
        for _ in range(qdcount):
            pos = _skip_dns_name(data, pos) + 4
        for _ in range(ancount):
            pos = _skip_dns_name(data, pos)
            rtype, _, _, rdlength = struct.unpack(">HHIH", data[pos : pos + 10])
            pos += 10
            if rtype == 1 and rdlength == 4:
                return socket.inet_ntoa(data[pos : pos + 4])
            pos += rdlength
    except (OSError, struct.error, IndexError):
        return None
    return None


class PresenceDetector:
    """指定端末（IP またはホスト名）がネットワーク上に居るかを確認する。"""

    def __init__(self, hosts: tuple[str, ...], dns_server: str | None = None) -> None:
        self._hosts = hosts
        self._dns_server = dns_server
        self._ip_command_available = True
        self._last_resolved: dict[str, str | None] = {}

    async def resolve(self, host: str) -> str | None:
        """ホスト名を IPv4 アドレスに解決する（IP ならそのまま返す）。"""
        if _is_ip(host):
            return host
        loop = asyncio.get_running_loop()
        if self._dns_server is not None:
            ip = await loop.run_in_executor(None, _dns_query_a, host, self._dns_server)
        else:
            try:
                infos = await loop.getaddrinfo(host, None, family=socket.AF_INET)
                ip = infos[0][4][0] if infos else None
            except OSError:
                ip = None

        if host not in self._last_resolved or self._last_resolved[host] != ip:
            if ip is None:
                _logger.info("%s の IP が引けません（不在扱い）", host)
            else:
                _logger.info("%s -> %s", host, ip)
            self._last_resolved[host] = ip
        return ip

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
        ip = await self.resolve(host)
        if ip is None:
            return False
        if await self._ping(ip):
            return True
        return await self._arp_reachable(ip)

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
