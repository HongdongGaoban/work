# note 記事自動生成・投稿システム 設計書

Claude Code への実装引き継ぎ用。リポジトリ直下に `DESIGN.md` として置き、実装時に参照させる想定。

---

## 1. 目的とスコープ

テーマを登録するだけで、リサーチ → 執筆 → 品質チェック → note への**下書き保存**までを自動で行う。
**公開（publish）は人が note 上で行う**。システムは公開ボタンを押さない。

### スコープ外
- note 上での公開操作、有料記事の価格・有料ライン設定
- スキ・コメント・フォローなどのインタラクション
- 非公式 API（内部 API の直叩き）の利用。投稿はブラウザ操作（Playwright）のみで行う

---

## 2. 前提（仮置き。変更可能な設定値として実装する）

| 項目 | 仮の値 | 設定場所 |
|---|---|---|
| 言語・ランタイム | TypeScript / Node.js 22+ | — |
| 実行基盤 | GitHub Actions（定期 + 手動実行） | `.github/workflows/` |
| 投稿頻度 | 週1回（月曜 7:00 JST）＋ 手動 | `generate.yml` の cron |
| テーマの出し方 | `topics.yaml` に手動登録（RSS 自動収集は Phase 4） | `topics.yaml` |
| 記事ジャンル・文体 | `config/style.md` と過去記事サンプルで指定 | `config/` |
| LLM | Anthropic API（モデル名は設定値） | `config/models.yaml` |
| 通知 | GitHub Issue 作成（失敗時）＋ PR 作成（成功時） | — |

---

## 3. 全体フロー

```
topics.yaml（テーマ登録）
   │
   ▼  [generate ワークフロー：cron / 手動]
┌──────────────────────────────────────────┐
│ 1. pick      未処理テーマを1件選ぶ       │
│ 2. research  Web検索で情報・出典を収集   │
│ 3. outline   構成案を作る                │
│ 4. write     本文を書く（Markdown）      │
│ 5. review    別エージェントで検証・修正  │
│ 6. package   articles/<id>/ に保存       │
└──────────────────────────────────────────┘
   │  記事を含む Pull Request を自動作成
   ▼
人が PR 上でレビュー・修正 → マージ
   │
   ▼  [draft ワークフロー：main への push で起動]
┌──────────────────────────────────────────┐
│ 7. publish-draft  Playwright で note に   │
│                   下書き保存              │
│ 8. record         note の下書きURLを記録 │
└──────────────────────────────────────────┘
   │
   ▼
人が note で最終確認して「公開」
```

**ポイント：人の確認を2回入れる**
- PR レビュー（内容・事実関係）
- note 上の最終確認（見た目・画像・タグ）

---

## 4. ディレクトリ構成

```
note-autopost/
├── DESIGN.md                  # この設計書
├── CLAUDE.md                  # Claude Code 向けの作業ルール
├── topics.yaml                # テーマ一覧（入力）
├── config/
│   ├── models.yaml            # 役割ごとのモデル名・max_tokens
│   ├── style.md               # 文体・トーン・NG表現
│   ├── samples/               # 文体見本となる過去記事（2〜5本）
│   └── note-selectors.ts      # note エディタの DOM セレクタを集約
├── prompts/
│   ├── research.md
│   ├── outline.md
│   ├── write.md
│   └── review.md
├── src/
│   ├── cli.ts                 # エントリポイント（サブコマンド）
│   ├── pipeline/
│   │   ├── pick.ts
│   │   ├── research.ts
│   │   ├── outline.ts
│   │   ├── write.ts
│   │   ├── review.ts
│   │   └── package.ts
│   ├── llm/
│   │   └── client.ts          # Anthropic SDK ラッパ（リトライ・トークン記録）
│   ├── note/
│   │   ├── login.ts           # 手動ログイン → storageState 保存（ローカル専用）
│   │   ├── session.ts         # storageState の読込・有効性チェック
│   │   ├── publisher.ts       # 下書き保存の本体
│   │   └── convert.ts         # Markdown → note 貼り付け用 HTML
│   ├── checks/                # 機械的チェック（文字数・リンク・NGワード）
│   └── notify.ts              # Issue 作成など
├── articles/
│   └── 2026-10-26-<slug>/
│       ├── article.md         # frontmatter + 本文
│       ├── research.json      # 収集した情報と出典
│       ├── review.json        # レビュー結果
│       └── images/            # 本文・アイキャッチ画像（任意）
├── tests/
└── .github/workflows/
    ├── generate.yml
    ├── draft.yml
    └── session-check.yml
```

