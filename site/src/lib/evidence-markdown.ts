import path from "node:path";
import type { EvidenceFile } from "./specs";

type Node = { type?: string; tagName?: string; properties?: Record<string, unknown>; children?: Node[] };

const origin = "https://raw.githubusercontent.com/knewter/tdisplay-k230";

function encodedPath(value: string): string {
  return value.split("/").map(encodeURIComponent).join("/");
}

export function rawEvidenceUrl(revision: string, filePath: string): string {
  return `${origin}/${revision}/${encodedPath(filePath)}`;
}

/** Repoint repository-relative Markdown links after Astro has parsed them. */
export function evidenceMarkdownLinks(
  sourcePath: string,
  files: EvidenceFile[],
  base: string,
  revision: string,
) {
  const pages = new Map(files.map((file) => [file.path, file]));
  const siteBase = base.endsWith("/") ? base : `${base}/`;
  return () => (tree: Node) => {
    function visit(node: Node): void {
      if (node.type === "element" && (node.tagName === "a" || node.tagName === "img")) {
        const key = node.tagName === "a" ? "href" : "src";
        const value = node.properties?.[key];
        if (typeof value === "string" && !/^(?:[a-z][a-z\d+.-]*:|\/|#)/i.test(value)) {
          const match = /^([^?#]+)([?#].*)?$/.exec(value);
          if (match) {
            let relative: string;
            try { relative = decodeURIComponent(match[1]); }
            catch { relative = match[1]; }
            const target = path.posix.normalize(path.posix.join(path.posix.dirname(sourcePath), relative));
            if (target !== ".." && !target.startsWith("../")) {
              const page = pages.get(target);
              node.properties![key] = page && (node.tagName === "a" || page.kind !== "image")
                ? `${siteBase}evidence/${page.slug}/${match[2] ?? ""}`
                : page?.asset
                  ? `${siteBase}${page.asset}${match[2] ?? ""}`
                  : `${rawEvidenceUrl(revision, target)}${match[2] ?? ""}`;
            }
          }
        }
      }
      node.children?.forEach(visit);
    }
    visit(tree);
  };
}
