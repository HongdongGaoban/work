/**
 * publisher の流れを模擬エディタで確認する（実際の note にはアクセスしない）。
 * 模擬エディタは config/note-selectors.ts の仮セレクタに合わせたもので、
 * 実際の note の DOM と一致することは保証しない。実機確認は別途手動で行う。
 */
import assert from "node:assert/strict";
import { cp, mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { chromium, type Browser } from "playwright";
import { parseArticle } from "../src/article.ts";
import { publishDrafts } from "../src/note/publisher.ts";

const SAMPLE = path.resolve("articles/2026-10-26-phase1-sample");

const mockEditor = `<!doctype html><meta charset="utf-8">
<textarea placeholder="記事タイトル"></textarea>
<button aria-label="画像を追加" id="eyecatch">見出し画像</button><img id="eyecatch-img" hidden>
<div contenteditable="true" role="textbox" id="body"></div>
<button aria-label="メニューを開く">＋</button><button id="img">画像</button>
<button id="publish">公開に進む</button><button id="save">下書き保存</button>
<input type="file" id="file" hidden><div id="toast"></div>
<script>
  window.publishClicked = false;
  const body = document.getElementById("body");
  body.addEventListener("paste", (e) => { e.preventDefault(); body.innerHTML = e.clipboardData.getData("text/html"); });
  let target = null;
  const file = document.getElementById("file");
  document.getElementById("img").onclick = () => {
    const node = getSelection().anchorNode;
    target = (node && node.nodeType === 3 ? node.parentElement : node).closest("#body > *");
    file.click();
  };
  document.getElementById("eyecatch").onclick = () => { target = "eyecatch"; file.click(); };
  file.onchange = () => {
    if (target === "eyecatch") { document.getElementById("eyecatch-img").hidden = false; return; }
    const img = document.createElement("img"); img.src = "data:,"; target.replaceWith(img);
  };
  document.getElementById("publish").onclick = () => { window.publishClicked = true; };
  document.getElementById("save").onclick = () => {
    fetch("/__saved", { method: "POST", body: JSON.stringify({
      title: document.querySelector("textarea").value,
      body: body.innerHTML,
      eyecatch: !document.getElementById("eyecatch-img").hidden,
      publishClicked: window.publishClicked,
    }) });
    history.pushState({}, "", "/notes/nabc123/edit");
    document.getElementById("toast").textContent = "保存しました";
  };
</script>`;

interface Saved {
  title: string;
  body: string;
  eyecatch: boolean;
  publishClicked: boolean;
}

let browser: Browser;
before(async () => {
  browser = await chromium.launch();
});
after(async () => {
  await browser.close();
});

async function setup() {
  const dir = path.join(await mkdtemp(path.join(tmpdir(), "publisher-")), "article");
  await cp(SAMPLE, dir, { recursive: true });
  const context = await browser.newContext();
  await context.route("https://note.com/settings/account", (r) => r.fulfill({ contentType: "text/html", body: "ok" }));
  await context.route("https://editor.note.com/new", (r) => r.fulfill({ contentType: "text/html", body: mockEditor }));
  const saved: Saved[] = [];
  await context.route("https://editor.note.com/__saved", (r) => {
    saved.push(JSON.parse(r.request().postData() ?? "{}"));
    return r.fulfill({ status: 204 });
  });
  return { file: path.join(dir, "article.md"), context, saved };
}

test("下書き保存して URL と status を記録する", async () => {
  const { file, context, saved } = await setup();
  const results = await publishDrafts([file], { context, outDir: path.dirname(file), timeoutMs: 5_000 });
  assert.equal(results.length, 1);
  assert.equal(results[0]!.outcome, "drafted", JSON.stringify(results[0]));

  const meta = parseArticle(await readFile(file, "utf8"), file).meta;
  assert.equal(meta.status, "drafted");
  assert.equal(meta.note_draft_url, "https://editor.note.com/notes/nabc123/edit");

  assert.equal(saved.length, 1);
  const s = saved[0]!;
  assert.equal(s.title, "【テスト】note下書き保存の動作確認");
  assert.match(s.body, /<h2>大見出し<\/h2>/);
  assert.match(s.body, /<ul><li>箇条書き 1<\/li>/);
  assert.match(s.body, /<img /);
  assert.doesNotMatch(s.body, /\[\[IMAGE:/);
  assert.equal(s.eyecatch, true);
  assert.equal(s.publishClicked, false);
  await context.close();
});

test("下書き保存済みの記事はスキップする", async () => {
  const { file, context } = await setup();
  await publishDrafts([file], { context, outDir: path.dirname(file), timeoutMs: 5_000 });
  const results = await publishDrafts([file], { context, outDir: path.dirname(file), timeoutMs: 5_000 });
  assert.equal(results[0]!.outcome, "skipped");
  await context.close();
});
