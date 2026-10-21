/**
 * Markdown → note 貼り付け用 HTML（DESIGN.md §5.3, §7.2-4）。
 *
 * 対応するのは §5.3 で許可した要素だけ。それ以外は Violation として返し、
 * convert() は 1 件でもあれば例外にする（checks からは validate() を使う）。
 *
 * 画像は貼り付けでは入らないため、段落単独の画像を [[IMAGE:n]] というプレースホルダ段落に置き換え、
 * publisher がその位置で画像アップロード操作を行う。
 */
import { Lexer, type Token, type Tokens } from "marked";

export interface ImageRef {
  index: number;
  /** Markdown に書かれたパス（記事ディレクトリからの相対） */
  src: string;
  alt: string;
}

export interface Violation {
  element: string;
  message: string;
  /** 該当箇所の Markdown（先頭 60 文字） */
  excerpt: string;
}

export interface ConvertResult {
  html: string;
  images: ImageRef[];
  violations: Violation[];
}

export const imagePlaceholder = (index: number): string => `[[IMAGE:${index}]]`;

export class ConvertError extends Error {
  constructor(public readonly violations: Violation[]) {
    super(
      "使用できない Markdown 要素があります:\n" +
        violations.map((v) => `- ${v.message}: ${v.excerpt}`).join("\n"),
    );
  }
}

/** 変換して HTML を返す。許可外の要素があれば ConvertError */
export function convert(markdown: string): ConvertResult {
  const result = render(markdown);
  if (result.violations.length > 0) throw new ConvertError(result.violations);
  return result;
}

/** 許可外の要素を列挙するだけ（例外にしない） */
export function validate(markdown: string): Violation[] {
  return render(markdown).violations;
}

function render(markdown: string): ConvertResult {
  const tokens = new Lexer({ gfm: true, breaks: true }).lex(markdown);
  const ctx: Ctx = { images: [], violations: [] };
  const html = tokens.map((t) => block(t, ctx)).filter(Boolean).join("\n");
  return { html, images: ctx.images, violations: ctx.violations };
}

interface Ctx {
  images: ImageRef[];
  violations: Violation[];
}

function violate(ctx: Ctx, token: Token, element: string, message: string): string {
  const excerpt = (token.raw ?? "").trim().replace(/\s+/g, " ").slice(0, 60);
  ctx.violations.push({ element, message, excerpt });
  return "";
}

function block(token: Token, ctx: Ctx): string {
  switch (token.type) {
    case "space":
    case "def":
      return "";
    case "heading": {
      const t = token as Tokens.Heading;
      if (t.depth === 1) return violate(ctx, t, "h1", "# 見出しはタイトル扱いのため本文に使えません");
      if (t.depth > 3) return violate(ctx, t, `h${t.depth}`, "見出しは ## と ### のみ使えます");
      return `<h${t.depth}>${inline(t.tokens, ctx)}</h${t.depth}>`;
    }
    case "paragraph": {
      const t = token as Tokens.Paragraph;
      const only = t.tokens.filter((c) => !(c.type === "text" && c.raw.trim() === ""));
      if (only.length === 1 && only[0]!.type === "image") {
        const img = only[0] as Tokens.Image;
        const index = ctx.images.length;
        ctx.images.push({ index, src: img.href, alt: img.text });
        return `<p>${imagePlaceholder(index)}</p>`;
      }
      return `<p>${inline(t.tokens, ctx)}</p>`;
    }
    case "list": {
      const t = token as Tokens.List;
      if (t.items.some((i) => i.task)) return violate(ctx, t, "task-list", "チェックボックス付きリストは使えません");
      const tag = t.ordered ? "ol" : "ul";
      const start = t.ordered && t.start !== "" && t.start !== 1 ? ` start="${t.start}"` : "";
      const items = t.items.map((item) => `<li>${listItem(item, ctx)}</li>`).join("");
      return `<${tag}${start}>${items}</${tag}>`;
    }
    case "blockquote": {
      const t = token as Tokens.Blockquote;
      const inner = t.tokens.map((c) => {
        if (c.type === "paragraph") return `<p>${inline((c as Tokens.Paragraph).tokens, ctx)}</p>`;
        if (c.type === "space") return "";
        return violate(ctx, c, `blockquote>${c.type}`, "引用の中には段落しか書けません");
      });
      return `<blockquote>${inner.join("")}</blockquote>`;
    }
    case "code": {
      const t = token as Tokens.Code;
      return `<pre><code>${escapeHtml(t.text)}</code></pre>`;
    }
    case "hr":
      return "<hr>";
    case "table":
      return violate(ctx, token, "table", "表は note 非対応のため箇条書きに置き換えてください");
    case "html":
      return violate(ctx, token, "html", "HTML は使えません");
    case "text": {
      // トップレベルの text はリスト外では通常出ないが、念のため段落扱い
      const t = token as Tokens.Text;
      return `<p>${t.tokens ? inline(t.tokens, ctx) : escapeHtml(t.text)}</p>`;
    }
    default:
      return violate(ctx, token, token.type, `${token.type} は使えません`);
  }
}

function listItem(item: Tokens.ListItem, ctx: Ctx): string {
  const parts: string[] = [];
  for (const c of item.tokens) {
    if (c.type === "list") {
      violate(ctx, c, "nested-list", "リストの入れ子は使えません");
    } else if (c.type === "text") {
      const t = c as Tokens.Text;
      parts.push(t.tokens ? inline(t.tokens, ctx) : escapeHtml(t.text));
    } else if (c.type === "paragraph") {
      parts.push(inline((c as Tokens.Paragraph).tokens, ctx));
    } else if (c.type !== "space") {
      violate(ctx, c, `li>${c.type}`, "リスト項目の中には文章しか書けません");
    }
  }
  return parts.join("<br>");
}

function inline(tokens: Token[], ctx: Ctx): string {
  return tokens
    .map((t) => {
      switch (t.type) {
        case "text": {
          const tt = t as Tokens.Text;
          return tt.tokens ? inline(tt.tokens, ctx) : escapeHtml(tt.text);
        }
        case "escape":
          return escapeHtml((t as Tokens.Escape).text);
        case "strong":
          return `<strong>${inline((t as Tokens.Strong).tokens, ctx)}</strong>`;
        case "br":
          return "<br>";
        case "link": {
          const l = t as Tokens.Link;
          if (!/^https?:\/\//.test(l.href)) {
            return violate(ctx, t, "link", "リンクは http(s) の URL のみ使えます");
          }
          return `<a href="${escapeAttr(l.href)}">${inline(l.tokens, ctx)}</a>`;
        }
        case "image":
          return violate(ctx, t, "inline-image", "画像は単独の段落に置いてください");
        case "em":
          return violate(ctx, t, "em", "斜体は使えません（強調は **太字** で）");
        case "del":
          return violate(ctx, t, "del", "取り消し線は使えません");
        case "codespan":
          return violate(ctx, t, "codespan", "インラインコードは使えません（コードブロックを使ってください）");
        case "html":
          return violate(ctx, t, "html", "HTML は使えません");
        default:
          return violate(ctx, t, t.type, `${t.type} は使えません`);
      }
    })
    .join("");
}

export function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeAttr(s: string): string {
  return escapeHtml(s).replace(/"/g, "&quot;");
}
