---
title: "ドキュメント整備（配線図・セットアップ手順）"
labels: ["documentation"]
---

## 背景
実装完了後、実機構築に必要な配線とセットアップ手順を README / docs に反映する。

## タスク
- [ ] PN532–Pi の SPI 配線表（VCC/GND/SCK/MISO/MOSI/CS）
- [ ] SPI 有効化（raspi-config）手順
- [ ] venv・依存インストール・authorize・起動の一連手順
- [ ] トラブルシュート（PN532 未検出 / トークン失効 / モード変わらない）

## 受け入れ基準
- 手順どおりで初見でも構築できる
- 秘密情報の扱い（.env / トークン）が明記されている

## 関連
- design: 7章, 8章
