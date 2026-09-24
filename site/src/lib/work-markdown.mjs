import path from "node:path";
import { isIP } from "node:net";

function publicHttps(value) {
  let url;
  try { url = new URL(value); }
  catch { return false; }
  const host = url.hostname.toLowerCase();
  return url.protocol === "https:"
    && !url.username && !url.password && !url.port
    && host.includes(".") && !host.endsWith(".")
    && !isIP(host) && !host.startsWith("[")
    && ![".localhost", ".local", ".internal", ".test", ".invalid"].some((suffix) => host.endsWith(suffix));
}

/** Resolve links inside committed proposal/design/task/spec Markdown. */
export function workMarkdownLinks(
  sourcePath,
  evidence,
  documents,
  knownPaths,
  base,
  revision,
) {
  const evidenceByPath = new Map(evidence.map((file) => [file.path, file]));
  const docByPath = new Map(documents.map((doc) => [doc.path, doc]));
  const known = new Set(knownPaths);
  const siteBase = base.endsWith("/") ? base : `${base}/`;
  const github = `https://github.com/knewter/tdisplay-k230/blob/${revision}/`;
  return () => (tree) => {
    const visit = (node) => {
      if (node.type === "element" && (node.tagName === "a" || node.tagName === "img")) {
        const key = node.tagName === "a" ? "href" : "src";
        const value = node.properties?.[key];
        if (typeof value === "string") {
          if (value.startsWith("#")) {
            // A heading anchor stays inside the active document.
          } else if (value.startsWith("/") || /^[a-z][a-z\d+.-]*:/i.test(value)) {
            if (node.tagName === "img" || !publicHttps(value)) {
              throw new Error(`unsupported work Markdown link: ${sourcePath} -> ${value}`);
            }
          } else {
            const match = /^([^?#]+)([?#].*)?$/.exec(value);
            if (match) {
              let relative;
              try { relative = decodeURIComponent(match[1]); }
              catch { relative = match[1]; }
              const target = path.posix.normalize(relative.startsWith("docs/") || relative.startsWith("openspec/")
                ? relative : path.posix.join(path.posix.dirname(sourcePath), relative));
              if (target === ".." || target.startsWith("../")) {
                throw new Error(`work Markdown link escapes repository: ${sourcePath} -> ${value}`);
              }
              if (!known.has(target)) {
                throw new Error(`work Markdown link has no committed target: ${sourcePath} -> ${value}`);
              }
              const suffix = match[2] ?? "";
              const localEvidence = evidenceByPath.get(target);
              const localDoc = docByPath.get(target);
              if (node.tagName === "img") {
                if (!localEvidence || localEvidence.kind !== "image" || !localEvidence.asset) {
                  throw new Error(`work Markdown image has no published asset: ${sourcePath} -> ${value}`);
                }
                node.properties[key] = `${siteBase}${localEvidence.asset}${suffix}`;
              } else if (localEvidence) {
                node.properties[key] = `${siteBase}evidence/${localEvidence.slug}/${suffix}`;
              } else if (localDoc) {
                node.properties[key] = `${siteBase}work/?work=${encodeURIComponent(localDoc.workId)}&doc=${localDoc.section}`;
              } else {
                node.properties[key] = `${github}${target.split("/").map(encodeURIComponent).join("/")}${suffix}`;
              }
            }
          }
        }
      }
      node.children?.forEach(visit);
    };
    visit(tree);
  };
}
