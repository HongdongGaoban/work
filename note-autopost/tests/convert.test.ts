import assert from "node:assert/strict";
import { test } from "node:test";
import { convert, ConvertError, validate } from "../src/note/convert.ts";

const elements = (md: string) => validate(md).map((v) => v.element);

test("見出し h2/h3 と段落・太字・リンク", () => {
  const { html } = convert("## 大見出し\n\n### 小見出し\n\n本文 **太字** と [リンク](https://example.com/?a=1&b=2)。");
  assert.equal(
    html,
    '<h2>大見出し</h2>\n<h3>小見出し</h3>\n<p>本文 <strong>太字</strong> と <a href="https://example.com/?a=1&amp;b=2">リンク</a>。</p>',
  );
});

test("段落内の改行は <br>", () => {
  assert.equal(convert("1行目\n2行目").html, "<p>1行目<br>2行目</p>");
});

test("箇条書き・番号付きリスト", () => {
  assert.equal(convert("- a\n- **b**").html, "<ul><li>a</li><li><strong>b</strong></li></ul>");
  assert.equal(convert("1. x\n2. y").html, "<ol><li>x</li><li>y</li></ol>");
  assert.equal(convert("3. x\n4. y").html, '<ol start="3"><li>x</li><li>y</li></ol>');
});

test("引用・コードブロック・区切り線", () => {
  assert.equal(convert("> 引用").html, "<blockquote><p>引用</p></blockquote>");
  assert.equal(convert("```ts\nif (a < b) {}\n```").html, "<pre><code>if (a &lt; b) {}</code></pre>");
  assert.equal(convert("a\n\n---\n\nb").html, "<p>a</p>\n<hr>\n<p>b</p>");
});

test("単独段落の画像はプレースホルダに置き換える", () => {
  const r = convert("前\n\n![説明](images/a.png)\n\n![](images/b.png)\n\n後");
  assert.equal(r.html, "<p>前</p>\n<p>[[IMAGE:0]]</p>\n<p>[[IMAGE:1]]</p>\n<p>後</p>");
  assert.deepEqual(r.images, [
    { index: 0, src: "images/a.png", alt: "説明" },
    { index: 1, src: "images/b.png", alt: "" },
  ]);
});

test("HTML 特殊文字をエスケープする", () => {
  assert.equal(convert("a < b & c > d").html, "<p>a &lt; b &amp; c &gt; d</p>");
  assert.equal(convert("\\*not bold\\*").html, "<p>*not bold*</p>");
});

test("禁止要素を検出する", () => {
  assert.deepEqual(elements("# タイトル"), ["h1"]);
  assert.deepEqual(elements("#### 深い"), ["h4"]);
  assert.deepEqual(elements("| a | b |\n|---|---|\n| 1 | 2 |"), ["table"]);
  assert.deepEqual(elements("- a\n  - b"), ["nested-list"]);
  assert.deepEqual(elements("- [ ] todo"), ["task-list"]);
  assert.deepEqual(elements("<div>x</div>"), ["html"]);
  assert.deepEqual(elements("*斜体*"), ["em"]);
  assert.deepEqual(elements("~~消す~~"), ["del"]);
  assert.deepEqual(elements("`code`"), ["codespan"]);
  assert.deepEqual(elements("文中 ![](a.png) の画像"), ["inline-image"]);
  assert.deepEqual(elements("[x](javascript:alert(1))"), ["link"]);
});

test("convert は禁止要素があれば ConvertError", () => {
  assert.throws(() => convert("ok\n\n| a |\n|---|\n| 1 |"), ConvertError);
});
