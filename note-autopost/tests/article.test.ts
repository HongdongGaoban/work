import assert from "node:assert/strict";
import { test } from "node:test";
import { parseArticle, serializeArticle } from "../src/article.ts";

const src = `---
topic_id: t1
title: タイトル
tags: [a, b]
status: generated
note_draft_url: null
---

本文です。
`;

test("frontmatter と本文を分離する", () => {
  const a = parseArticle(src, "articles/x/article.md");
  assert.equal(a.meta.title, "タイトル");
  assert.deepEqual(a.meta.tags, ["a", "b"]);
  assert.equal(a.meta.note_draft_url, null);
  assert.equal(a.body, "本文です。\n");
});

test("書き戻しで本文と値が保たれる", () => {
  const a = parseArticle(src, "articles/x/article.md");
  const again = parseArticle(
    serializeArticle({ ...a, meta: { ...a.meta, note_draft_url: "https://editor.note.com/notes/n1/edit", status: "drafted" } }),
    "articles/x/article.md",
  );
  assert.equal(again.body, a.body);
  assert.equal(again.meta.status, "drafted");
  assert.equal(again.meta.note_draft_url, "https://editor.note.com/notes/n1/edit");
});

test("title がなければエラー", () => {
  assert.throws(() => parseArticle("---\ntags: []\n---\n本文", "a.md"));
});
