# note-autopost

テーマ登録 → リサーチ → 執筆 → チェック → note への**下書き保存**までを自動化する（公開は人が行う）。
設計は [DESIGN.md](DESIGN.md)、作業ルールは [CLAUDE.md](CLAUDE.md)。

## 現在の状態: Phase 1（note 投稿モジュール）

実装済み: `login` / `session-check` / `convert` / `draft`（publisher）と、変換・ガード・模擬エディタでのテスト。
**`config/note-selectors.ts` のセレクタは実画面で未検証の仮値**なので、以下の手順で実機確認が必要。

### 実機確認の手順（ローカル）

```sh
cd note-autopost
npm install
npx playwright install chromium

# 1. 手動ログイン → .auth/note.state.json に保存（コミットされない）
npm run login

# 2. ログイン状態の確認
npm run session-check

# 3. 実際のエディタ画面を見てセレクタを確認・修正（DESIGN.md §11）
npx playwright codegen --load-storage=.auth/note.state.json https://editor.note.com/new
#    → 合わない箇所を config/note-selectors.ts で直す。codegen で開いた画面の下書きは手動で削除

# 4. 変換結果だけ確認（note にはアクセスしない）
npm run draft -- --dry-run articles/2026-10-26-phase1-sample/article.md

# 5. テスト用記事を 1 件下書き保存（--headed でブラウザを表示）
npm run draft -- --headed articles/2026-10-26-phase1-sample/article.md
```

5 が成功すると `article.md` に `note_draft_url` と `status: drafted` が書き込まれる。
note 上で見出し・リスト・画像・アイキャッチが正しく入っているか確認し、テスト用の下書きは削除する。
再実行する場合は `note_draft_url: null` / `status: generated` に戻す。

失敗時は `out/failures/` にスクリーンショットと HTML が保存される。

### メモ
- タグは note の「公開に進む」画面でしか設定できないため、システムでは入力しない（公開時に人が設定）
- 本文は `text/html` の paste イベントで流し込む。崩れる要素があれば要素ごとの入力にフォールバックを検討（DESIGN.md §7.2-4）
