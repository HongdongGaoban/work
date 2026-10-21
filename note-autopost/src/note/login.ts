/**
 * 手動ログイン → storageState 保存（ローカル専用。DESIGN.md §7.1）。
 * メールアドレス・パスワードはコードで扱わない。ブラウザで人がログインする。
 */
import { chmod, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { createInterface } from "node:readline/promises";
import { chromium } from "playwright";
import { isLoginUrl, noteUrls } from "../../config/note-selectors.ts";
import { DEFAULT_STATE_PATH } from "./session.ts";

export async function login(outFile = process.env.NOTE_STORAGE_STATE_PATH ?? DEFAULT_STATE_PATH): Promise<void> {
  if (process.env.CI) throw new Error("login はローカル専用です（CI では実行できません）");

  const browser = await chromium.launch({ headless: false });
  try {
    const context = await browser.newContext({ locale: "ja-JP" });
    const page = await context.newPage();
    await page.goto(noteUrls.login);

    const rl = createInterface({ input: process.stdin, output: process.stdout });
    await rl.question("ブラウザで note にログインし、完了したら Enter を押してください: ");
    rl.close();

    if (isLoginUrl(page.url())) {
      throw new Error("まだログイン画面のままです。ログインを完了してからやり直してください");
    }

    const state = await context.storageState();
    await mkdir(path.dirname(outFile), { recursive: true });
    await writeFile(outFile, JSON.stringify(state, null, 2), { encoding: "utf8", mode: 0o600 });
    await chmod(outFile, 0o600);
    console.log(`storageState を保存しました: ${outFile}`);
    console.log("GitHub Actions で使う場合は、このファイルの中身を Secret NOTE_STORAGE_STATE_JSON に登録してください");
  } finally {
    await browser.close();
  }
}
