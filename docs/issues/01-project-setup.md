---
title: "プロジェクト初期化と設定基盤（.env ローダ）"
labels: ["setup", "enhancement"]
---

## 背景
設計書 [docs/design.md](../design.md) の「5. 設定（環境変数 / .env）」に基づき、
すべての設定を環境変数から読み込む基盤を用意する。秘密情報はリポジトリに含めない。

## タスク
- [ ] `src/` ディレクトリを作成
- [ ] `.env` を読み込む設定ローダを実装（`python-dotenv`）
- [ ] 既定値の補完と検証（`TOGGLE_MODE_*` は home/away/disarmed のみ、UID 正規化）
- [ ] `.env.example` と実装のキーを一致させる

## 受け入れ基準
- `.env` の値でコード変更なしに挙動が変わる
- 不正なモード値・欠落時に分かりやすいエラーで停止する
- `.env` 未コミット（.gitignore 済み）を確認

## 関連
- requirements: NFR-1, NFR-2
