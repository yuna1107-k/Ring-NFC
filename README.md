# Ring NFC モード切替

NFC カード**1枚**を Raspberry Pi のリーダーにかざすたびに、Ring のモードを
**在宅（home）⇔不在（away）でトグル**する仕組みです。スマホやクラウドを介さず、
Pi 単体でローカルに完結します。

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
NFCカード → PN532(SPI) → Raspberry Pi 常駐プロセス
          → python-ring-doorbell
          → Ring API (app.ring.com/api/v1/mode/location/{id})
```

かざすたびに現在モードを確認し、`home` なら `away`、それ以外なら `home` に切り替えます。

## 必要なもの

- Raspberry Pi（Raspberry Pi OS）
- PN532 NFC リーダー（**SPI 接続**推奨）
- NFC カード / タグ 1枚
- Ring アカウント（メール / パスワード / 2FA）

## セットアップ（予定フロー）

```bash
# 1. 設定ファイルを用意
cp .env.example .env
#    .env を編集（CARD_UID / TOGGLE_MODE など）

# 2. 依存インストール
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. 初回認証（トークンをローカルにキャッシュ）
python3 src/authorize.py

# 4. カードのUIDを確認して .env に設定（任意）
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

## 設定

すべて環境変数（`.env`）で与えます。項目一覧は [.env.example](./.env.example) と
[docs/design.md](./docs/design.md#5-設定環境変数env) を参照してください。

> `.env` とトークンキャッシュは `.gitignore` 済みです。リポジトリは公開しても
> 秘密情報が含まれない設計です。

## ライセンス

TBD
