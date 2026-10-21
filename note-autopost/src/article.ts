/**
 * articles/<id>/article.md の読み書き（DESIGN.md §5.2）。
 */
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import YAML from "yaml";

export type ArticleStatus = "generated" | "needs_human" | "drafted" | "published";

export interface ArticleMeta {
  topic_id: string;
  title: string;
  tags: string[];
  eyecatch?: string | null;
  status: ArticleStatus;
  note_draft_url: string | null;
  generated_at?: string;
  models?: Record<string, string>;
  sources?: { title: string; url: string }[];
  [key: string]: unknown;
}

export interface Article {
  /** article.md の絶対パス */
  file: string;
  /** 記事ディレクトリ（画像パスの基準） */
  dir: string;
  meta: ArticleMeta;
  body: string;
}

const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/;

export function parseArticle(source: string, file: string): Article {
  const m = FRONTMATTER.exec(source);
  if (!m) throw new Error(`${file}: frontmatter がありません`);
  const meta = YAML.parse(m[1]!) as Partial<ArticleMeta> | null;
  if (!meta || typeof meta.title !== "string" || meta.title.trim() === "") {
    throw new Error(`${file}: frontmatter に title がありません`);
  }
  return {
    file: path.resolve(file),
    dir: path.dirname(path.resolve(file)),
    meta: {
      ...meta,
      topic_id: meta.topic_id ?? path.basename(path.dirname(file)),
      title: meta.title,
      tags: meta.tags ?? [],
      status: meta.status ?? "generated",
      note_draft_url: meta.note_draft_url ?? null,
    },
    body: m[2]!.replace(/^\s*\n/, ""),
  };
}

export async function loadArticle(file: string): Promise<Article> {
  return parseArticle(await readFile(file, "utf8"), file);
}

export function serializeArticle(article: Pick<Article, "meta" | "body">): string {
  const yaml = YAML.stringify(article.meta, { lineWidth: 0 }).trimEnd();
  return `---\n${yaml}\n---\n\n${article.body}`;
}

/** frontmatter の一部を更新して書き戻す */
export async function updateArticleMeta(article: Article, patch: Partial<ArticleMeta>): Promise<Article> {
  const next = { ...article, meta: { ...article.meta, ...patch } };
  await writeFile(article.file, serializeArticle(next), "utf8");
  return next;
}
