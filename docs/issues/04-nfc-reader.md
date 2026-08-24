---
title: "NFC リーダー抽象（PN532 SPI・UID 読み取り）"
labels: ["enhancement", "hardware"]
---

## 背景
PN532（SPI 接続）からカード UID を読み取る。将来 USB リーダー等へ差し替え可能なよう
抽象化しておく。

## タスク
- [ ] PN532(SPI) 初期化（`PN532_CS_PIN` を使用、firmware 検出ログ）
- [ ] `read_uid(timeout)`：UID を大文字 HEX 文字列で返す
- [ ] `src/read_uid.py`：UID を表示する設定用 CLI
- [ ] PN532 未検出時の分かりやすいエラー（SPI 有効化・配線・CS ピン案内）

## 受け入れ基準
- カードをかざすと安定して UID を取得できる
- `read_uid.py` で UID を確認し `.env` に設定できる

## 関連
- requirements: FR-2
- design: 2章, 8章
