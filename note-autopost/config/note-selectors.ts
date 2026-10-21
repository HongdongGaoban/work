/**
 * note エディタの DOM セレクタ集約（DESIGN.md §7.3）。
 *
 * UI 変更時はこのファイルだけ直せばよいようにする。
 * テキスト・ロール指定を優先し、壊れやすいクラス名は避ける。
 *
 * ⚠️ 未検証: ここにある値はログイン後のエディタ画面を実際に確認する前の仮値。
 *    `npx playwright codegen --load-storage=.auth/note.state.json https://editor.note.com/new`
 *    で実画面を確認し、合わない箇所を修正すること。
 */
import type { Locator, Page } from "playwright";

export const noteUrls = {
  login: "https://note.com/login",
  /** 新規記事作成画面。開くと下書きが 1 件作られる可能性があるので session チェックには使わない */
  newNote: "https://editor.note.com/new",
  /** ログインしていないとログイン画面へリダイレクトされるページ */
  sessionProbe: "https://note.com/settings/account",
};

/** 未ログイン時にリダイレクトされる URL の判定 */
export const isLoginUrl = (url: string): boolean => /note\.com\/login/.test(url);

/** 下書き保存後のエディタ URL（ここから下書き URL を得る） */
export const draftUrlPattern = /editor\.note\.com\/notes\/[A-Za-z0-9]+\/edit/;

export const selectors = {
  /** タイトル入力欄 */
  title: (page: Page): Locator => page.getByPlaceholder("記事タイトル"),

  /** 本文エディタ（contenteditable） */
  body: (page: Page): Locator => page.locator('[contenteditable="true"][role="textbox"]').first(),

  /** 本文中の画像挿入: 「＋」メニュー → 「画像」 */
  insertMenuButton: (page: Page): Locator => page.getByRole("button", { name: "メニューを開く", exact: true }),
  insertImageItem: (page: Page): Locator => page.getByRole("button", { name: "画像", exact: true }),

  /** アイキャッチ画像の追加ボタン */
  eyecatchButton: (page: Page): Locator => page.getByRole("button", { name: /画像を追加|見出し画像/ }),

  /** 画像トリミング等のダイアログが出た場合の確定ボタン */
  imageDialogConfirm: (page: Page): Locator => page.getByRole("button", { name: /^(保存|完了|OK)$/ }),

  /** 下書き保存ボタン */
  saveDraft: (page: Page): Locator => page.getByRole("button", { name: "下書き保存", exact: true }),

  /** 保存完了の表示（トースト等） */
  savedIndicator: (page: Page): Locator => page.getByText(/保存しました|下書きを保存/),
};

/**
 * クリックしてはいけないボタンのラベル（公開系）。
 * src/note/guard.ts の safeClick がクリック直前にラベルを照合して弾く。
 */
export const forbiddenLabelPatterns: RegExp[] = [
  /公開/, // 「公開に進む」「公開する」「投稿を公開」等
  /投稿する/,
  /publish/i,
  /予約/, // 予約投稿
  /有料/, // 有料設定
];
