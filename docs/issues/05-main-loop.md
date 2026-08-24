---
title: "メインループ（トグル制御・デバウンス）"
labels: ["enhancement"]
---

## 背景
NFC 読み取り→トグル判定→モード切替→ログ、を行う常駐本体。カード1枚で home⇔away を切替。

## タスク
- [ ] `src/nfc_ring_switch.py`：起動時に設定・セッション・location_id・現在モードを準備
- [ ] `CARD_UID` 指定時は対象カード以外を無視
- [ ] 同一 UID の連続読取を `DEBOUNCE_SECONDS` 間デバウンス
- [ ] 現在モードを取得し、`TOGGLE_MODE_A`↔`TOGGLE_MODE_B` を判定して切替
- [ ] API 一時エラーは捕捉してログ出力し、プロセスは継続
- [ ] ブロッキングな NFC 読み取りは executor で実行

## 受け入れ基準
- かざすたびに home⇔away が切り替わる
- 連続タップで多重切替しない
- ネットワーク断でも落ちず、次タップで再試行できる

## 関連
- requirements: FR-1, FR-3, FR-5, FR-6, NFR-4
- design: 3章
