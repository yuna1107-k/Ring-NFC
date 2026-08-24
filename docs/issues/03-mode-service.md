---
title: "Ring モード操作サービス（location_id 解決・get/set mode）"
labels: ["enhancement", "ring"]
---

## 背景
ロケーション単位のモード API を用いて現在モードの取得と設定を行う。
`python-ring-doorbell` の既定ベース URI は `api.ring.com` のため、モード API では
`base_uri="https://app.ring.com"` を明示する。

## タスク
- [ ] `location_id` の解決（`RING_LOCATION_ID` 優先、無ければデバイスから自動検出）
- [ ] 複数拠点検出時は設定を促して停止
- [ ] `get_mode()`：`GET /api/v1/mode/location/{id}` → `mode`
- [ ] `set_mode(mode)`：`POST /api/v1/mode/location/{id}` body `{"mode": ...}`
- [ ] 将来の Ring Alarm 実装差し替えを見据えインターフェースを分離

## 受け入れ基準
- home/away/disarmed の取得・設定が実機で成功する
- 単一拠点なら location_id 未設定でも動作する

## 関連
- requirements: FR-1
- design: 2章, 4章, 9章
