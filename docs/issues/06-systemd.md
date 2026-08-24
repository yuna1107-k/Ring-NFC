---
title: "systemd による常駐化"
labels: ["deployment"]
---

## 背景
電源投入で自動起動し、異常終了時は自動再起動する常駐運用を用意する。

## タスク
- [ ] `ring-nfc.service`（`Restart=on-failure`, `After=network-online.target`）
- [ ] `WorkingDirectory` / `ExecStart` / `User` をテンプレート化
- [ ] README にインストールとログ確認（`journalctl -u`）手順を追記

## 受け入れ基準
- Pi 再起動後、手動操作なしでサービスが復帰する
- 失敗時に自動再起動する

## 関連
- requirements: FR-7
- design: 7章
