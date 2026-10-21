/**
 * note への下書き保存（DESIGN.md §7.2, §7.3）。
 *
 * - 公開系の操作は一切しない。クリックはすべて safeClick 経由
 * - note_draft_url が記録済み、または status が generated 以外の記事はスキップ
 * - 1 回の実行で下書き保存する記事数に上限（maxPerRun）、記事ごとに interval を空ける
 * - 失敗時はスクリーンショットと HTML を outDir/failures/ に保存
 */
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { setTimeout as sleep } from "node:timers/promises";
import path from "node:path";
import type { BrowserContext, Locator, Page } from "playwright";
import { draftUrlPattern, noteUrls, selectors } from "../../config/note-selectors.ts";
import { loadArticle, updateArticleMeta, type Article } from "../article.ts";
import { convert, imagePlaceholder, type ConvertResult } from "./convert.ts";
import { safeClick } from "./guard.ts";
import { assertLoggedIn, openContext } from "./session.ts";

export interface PublishOptions {
  dryRun?: boolean;
  /** 1 回の実行で下書き保存する上限（DESIGN.md §7.3 初期値 3） */
  maxPerRun?: number;
  /** 記事間の待機ミリ秒（30 秒未満は 30 秒に切り上げ） */
  intervalMs?: number;
  /** dry-run の HTML と失敗時のスクショの出力先 */
  outDir?: string;
  headless?: boolean;
  /** 各操作のタイムアウト */
  timeoutMs?: number;
  /** 既存のブラウザコンテキストを使う（テスト用。指定時は storageState を読まない） */
  context?: BrowserContext;
}

export type PublishResult =
  | { file: string; outcome: "drafted"; url: string }
  | { file: string; outcome: "dry-run"; htmlFile: string }
  | { file: string; outcome: "skipped"; reason: string }
  | { file: string; outcome: "failed"; error: string; evidence?: string[] };

const MIN_INTERVAL_MS = 30_000;

interface Prepared {
  article: Article;
  converted: ConvertResult;
  /** images[i] の絶対パス */
  imagePaths: string[];
  eyecatchPath: string | null;
}

/** 変換と画像パスの解決。note にはアクセスしない */
export function prepare(article: Article): Prepared {
  const converted = convert(article.body);
  const resolve = (src: string) => {
    const p = path.resolve(article.dir, src);
    if (!existsSync(p)) throw new Error(`画像が見つかりません: ${src}`);
    return p;
  };
  return {
    article,
    converted,
    imagePaths: converted.images.map((img) => resolve(img.src)),
    eyecatchPath: article.meta.eyecatch ? resolve(article.meta.eyecatch) : null,
  };
}

function skipReason(article: Article): string | null {
  if (article.meta.note_draft_url) return `下書き保存済み: ${article.meta.note_draft_url}`;
  if (article.meta.status !== "generated") return `status が ${article.meta.status}`;
  return null;
}

export async function publishDrafts(files: string[], options: PublishOptions = {}): Promise<PublishResult[]> {
  const outDir = path.resolve(options.outDir ?? "out");
  const maxPerRun = options.maxPerRun ?? 3;
  const intervalMs = Math.max(options.intervalMs ?? 45_000, MIN_INTERVAL_MS);
  const timeoutMs = options.timeoutMs ?? 30_000;

  const results: PublishResult[] = [];
  const queue: Prepared[] = [];

  for (const file of files) {
    try {
      const article = await loadArticle(file);
      const reason = skipReason(article);
      if (reason) {
        results.push({ file, outcome: "skipped", reason });
        continue;
      }
      if (queue.length >= maxPerRun) {
        results.push({ file, outcome: "skipped", reason: `1 回の上限 ${maxPerRun} 件に達したため次回に回します` });
        continue;
      }
      queue.push(prepare(article));
    } catch (e) {
      results.push({ file, outcome: "failed", error: errorMessage(e) });
    }
  }

  if (options.dryRun) {
    for (const p of queue) results.push(await writeDryRun(p, outDir));
    return results;
  }
  if (queue.length === 0) return results;

  const { browser, context } = options.context
    ? { browser: null, context: options.context }
    : await openContext({ headless: options.headless });
  try {
    await assertLoggedIn(context);
    for (const [i, p] of queue.entries()) {
      if (i > 0) await sleep(intervalMs);
      results.push(await draftOne(context, p, outDir, timeoutMs));
    }
  } finally {
    await browser?.close();
  }
  return results;
}

