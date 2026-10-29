# Ring NFC モード切替

Raspberry Pi が家の LAN 上で**指定した端末（スマホ等）**を見張り、
**一定時間ネットワークから切断されたら Ring を不在（away）**に、
**再び接続したら在宅（home）**に自動で切り替える仕組みです。
スマホアプリやクラウド連携を介さず、Pi 単体でローカルに完結します。

オプションで、NFC カードをリーダーにかざして home⇔away を手動トグルすることもできます。

> 対象: カメラ / ドアベルのみの構成（Ring Alarm ベースステーションなし）。
> Ring には公式 API がないため、非公式ライブラリ
> [`python-ring-doorbell`](https://github.com/python-ring-doorbell/python-ring-doorbell) を利用します。

## 状態

実装済み。コードは [`src/`](./src) にあります。

- 要件定義: [docs/requirements.md](./docs/requirements.md)
- 設計書: [docs/design.md](./docs/design.md)
- Issue 下書き: [docs/issues/](./docs/issues)

## 仕組み（概要）

```
スマホ(Wi-Fi) ←ping / ARP─ Raspberry Pi 常駐プロセス
(任意) NFCカード → PN532(SPI) ┘   │
                              → python-ring-doorbell
                              → Ring API (app.ring.com/api/v1/mode/location/{id})
```

- `PRESENCE_CHECK_INTERVAL` 秒ごとに端末を確認（ping と ARP 応答の両方で判定）。
- 全端末が `PRESENCE_ABSENT_SECONDS` 秒以上続けて見えなければ `away` に切替。
  それより短い切断（スマホのスリープ等）は無視します。
- どれか1台でも見えたら `home` に切替。
- 既に目的のモードなら何もしません。アプリでの手動変更は、次に在/不在が変わるまで維持されます。

## 必要なもの

- Raspberry Pi（Raspberry Pi OS）
- PN532 NFC リーダー（**SPI 接続**推奨）
- NFC カード / タグ 1枚
- Ring アカウント（メール / パスワード / 2FA）

## セットアップ（予定フロー）

```bash
# 1. 設定ファイルを用意
cp .env.example .env
#    .env を編集（PRESENCE_HOSTS に端末のホスト名か IP を設定）

# 2. 依存インストール
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. 初回認証（トークンをローカルにキャッシュ）
python3 src/authorize.py

# 4. 端末が検出できるか確認（スマホの Wi-Fi を切って「不在」になるか試す）
python3 src/check_presence.py

#    （NFC も使う場合）カードの UID を確認して .env に設定
python3 src/read_uid.py

# 5. 起動
python3 src/nfc_ring_switch.py
```

詳細な配線・手順は [docs/design.md](./docs/design.md) を参照してください。

## 常駐化（systemd）

```bash
sudo cp deploy/ring-nfc.service /etc/systemd/system/ring-nfc.service
# User / WorkingDirectory / ExecStart のパスを環境に合わせて編集
sudo systemctl daemon-reload
sudo systemctl enable --now ring-nfc

# ログ確認
journalctl -u ring-nfc -f
```

## ローカル操作 API

同じ Pi 上のステータスページなどから使う API です（`127.0.0.1:8095`、`CONTROL_PORT` で変更、0 で無効）。
Ring の認証情報を使うのはこのプロセスだけなので、トークン更新の取り合いが起きません。

```bash
curl -s 127.0.0.1:8095/status                              # モード・在宅状態
curl -s -X POST 127.0.0.1:8095/mode -d '{"mode":"away"}'   # モード変更
curl -s -X POST 127.0.0.1:8095/restart                     # 再起動（.env の再読込）
```

## 設定

すべて環境変数（`.env`）で与えます。項目一覧は [.env.example](./.env.example) と
[docs/design.md](./docs/design.md#5-設定環境変数env) を参照してください。

> `.env` とトークンキャッシュは `.gitignore` 済みです。リポジトリは公開しても
> 秘密情報が含まれない設計です。

## ライセンス

TBD
