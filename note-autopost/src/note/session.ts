/**
 * storageState の読込・有効性チェック（DESIGN.md §7.1）。
 *
 * 読込元の優先順:
 *   1. 環境変数 NOTE_STORAGE_STATE_JSON（GitHub Actions の Secret。JSON 文字列そのもの）
 *   2. 環境変数 NOTE_STORAGE_STATE_PATH のファイル
 *   3. .auth/note.state.json（npm run login の保存先）
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { chromium, type Browser, type BrowserContext } from "playwright";
import { isLoginUrl, noteUrls } from "../../config/note-selectors.ts";

export const DEFAULT_STATE_PATH = path.resolve(".auth/note.state.json");

type StorageState = Exclude<Parameters<Browser["newContext"]>[0], undefined>["storageState"];

export class SessionError extends Error {}

export function loadStorageState(): Exclude<StorageState, string | undefined> {
  const inline = process.env.NOTE_STORAGE_STATE_JSON;
  if (inline && inline.trim() !== "") {
    try {
      return JSON.parse(inline);
    } catch {
      throw new SessionError("NOTE_STORAGE_STATE_JSON が JSON として読めません");
    }
  }
  const file = process.env.NOTE_STORAGE_STATE_PATH ?? DEFAULT_STATE_PATH;
  if (!existsSync(file)) {
    throw new SessionError(`storageState がありません: ${file}（npm run login でログインしてください）`);
  }
  return JSON.parse(readFileSync(file, "utf8"));
}

export async function openContext(options: { headless?: boolean } = {}): Promise<{
  browser: Browser;
  context: BrowserContext;
}> {
  const storageState = loadStorageState();
  const browser = await chromium.launch({ headless: options.headless ?? true });
  const context = await browser.newContext({ storageState, locale: "ja-JP", viewport: { width: 1280, height: 900 } });
  return { browser, context };
}

/** ログイン状態なら true。未ログインならログイン画面へリダイレクトされる前提 */
export async function isLoggedIn(context: BrowserContext): Promise<boolean> {
  const page = await context.newPage();
  try {
    await page.goto(noteUrls.sessionProbe, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
    return !isLoginUrl(page.url());
  } finally {
    await page.close();
  }
}

/** ログイン切れなら SessionError を投げる */
export async function assertLoggedIn(context: BrowserContext): Promise<void> {
  if (!(await isLoggedIn(context))) {
    throw new SessionError("note のログインが切れています。npm run login で再ログインし、storageState を更新してください");
  }
}

export async function checkSession(): Promise<boolean> {
  const { browser, context } = await openContext();
  try {
    return await isLoggedIn(context);
  } finally {
    await browser.close();
  }
}
