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
forgotten.

## What Changes

- **A static site rendered from `openspec/specs/`**, one page per capability,
  built by a command that runs on a laptop as readily as in a job.
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

**Non-goals.** Rendering `openspec/changes/` — in-flight proposals are for
people working on them, and publishing drafts invites reading them as
decisions. Any hosting or deployment; this change produces a directory.
Search, theming, or navigation beyond what a handful of capabilities needs.
Reproducing the Dozer renderer in `../truck`, which at 742 lines carries a
journey atlas, a design gallery and a product story this project has no use
for. Start small and grow toward it only where there is a reason.

## Capabilities

### New Capabilities

- `docs/spec-site`: how these specifications reach a reader, and what the
  rendering is obliged to show.

### Modified Capabilities

None.

## Impact

Adds a renderer under `scripts/`, its output directory to `.gitignore`, and a
Python dependency on `markdown` to the flake's development shell.

Creates a coupling worth naming: the renderer parses the `<!-- UNVERIFIED -->`
convention and the `docs/evidence/` path convention out of spec prose. Both are
established by `.skills/k230-spec-change/SKILL.md`, and a change to either
breaks the site quietly — so the renderer is obliged to fail loudly rather than
render a requirement whose status it could not determine.
