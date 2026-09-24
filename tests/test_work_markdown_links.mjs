import assert from "node:assert/strict";
import { workMarkdownLinks } from "../site/src/lib/work-markdown.mjs";

const source = "openspec/changes/example/design.md";
const evidence = [
  { path: "docs/evidence/example/README.md", slug: "docs-evidence-example-readme-md", kind: "text" },
  { path: "docs/evidence/example/image.png", slug: "docs-evidence-example-image-png", kind: "image", asset: "assets/example.png" },
];
const documents = [{ path: "openspec/changes/example/tasks.md", workId: "example", section: 2 }];
const rewrite = workMarkdownLinks(source, evidence, documents, ["docs/evidence/example/README.md", "docs/evidence/example/image.png", "openspec/changes/example/tasks.md"], "/tdisplay-k230/", "1234567");
const link = (href, tagName = "a") => ({ type: "element", tagName, properties: { [tagName === "a" ? "href" : "src"]: href }, children: [] });
const render = (node) => { rewrite()({ type: "root", children: [node] }); return node.properties.href ?? node.properties.src; };

assert.equal(render(link("docs/evidence/example/README.md")), "/tdisplay-k230/evidence/docs-evidence-example-readme-md/");
assert.equal(render(link("tasks.md")), "/tdisplay-k230/work/?work=example&doc=2");
assert.equal(render(link("https://github.com/omacom/omarchy")), "https://github.com/omacom/omarchy");
assert.equal(render(link("https://docs.example.com/new-public-reference")), "https://docs.example.com/new-public-reference");
assert.equal(render(link("#section")), "#section");
assert.equal(render(link("docs/evidence/example/image.png", "img")), "/tdisplay-k230/assets/example.png");
assert.throws(() => render(link("missing.md")), /no committed target/);
assert.throws(() => render(link("docs/evidence/example/README.md", "img")), /no published asset/);
for (const href of ["javascript:alert(1)", "data:text/html,evil", "//private.example/", "http://example.com/", "https://127.0.0.1/private", "https://localhost/private", "https://tool.local/x", "https://private.invalid/x", "https://user:pass@example.com/", "https://example.com:8443/", "/tmp/hidden"])
  assert.throws(() => render(link(href)), /unsupported work Markdown link/);
assert.throws(() => render(link("https://github.com/image.png", "img")), /unsupported work Markdown link/);
console.log("work Markdown links: 20 assertions passed");
