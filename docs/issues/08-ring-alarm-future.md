---
title: "将来対応: Ring Alarm ベースステーションの武装/解除"
labels: ["enhancement", "future"]
---

## 背景
Ring Alarm 本体がある構成では、モード切替は location mode API ではなく
WebSocket 経由の武装/解除になる。`mode_service` をインターフェース化し実装を差し替える。

## タスク
- [ ] `mode_service` をインターフェース化（get/set の抽象）
- [ ] Alarm 実装案の調査（`ring-mqtt` / `ring-client-api` の armAway/armHome/disarm）
- [ ] 構成の自動判定 or `.env` での切替方針を設計

## 受け入れ基準
- Alarm 構成でも同一の NFC トグル体験を提供できる設計になっている

## 関連
- design: 9章
