/**
 * エントリポイント。
 *
 *   login                         手動ログイン → storageState 保存（ローカル専用）
 *   session-check                 ログイン状態を確認（切れていれば exit 1）
 *   draft <article.md...>         note に下書き保存
 *     --all                       articles/ 以下の全 article.md を対象にする
 *     --dry-run                   note にアクセスせず out/dry-run/ に HTML を出力
 *     --max <n>                   1 回の上限（既定 3）
 *     --interval <sec>            記事間の待機秒（既定 45、最小 30）
 *     --headed                    ブラウザを表示する（ローカルでの確認用）
 *   convert <article.md>          変換結果の HTML を標準出力へ
 */
import { readdir } from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { loadArticle } from "./article.ts";
import { convert } from "./note/convert.ts";
import { login } from "./note/login.ts";
import { publishDrafts } from "./note/publisher.ts";
import { checkSession } from "./note/session.ts";

async function findArticles(root = "articles"): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true }).catch(() => []);
  return entries
    .filter((e) => e.isDirectory())
    .map((e) => path.join(root, e.name, "article.md"))
    .sort();
}

async function main(argv: string[]): Promise<number> {
  const [command, ...rest] = argv;
  switch (command) {
    case "login":
      await login();
      return 0;

    case "session-check": {
      const ok = await checkSession();
      console.log(ok ? "note: ログイン中" : "note: ログインが切れています（npm run login で再ログイン）");
      return ok ? 0 : 1;
    }

    case "draft": {
      const { values, positionals } = parseArgs({
        args: rest,
        allowPositionals: true,
        options: {
          all: { type: "boolean", default: false },
          "dry-run": { type: "boolean", default: false },
          max: { type: "string" },
          interval: { type: "string" },
          headed: { type: "boolean", default: false },
        },
      });
      const files = values.all ? await findArticles() : positionals;
      if (files.length === 0) {
        console.error("対象の article.md を指定してください（または --all）");
        return 2;
      }
      const results = await publishDrafts(files, {
        dryRun: values["dry-run"],
        maxPerRun: values.max ? Number(values.max) : undefined,
        intervalMs: values.interval ? Number(values.interval) * 1000 : undefined,
        headless: !values.headed,
      });
      for (const r of results) {
        const detail =
          r.outcome === "drafted" ? r.url
          : r.outcome === "dry-run" ? r.htmlFile
          : r.outcome === "skipped" ? r.reason
          : `${r.error}${r.evidence?.length ? `\n    証跡: ${r.evidence.join(", ")}` : ""}`;
        console.log(`[${r.outcome}] ${r.file}\n    ${detail}`);
      }
      return results.some((r) => r.outcome === "failed") ? 1 : 0;
    }

    case "convert": {
      const file = rest[0];
      if (!file) {
        console.error("usage: convert <article.md>");
        return 2;
      }
      const article = await loadArticle(file);
      const { html, images } = convert(article.body);
      console.log(html);
      if (images.length) console.error(`画像 ${images.length} 件: ${images.map((i) => i.src).join(", ")}`);
      return 0;
    }

    default:
      console.error("usage: tsx src/cli.ts <login|session-check|draft|convert> ...");
      return 2;
  }
}

main(process.argv.slice(2)).then(
  (code) => process.exit(code),
  (e) => {
    console.error(e instanceof Error ? e.message : e);
    process.exit(1);
  },
);
