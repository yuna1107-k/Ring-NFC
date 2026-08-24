#!/usr/bin/env bash
#
# docs/issues/*.md の front matter (title/labels) と本文を読み取り、
# gh CLI で GitHub Issue をまとめて作成します。
#
# 前提:
#   - gh がインストール済み            (https://cli.github.com/)
#   - gh auth login 済み（Issues 書き込み権限）
#   - カレントがリポジトリ内、または REPO を指定
#
# 使い方:
#   ./scripts/create_issues.sh              # 実際に作成
#   DRY_RUN=1 ./scripts/create_issues.sh    # 内容確認のみ（作成しない）
#   REPO=yuna1107-k/Ring-NFC ./scripts/create_issues.sh
#
set -euo pipefail

REPO="${REPO:-yuna1107-k/Ring-NFC}"
DRY_RUN="${DRY_RUN:-0}"
ISSUE_DIR="$(cd "$(dirname "$0")/.." && pwd)/docs/issues"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh が見つかりません。https://cli.github.com/ を参照してインストールしてください。" >&2
  exit 1
fi

shopt -s nullglob
for f in "$ISSUE_DIR"/*.md; do
  # front matter から title / labels を抽出
  title=$(sed -n 's/^title:[[:space:]]*"\{0,1\}\(.*\)/\1/p' "$f" | head -1 | sed 's/"$//')
  labels=$(sed -n 's/^labels:[[:space:]]*\[\(.*\)\].*/\1/p' "$f" | head -1 \
            | tr -d '"' | tr -d ' ')
  # front matter (先頭の --- ... ---) を除いた本文
  body=$(awk 'BEGIN{fm=0} /^---[[:space:]]*$/{fm++; next} fm>=2{print}' "$f")

  if [[ -z "$title" ]]; then
    echo "スキップ (title 無し): $f" >&2
    continue
  fi

  echo "----------------------------------------"
  echo "Title : $title"
  echo "Labels: ${labels:-（なし）}"
  echo "File  : $(basename "$f")"

  label_args=()
  if [[ -n "$labels" ]]; then
    IFS=',' read -ra arr <<< "$labels"
    for l in "${arr[@]}"; do label_args+=(--label "$l"); done
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "(DRY_RUN) gh issue create --repo $REPO --title \"$title\" ${label_args[*]}"
    continue
  fi

  # ラベルが未作成でも失敗しないよう、まず作成を試みる
  if [[ -n "$labels" ]]; then
    IFS=',' read -ra arr <<< "$labels"
    for l in "${arr[@]}"; do
      gh label create "$l" --repo "$REPO" >/dev/null 2>&1 || true
    done
  fi

  printf '%s\n' "$body" | gh issue create \
    --repo "$REPO" \
    --title "$title" \
    "${label_args[@]}" \
    --body-file -
done

echo "----------------------------------------"
echo "完了しました。"
