## Context

See proposal.md — Why. What shapes the approach:

- `../truck` solves this already with `scripts/render-specs.py` and a
  `task spec-site` target rendering into `public/`. It is 742 lines and imports
  a journey atlas, a design review gallery, a product story workbench and
  marketing research — all Dozer concerns. It also carries measured budgets
  (`MAX_CLEAN_GENERATION_SECONDS = 8.0`, a size ceiling raised deliberately
  once) that are worth copying as a habit.
- This project has six capability groups and will have on the order of fifteen
  capabilities. That is a different problem from truck's eighty-one.
- The verification conventions are prose conventions, established in
  `.skills/k230-spec-change/SKILL.md`, not structured data. Anything reading
  them is coupled to them.
- The site has to be at a URL that updates itself. The repository lives on
  GitHub, so Pages is the shortest path from a push to a reader.

## Goals / Non-Goals

**Goals:**

- A reader learns what is unproven before anything else.
- Evidence is one click from the requirement it grounds.
- A push to `main` updates what the reader sees.
- The part that must not be wrong — which requirements are proven — is small,
  in one place, and tested.

**Non-Goals:**

- Feature parity with truck's renderer.
- Search, or navigation beyond a capability index.
- Any deployment target but GitHub Pages.

## Decisions

**Which layer does what: Python reads the specs, Astro draws them.**
`scripts/render_specs.py` parses `openspec/specs/`, classifies every
requirement, checks cited evidence, and writes `site/src/data/specs.json`.
Astro reads that JSON and owns presentation and deployment and nothing else.

The alternative — Astro content collections reading the Markdown directly —
was rejected. It would have put the classification, the `<!-- UNVERIFIED -->`
parsing and the evidence checking into TypeScript, in a second language, with
a second set of tests, for no gain: Astro's Markdown pipeline does not
understand these conventions and would have needed the same hand-written
parsing either way. The classifier is the one part of this that must not be
wrong, so it stays in one place with unit tests around it.

**A hand-rolled HTML writer was built first and then replaced.** It worked,
and the design of the pages survived into Astro almost unchanged — the
stylesheet moved across verbatim. What it could not do was deploy itself. The
markup, the layout and the budget habit were the valuable part; the `write
this string to that file` half was thrown away. Its parsing half is what
`render_specs.py` still is.

**Parse the conventions, and fail when they do not parse.** The alternative,
treating an unrecognised requirement as grounded, was rejected: the unverified
count is the site's entire product, and a count that silently under-reports is
worse than no site. Failing loudly also makes the coupling to the skill
document visible the moment someone changes the convention.

**Failing does not mean withholding the site.** An unclassifiable requirement
makes `scripts/build_site.py` exit non-zero and name the file and the
requirement; it also renders that requirement on the site in a third colour,
as a defect. A build failure that produces nothing hides the defect from the
only person positioned to fix it. CI reads the exit code; a person reads the
page. This is a change to the requirement as originally written, and the
requirement was amended to say so rather than left disagreeing with the code.

**Quoting a convention is not using it.** `docs/spec-site` is the one
capability whose prose must discuss `<!-- UNVERIFIED -->`, and the first real
build read the quoted marker as a real one and reported two grounded
requirements as unverified. Code spans are masked, with offsets preserved,
before either the marker or the grounding line is looked for. The count being
wrong in that direction is exactly the failure this change exists to prevent.

**Render `specs/` only.** Publishing `changes/` would put proposals in front
of readers as though they were decided. Truck makes the same split. This is
enforced by the loader, which walks only `openspec/specs/`, and asserted
against the built output.

**Budgets from the first commit, set above current output.** Truck's history
shows the alternative: a budget set at what the tree happened to produce goes
red on ordinary growth and gets raised reflexively until it means nothing.
The budgets are on the whole build — the data pass plus Astro — because that
is what a person waits for and what CI pays for.

**One deployment, one base path.** GitHub Pages serves this repository under
`/tdisplay-k230/`. `npm run build` sets `ASTRO_BASE` to that path; `npm run
dev` and `npm run build:local` leave it unset so a local preview is
served from the root with nothing to reason about. A GitLab Pages job was
asked for and then withdrawn; with one forge there is no per-forge
indirection to carry, and every link in the site resolves through Astro's
`BASE_URL` rather than a hardcoded prefix.

The data pass does not know where the site is served from, and should not:
it emits `@@BASE@@` in the HTML it hands Astro, and Astro substitutes
`import.meta.env.BASE_URL` before rendering.

## Risks / Trade-offs

- **The convention parsing drifts from the skill document.** → Failing rather
  than defaulting turns the drift into a build error on the next push instead
  of a quietly wrong number.
- **`UNVERIFIED` markers are added faster than they are resolved, and the
  landing page becomes noise.** → Accepted. A large honest number is the
  correct output for a project at this stage, and hiding it would defeat the
  purpose.
- **A Node dependency in a repository that is otherwise Nix and Python.** →
  Accepted, and confined: `site/` is the only thing that needs it, and nothing
  in the image, the system or the board build touches it. The data pass runs
  on the standard library alone, so the specs can still be checked without npm.
- **Pages must be enabled on the repository once.** → The workflow asks for it
  (`configure-pages` with `enablement: true`), which fails if the repository's
  Actions token is read-only. Recorded in tasks.md as the one manual step.
- **Nobody reads it.** → Possible. Mitigated by it being a URL that is current
  without anyone doing anything.

## Open Questions

None outstanding. Whether to render evidence files into the site or link to
them in the repository is settled: they are rendered, because a link into a
checkout is not a link for a reader on the web.