async function writeDryRun(p: Prepared, outDir: string): Promise<PublishResult> {
  const dir = path.join(outDir, "dry-run", p.article.meta.topic_id);
  await mkdir(dir, { recursive: true });
  const htmlFile = path.join(dir, "body.html");
  await writeFile(htmlFile, p.converted.html, "utf8");
  await writeFile(
    path.join(dir, "plan.json"),
    JSON.stringify(
      {
        title: p.article.meta.title,
        tags: p.article.meta.tags,
        eyecatch: p.eyecatchPath,
        images: p.converted.images.map((img, i) => ({ ...img, path: p.imagePaths[i] })),
      },
      null,
      2,
    ),
    "utf8",
  );
  return { file: p.article.file, outcome: "dry-run", htmlFile };
}

async function draftOne(context: BrowserContext, p: Prepared, outDir: string, timeout: number): Promise<PublishResult> {
  const page = await context.newPage();
  page.setDefaultTimeout(timeout);
  try {
    await page.goto(noteUrls.newNote, { waitUntil: "domcontentloaded" });

    // タイトル
    const title = selectors.title(page);
    await title.waitFor({ state: "visible" });
    await title.fill(p.article.meta.title);

    // 本文（HTML を paste イベントで流し込む）
    const body = selectors.body(page);
    await safeClick(body);
    await pasteHtml(body, p.converted.html);

    // 本文画像（プレースホルダ段落を空にして、その位置で画像を挿入）
    for (const [i, file] of p.imagePaths.entries()) {
      await insertImageAt(page, body, imagePlaceholder(i), file);
    }
    const leftover = await body.innerText();
    if (leftover.includes("[[IMAGE:")) throw new Error("画像プレースホルダが本文に残っています");

    // アイキャッチ
    if (p.eyecatchPath) await uploadVia(page, selectors.eyecatchButton(page), p.eyecatchPath);

    // 下書き保存（公開系には触れない）
    await safeClick(selectors.saveDraft(page));
    await Promise.race([
      selectors.savedIndicator(page).first().waitFor({ state: "visible" }),
      page.waitForURL(draftUrlPattern),
    ]);
    if (!draftUrlPattern.test(page.url())) await page.waitForURL(draftUrlPattern);
    const url = page.url();

    await updateArticleMeta(p.article, {
      note_draft_url: url,
      status: "drafted",
      drafted_at: new Date().toISOString(),
    });
    return { file: p.article.file, outcome: "drafted", url };
  } catch (e) {
    const evidence = await saveEvidence(page, outDir, p.article.meta.topic_id);
    return { file: p.article.file, outcome: "failed", error: errorMessage(e), evidence };
  } finally {
    await page.close();
  }
}

/** contenteditable に text/html の paste イベントを送る（クリップボード権限不要） */
async function pasteHtml(body: Locator, html: string): Promise<void> {
  await body.evaluate((el, html) => {
    const plain = new DOMParser().parseFromString(html, "text/html").body.innerText;
    const data = new DataTransfer();
    data.setData("text/html", html);
    data.setData("text/plain", plain);
    el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
  }, html);
  // エディタが反映するまで待つ
  await body.page().waitForFunction((el) => (el as HTMLElement).innerText.trim().length > 0, await body.elementHandle());
}

async function insertImageAt(page: Page, body: Locator, placeholder: string, file: string): Promise<void> {
  const marker = body.getByText(placeholder, { exact: true });
  await safeClick(marker);
  // プレースホルダ文字列を消して空段落にする
  await page.keyboard.press("End");
  for (let i = 0; i < placeholder.length; i++) await page.keyboard.press("Backspace");

  const before = await body.locator("img").count();
  await safeClick(selectors.insertMenuButton(page));
  await uploadVia(page, selectors.insertImageItem(page), file);
  await page.waitForFunction(
    ([el, n]) => (el as HTMLElement).querySelectorAll("img").length > (n as number),
    [await body.elementHandle(), before] as const,
  );
}

/** ボタンを押してファイル選択ダイアログに file を渡す。確認ダイアログが出たら確定する */
async function uploadVia(page: Page, button: Locator, file: string): Promise<void> {
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), safeClick(button)]);
  await chooser.setFiles(file);
  const confirm = selectors.imageDialogConfirm(page);
  if (await confirm.first().isVisible({ timeout: 3_000 }).catch(() => false)) {
    await safeClick(confirm);
  }
}

async function saveEvidence(page: Page, outDir: string, id: string): Promise<string[]> {
  const dir = path.join(outDir, "failures");
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const base = path.join(dir, `${id}-${stamp}`);
  const saved: string[] = [];
  try {
    await mkdir(dir, { recursive: true });
    await page.screenshot({ path: `${base}.png`, fullPage: true });
    saved.push(`${base}.png`);
    await writeFile(`${base}.html`, await page.content(), "utf8");
    saved.push(`${base}.html`);
  } catch {
    // ページが閉じている等。証跡が取れなくても元のエラーを優先する
  }
  return saved;
}

function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
