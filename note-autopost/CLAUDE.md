# CLAUDE.md — note-autopost 作業ルール

設計は `DESIGN.md` を正とする。迷ったら DESIGN.md を読み直すこと。

## 進め方
- 実装は Phase 1 から順に進め、各 Phase の完了条件（DESIGN.md §9）を満たしてから次へ進む
- 現在の状態: **Phase 1 実装済み・実機検証待ち**（`config/note-selectors.ts` のセレクタは未検証の仮値）

## 禁止事項
- note への実アクセスを伴う操作は必ず下書き保存まで。公開系の操作は実装しない
  - クリックは必ず `src/note/guard.ts` の `safeClick` 経由で行う（公開系ボタンを弾くガード）
- note の非公式 API（内部 API の直叩き）は使わない。投稿はブラウザ操作のみ
- 秘密情報（API キー、storageState）をリポジトリにコミットしない（`.gitignore` に `*.state.json`, `.env`, `.auth/`）
- メールアドレス・パスワードをコードにも Secret にも持たない。ログインは常に人が行う

## note の DOM
- セレクタはすべて `config/note-selectors.ts` に集約する。テキスト・ロール指定を優先し、クラス名は避ける
- UI を調べるときは `npx playwright codegen --load-storage=.auth/note.state.json https://editor.note.com/new` で実画面を確認してから直す

## コマンド
- `npm run login` — ブラウザを開き手動ログイン → `.auth/note.state.json` 保存（ローカル専用）
- `npm run session-check` — ログイン状態の確認
- `npm run draft -- <article.md...> [--dry-run] [--all]` — note に下書き保存
- `npm run convert -- <article.md>` — 変換結果の HTML を標準出力へ
- `npm test` / `npm run typecheck`

## テスト
- `convert.ts` と `checks/` はユニットテストを書く（`tests/`、node:test + tsx）
- publisher は `--dry-run` と、テスト用の下書き 1 件での手動確認で検証する