---

## 5. データ仕様

### 5.1 topics.yaml

```yaml
- id: pmp-study-plan            # 一意。記事ディレクトリ名に使う
  theme: 社会人がPMPを3か月で取るための学習計画
  audience: IT系PM、資格勉強を始めたい人
  message: 毎日の小さな積み上げと模試の回し方が鍵
  cta: 自分の学習計画を書き出してみる
  tags: [PMP, 資格, プロジェクトマネジメント]
  length: 3000                  # 目安文字数（任意）
  status: pending               # pending / generated / drafted / published / skipped
  priority: 1                   # 小さいほど先に処理（任意）
```

`pick` は `status: pending` のうち `priority` 昇順で1件選ぶ。処理後に status を更新し、PR に含める。

### 5.2 article.md（frontmatter）

```markdown
---
topic_id: pmp-study-plan
title: 社会人がPMPを3か月で取るための学習計画
tags: [PMP, 資格, プロジェクトマネジメント]
eyecatch: images/eyecatch.png   # 任意
status: generated               # generated → drafted → published
note_draft_url: null            # draft 後に記録
generated_at: 2026-10-26T07:05:00+09:00
models: { write: <model>, review: <model> }
sources:
  - title: ...
    url: ...
---

本文（Markdown）
```

### 5.3 使ってよい Markdown 要素

note エディタで表現できるものに限定する（`convert.ts` もこれだけ対応すればよい）。

- 見出し：`##`（大見出し）、`###`（小見出し）のみ。`#` はタイトル扱いで本文に使わない
- 段落、太字、リンク
- 箇条書き・番号付きリスト（入れ子なし）
- 引用、コードブロック、区切り線
- 画像（`![](images/xxx.png)`）
- 表は使わない（note 非対応のため、箇条書きに置き換える）

`write` のプロンプトと `checks` の両方でこの制約を守らせる。

---

## 6. 生成パイプライン（各ステージ）

すべて `src/llm/client.ts` 経由で呼ぶ。各ステージの入出力は JSON で保存し、途中から再実行できるようにする（`--from write` など）。

| ステージ | 入力 | 出力 | 内容 |
|---|---|---|---|
| research | topic | `research.json` | Web検索ツール付きで呼び出し、要点・数値・出典URLを構造化して返す。出典のない主張は除外 |
| outline | topic + research | `outline.json` | 見出し構成（h2/h3）と各節の要点。読者・CTA に沿っているか |
| write | outline + research + style + samples | `article.md` | 本文生成。出典は文中リンクか末尾「参考」節に |
| review | article + research | `review.json` + 修正版 | **write とは別プロンプト・別呼び出し**で実施（自己採点にしない）。下記観点で問題点を列挙し、修正版を出す |

### review の観点
- 事実関係：research にない数値・固有名詞が出ていないか
- 出典：主張と出典URLが対応しているか
- 構成：読者・メッセージ・CTA に沿っているか、冗長でないか
- 文体：`style.md` に合っているか、AIっぽい定型表現（「いかがでしたか」等）がないか
- 形式：5.3 の Markdown 制約を守っているか

review で重大な問題（事実誤り等）が残った場合は `status: needs_human` にして PR に明記し、自動では進めない。

### 機械的チェック（`checks/`、LLM を使わない）
- 文字数が目安の ±30% 以内
- 使用禁止の Markdown 要素がない
- リンク切れがない（HEAD リクエスト）
- `style.md` の NG ワードがない
- タイトル 40 字以内程度、タグ 1〜5 個

---

## 7. note 投稿モジュール（`src/note/`）

### 7.1 認証
- `npm run login`（ローカル専用）：Playwright でブラウザを開き、人が手動ログイン → `storageState` を JSON で保存
- GitHub Actions では Secret `NOTE_STORAGE_STATE_JSON` から復元
- **メールアドレス・パスワードはコードにも Secret にも持たない**（ログインは常に人が行う）
- `session.ts`：投稿前にログイン状態を確認し、切れていたら即失敗 → 再ログインを促す Issue を作成

