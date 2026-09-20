## Why

This repository's specs answer a question nobody can currently ask it: **what
does this board actually do, as opposed to what is hoped for it?**

That distinction is the whole discipline here. The house rule is that an
observation on the board outranks vendor source and that a datasheet grounds
nothing, so every requirement is either backed by a committed boot log, a
photograph and a cited vendor file — or it carries an `<!-- UNVERIFIED -->`
marker. Those markers are the honest inventory of what this project has not
pinned down.

Today that inventory is only visible by grepping a tree of Markdown. It should
be the first thing a reader sees, including the reader who wrote it and has
forgotten — and it should be at a URL, because an inventory that requires a
checkout and a command is one nobody consults.

## What Changes

- **A site rendered from `openspec/specs/`**, one page per capability, built
  by a command that runs on a laptop as readily as in CI.
- **Verification status is the organising idea, not a footnote.** Each
  requirement is shown as grounded or unverified, and the landing page leads
  with the count of what is unproven. A reader should be able to answer "is the
  radio known to work?" without opening a file.
- **Grounding is a link, not a claim.** Where a requirement cites
  `docs/evidence/…`, the site links to it, so the boot log or photograph behind
  a requirement is one click away. Evidence that cannot be linked is treated as
  a defect in the requirement.
- **A budget the build enforces**, so the site stays fast to generate and
  cheap to host as capabilities accumulate.
- **Published on every push**, by GitHub Actions to GitHub Pages at
  `https://knewter.github.io/tdisplay-k230/`, so the count a reader sees is the
  count the specs currently say.

**Non-goals.** Rendering `openspec/changes/` — in-flight proposals are for
people working on them, and publishing drafts invites reading them as
decisions. Search, theming, or navigation beyond what a handful of capabilities
needs. Reproducing the Dozer renderer in `../truck`, which at 742 lines carries
a journey atlas, a design gallery and a product story this project has no use
for. Start small and grow toward it only where there is a reason.

## Capabilities

### New Capabilities

- `docs/spec-site`: how these specifications reach a reader, and what the
  rendering is obliged to show.

### Modified Capabilities

None.

## Impact

Adds `site/` (an Astro project), a data pass and a build command under
`scripts/`, their tests under `tests/`, and a GitHub Actions workflow under
`.github/workflows/`. Generated output — `site/dist/`, `site/node_modules/`,
`site/src/data/specs.json` — is gitignored.

Creates a coupling worth naming: the data pass parses the `<!-- UNVERIFIED -->`
convention and the `*Grounding: …*` citation form out of spec prose. Both are
established by `.skills/k230-spec-change/SKILL.md`, and a change to either
breaks the site quietly — so the build is obliged to fail loudly rather than
render a requirement whose status it could not determine.

Adds one thing the repository did not have: a dependency on Node and npm, for
the site only. Nothing in the image, the system or the board build touches it.
