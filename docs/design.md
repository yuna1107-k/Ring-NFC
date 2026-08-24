# 設計書 — Ring NFC モード切替

対応する要件: [requirements.md](./requirements.md)

## 1. システム構成

```
┌─────────────────────────────────────────────┐
│ Raspberry Pi                                 │
│                                              │
│  ┌──────────┐   SPI    ┌─────────────────┐  │
│  │  PN532    │◀────────▶│ nfc_ring_switch │  │
│  │ NFCリーダー│  UID読取 │   (常駐プロセス)  │  │
│  └──────────┘          └────────┬────────┘  │
│        ▲                        │           │
│        │ かざす                  │ HTTPS      │
│   ┌────┴────┐                   │           │
│   │ NFCカード│                   ▼           │
│   └─────────┘         python-ring-doorbell  │
└──────────────────────────────┬──────────────┘
                                │ HTTPS
                                ▼
                    Ring API (app.ring.com)
              /api/v1/mode/location/{location_id}
```

## 2. コンポーネント設計

| モジュール | 役割 |
|-----------|------|
| `config`（.env ローダ） | 環境変数を読み込み、既定値の補完と検証を行う |
| `ring_client` | 認証・セッション生成・トークン更新。`python-ring-doorbell` の薄いラッパー |
| `mode_service` | location_id の解決、現在モード取得（GET）、モード設定（POST） |
| `nfc_reader` | PN532(SPI) から UID を読み取る抽象。将来 USB リーダー等に差し替え可能 |
| `app`（メインループ） | UID読取→デバウンス→トグル判定→モード切替→ログ |
| `authorize`（CLI） | 初回のみ 2FA 認証しトークンをキャッシュ |
| `read_uid`（CLI） | カード UID を表示する設定用ヘルパー |

> 実装ファイル名は目安。単一スクリプト構成でも、モジュール分割構成でも本設計に準拠する。

## 3. データフロー / シーケンス

### 3.1 起動時
1. `.env` を読み込み、設定を検証。
2. トークンキャッシュからセッションを復元（無ければ authorize を促して終了）。
3. `location_id` を解決（`.env` 指定 or デバイス一覧から自動検出）。
4. 現在モードを取得しログ出力。
5. NFC リーダーを初期化し、読み取りループへ。

### 3.2 カードタップ時（トグル）
```
カード検出(UID)
   │
   ├─ CARD_UID 指定あり かつ 不一致 → 無視
   ├─ 直前と同一UID かつ debounce 秒以内 → 無視
   │
   ▼
現在モードを GET
   │  now == TOGGLE_MODE_A ?
   ├─ Yes → target = TOGGLE_MODE_B
   └─ No  → target = TOGGLE_MODE_A
   │
   ▼
モードを POST（target）
   │
   ▼
結果をログ出力（成功/失敗）
```

## 4. Ring API 仕様（利用箇所）

- 認証: `python-ring-doorbell` の `Auth` が OAuth・2FA・トークン更新を担当。
  トークンは更新コールバックでローカルファイルに保存。
- モード取得: `GET https://app.ring.com/api/v1/mode/location/{location_id}`
  → レスポンスの `mode`（`disarmed` / `home` / `away`）。
- モード設定: `POST https://app.ring.com/api/v1/mode/location/{location_id}`
  ボディ `{"mode": "home" | "away" | "disarmed"}`。
- 呼び出しは `Ring.async_query(url, method, json=..., base_uri="https://app.ring.com")` を利用。
  （`python-ring-doorbell` の既定ベース URI は `api.ring.com` のため `base_uri` を明示する）

## 5. 設定（環境変数 / `.env`）

| 変数 | 必須 | 既定 | 説明 |
|------|------|------|------|
| `RING_LOCATION_ID` | 任意 | （空=自動検出） | 対象ロケーション ID。複数拠点がある場合は必須 |
| `RING_TOKEN_CACHE` | 任意 | `./ring_token.cache` | トークンキャッシュの保存先パス |
| `RING_USER_AGENT` | 任意 | `RingNfcSwitch/1.0` | Ring API 用の User-Agent 名 |
| `PN532_CS_PIN` | 任意 | `D25` | PN532 の CS(SS) に接続した GPIO（例: `D8`=CE0） |
| `DEBOUNCE_SECONDS` | 任意 | `3` | 同一カード連続読取を無視する秒数 |
| `CARD_UID` | 任意 | （空=任意カード） | 反応対象カードの UID（大文字・区切りなし） |
| `TOGGLE_MODE_A` | 任意 | `home` | トグル対象モード A |
| `TOGGLE_MODE_B` | 任意 | `away` | トグル対象モード B |

- `.env` は **コミットしない**。テンプレートとして `.env.example` を配布する。
- 初回認証で使うメール/パスワードは対話入力とし、`.env` には保存しない
  （2FA が絡むため。必要なら任意で追加可能だが非推奨）。

## 6. セキュリティ設計

- リポジトリを公開可能にするため、以下を **gitignore** する:
  `.env`, `*.token.cache`, `ring_token.cache`, `__pycache__/`, `venv/`。
- トークンキャッシュは権限 `600` で保存し、本人のみ読み取り可能とする。
- Ring 認証情報（パスワード）はファイルに保存せず、初回のみ標準入力で受け取る。
- ログには UID とモード名のみ出力し、トークン等の秘密情報は出力しない。

## 7. デプロイ設計

- Python 仮想環境（`venv`）に依存をインストール。
- systemd ユニットで常駐化（`Restart=on-failure`、`After=network-online.target`）。
- ログは `journalctl -u <service>` で確認。

## 8. エラーハンドリング方針

| 事象 | 挙動 |
|------|------|
| トークン失効 | 起動時に検知しメッセージを出して終了（authorize を促す） |
| モード取得/設定の一時エラー | 例外を捕捉してログ出力、プロセスは継続。次のタップで再試行 |
| PN532 未検出 | 起動時に明示エラー（配線 / SPI 有効化 / CS ピンを案内） |
| 複数拠点検出 | `RING_LOCATION_ID` の設定を促して終了 |

## 9. 将来拡張

- **Ring Alarm 対応**: ベースステーションありの場合は WebSocket 経由の武装/解除が必要。
  `ring-mqtt`（Node.js）や `ring-client-api` の `armAway()/armHome()/disarm()` を用いる構成に
  切り替える。`mode_service` をインターフェース化し実装を差し替え可能にする。
- **複数カード / 複数モード**: `CARD_UID` を「UID→モード」のマップに拡張。
- **フィードバック**: LED / ブザー / 音声で切替結果を通知。
- **USB リーダー対応**: `nfc_reader` を差し替え（ACR122U + nfcpy/pyscard 等）。

## 10. ディレクトリ構成（予定）

```
Ring-NFC/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── docs/
│   ├── requirements.md
│   ├── design.md
│   └── issues/            # Issue 下書き
├── scripts/
│   └── create_issues.sh   # gh でIssueをまとめて作成
└── src/                   # 実装（今後）
    ├── authorize.py
    ├── read_uid.py
    └── nfc_ring_switch.py
```