### 7.2 下書き保存の手順（`publisher.ts`）
1. storageState を読み込んでブラウザ起動（headless）
2. 新規記事作成画面を開く
3. タイトルを入力
4. 本文を挿入：`convert.ts` で Markdown → HTML に変換し、クリップボード経由で貼り付ける（要検証。貼り付けで崩れる要素があれば、要素ごとにエディタ操作で入力する方式にフォールバック）
5. 本文画像：プレースホルダ位置で画像アップロード操作
6. アイキャッチ画像をアップロード（任意）
7. 下書き保存（**「公開」系のボタンには触れない**）
8. 下書きの URL を取得して返す

### 7.3 実装ルール
- DOM セレクタは `config/note-selectors.ts` に集約し、UI 変更時はそこだけ直せばよい形にする。テキストやロールでの指定を優先し、壊れやすいクラス名は避ける
- 各操作に待機とタイムアウトを設定し、失敗時はスクリーンショットと HTML を保存（Actions の artifact に上げる）
- 公開ボタンを誤って押さないよう、公開系セレクタへのクリックをコード上で禁止するガードを入れる
- 連続投稿時は 1 記事ごとに数十秒以上の間隔を空け、1 回の実行で投稿する記事数に上限を設ける（初期値 3）
- `--dry-run`：note にアクセスせず、変換結果の HTML を出力するだけ
- 同じ記事を二重に下書き保存しないよう、`note_draft_url` が記録済みならスキップ

---

## 8. GitHub Actions

### generate.yml
- トリガー：`schedule`（週1）＋ `workflow_dispatch`（入力：topic_id 任意、dry_run）
- 処理：pick → research → outline → write → review → checks → package
- 結果を新ブランチに commit し、PR を作成。PR 本文に review の指摘事項・出典一覧・チェック結果を載せる

### draft.yml
- トリガー：`articles/**` を含む main への push（＝PR マージ）＋ `workflow_dispatch`
- 処理：`status: generated` かつ未下書きの記事を publisher で下書き保存 → `note_draft_url` と `status: drafted` を commit
- 失敗時：スクショを artifact に保存し、Issue を作成

### session-check.yml
- 週1回、ログイン状態だけを確認。切れていれば Issue で再ログインを依頼

### Secrets
- `ANTHROPIC_API_KEY`
- `NOTE_STORAGE_STATE_JSON`

---

## 9. 実装フェーズ

| Phase | 内容 | 完了条件 |
|---|---|---|
| 1 | note 投稿モジュール（login / session / convert / publisher）をローカルで | 手書きの article.md が見出し・リスト・画像込みで正しく下書き保存される |
| 2 | 生成パイプライン（research〜review、checks）をローカル CLI で | `npm run generate -- --topic <id>` で article.md が出力される |
| 3 | GitHub Actions 化（generate → PR → draft） | 定期実行から PR 作成、マージで下書き保存まで通る |
| 4 | 拡張（RSS からのテーマ自動提案、アイキャッチ生成、コスト集計） | 必要に応じて |

Phase 1 を最初にやる理由：note の UI 操作が最も不確実で壊れやすく、ここが成り立たないと全体が成立しないため。

---

## 10. 未決事項（実装前に決める）

- 記事ジャンルと文体見本（`config/samples/` に入れる過去記事）
- テーマを手動登録だけにするか、RSS 等からの自動提案も入れるか
- 投稿頻度
- アイキャッチ画像の扱い（毎回自分で用意 / テンプレート画像にタイトル文字入れ / なし）
- 1 記事あたりの API コスト上限

---

## 11. Claude Code への指示メモ（CLAUDE.md に転記）

- 実装は Phase 1 から順に進め、各 Phase の完了条件を満たしてから次へ進む
- note への実アクセスを伴う操作は必ず下書き保存まで。公開系の操作は実装しない
- note の非公式 API は使わない
- 秘密情報（API キー、storageState）をリポジトリにコミットしない。`.gitignore` に `*.state.json`、`.env` を入れる
- note の DOM はこちらで事前に分からないため、Phase 1 の最初に実際のエディタ画面を Playwright（`codegen` やスクリーンショット）で調べてから `note-selectors.ts` を作る
- テスト：`convert.ts` と `checks/` はユニットテストを書く。publisher は `--dry-run` と、テスト用の下書き 1 件での手動確認で検証する
