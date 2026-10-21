/**
 * 公開系ボタンの誤クリック防止ガード（DESIGN.md §7.3）。
 * publisher からのクリックはすべて safeClick を通す。
 */
import type { Locator } from "playwright";
import { forbiddenLabelPatterns } from "../../config/note-selectors.ts";

export class ForbiddenClickError extends Error {}

/** ラベルが公開系なら例外 */
export function assertClickable(label: string): void {
  const normalized = label.replace(/\s+/g, " ").trim();
  const hit = forbiddenLabelPatterns.find((re) => re.test(normalized));
  if (hit) {
    throw new ForbiddenClickError(`公開系の操作は禁止されています: "${normalized}" (${hit})`);
  }
}

/** クリック直前に要素のテキスト・aria-label・title を読み、公開系なら押さずに例外 */
export async function safeClick(locator: Locator, options: { timeout?: number } = {}): Promise<void> {
  const target = locator.first();
  await target.waitFor({ state: "visible", timeout: options.timeout });
  const label = await target.evaluate((el) =>
    [el.textContent, el.getAttribute("aria-label"), el.getAttribute("title"), (el as HTMLInputElement).value]
      .filter(Boolean)
      .join(" "),
  );
  assertClickable(label);
  await target.click({ timeout: options.timeout });
}
