import assert from "node:assert/strict";
import { test } from "node:test";
import { assertClickable, ForbiddenClickError } from "../src/note/guard.ts";

test("公開系のラベルはクリック禁止", () => {
  for (const label of ["公開に進む", "公開する", "投稿する", "Publish", "予約投稿", " 公開\n設定 "]) {
    assert.throws(() => assertClickable(label), ForbiddenClickError, label);
  }
});

test("下書き保存などは許可", () => {
  for (const label of ["下書き保存", "画像", "メニューを開く", ""]) {
    assert.doesNotThrow(() => assertClickable(label), label);
  }
});
