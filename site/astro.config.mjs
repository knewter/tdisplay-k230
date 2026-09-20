// @ts-check
import { defineConfig } from "astro/config";

// One deployment: GitHub Pages at https://knewter.github.io/tdisplay-k230/,
// which serves the site under a project path. `npm run build` sets ASTRO_BASE
// to that path; `npm run dev` and `npm run build:local` leave it unset, so a
// local preview is served from the root with no prefix to reason about.
export default defineConfig({
  site: "https://knewter.github.io",
  base: process.env.ASTRO_BASE ?? "/",
  trailingSlash: "always",
  build: { format: "directory" },
  devToolbar: { enabled: false },
  compressHTML: true,
});
