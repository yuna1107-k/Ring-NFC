"""Ring 認証（初回2FA・トークンキャッシュ）と Ring セッション生成。"""

from __future__ import annotations

import getpass
import json
import logging
import os
from pathlib import Path
from typing import Any

from ring_doorbell import Auth, AuthenticationError, Requires2FAError, Ring

from config import Config

_logger = logging.getLogger(__name__)

_TOKEN_CACHE_MODE = 0o600


class AuthorizationRequiredError(RuntimeError):
    """有効なトークンが無く、対話認証（authorize.py）が必要な場合に送出する。"""


def _make_token_updater(cache_path: str):
    def _update(token: dict[str, Any]) -> None:
        path = Path(cache_path)
        path.write_text(json.dumps(token), encoding="utf-8")
        os.chmod(path, _TOKEN_CACHE_MODE)

    return _update


def _load_cached_token(cache_path: str) -> dict[str, Any] | None:
    path = Path(cache_path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


async def create_authenticated_ring(config: Config) -> Ring:
    """キャッシュ済みトークンから Ring セッションを復元する。

    トークンが無い/失効している場合は `AuthorizationRequiredError` を送出する。
    パスワードの対話入力はここでは行わない（authorize.py の責務）。
    """
    token = _load_cached_token(config.ring_token_cache)
    if token is None:
        raise AuthorizationRequiredError(
            f"トークンキャッシュ {config.ring_token_cache!r} が見つかりません。"
            "先に `python3 src/authorize.py` を実行してください。"
        )

    auth = Auth(
        config.ring_user_agent,
        token,
        _make_token_updater(config.ring_token_cache),
    )
    ring = Ring(auth)
    try:
        await ring.async_create_session()
    except AuthenticationError as ex:
        raise AuthorizationRequiredError(
            "トークンが失効しています。`python3 src/authorize.py` を再実行してください。"
        ) from ex
    return ring


async def interactive_authorize(config: Config) -> Ring:
    """対話式でユーザー名/パスワード/2FAコードを入力させ、認証を行う。

    成功するとトークンキャッシュに保存し、`Ring` インスタンスを返す。
    """
    username = input("Ring email: ").strip()
    password = getpass.getpass("Ring password: ")

    auth = Auth(
        config.ring_user_agent,
        None,
        _make_token_updater(config.ring_token_cache),
    )
    try:
        await auth.async_fetch_token(username, password)
    except Requires2FAError:
        otp_code = input("2FA code: ").strip()
        await auth.async_fetch_token(username, password, otp_code)

    ring = Ring(auth)
    await ring.async_update_devices()
    return ring
