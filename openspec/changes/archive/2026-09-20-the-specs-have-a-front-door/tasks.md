# Tasks

This change needs no hardware. Every command below runs on the build host.

The pieces: `scripts/render_specs.py` reads the specs and writes
`site/src/data/specs.json`; `site/` is the Astro project that renders it;
`scripts/build_site.py` is the one command that runs both and enforces the
budgets; `.github/workflows/spec-site.yml` publishes to GitHub Pages. Tests
are `tests/test_render_specs.py` (the data pass, stdlib only) and
`tests/test_site_output.py` (assertions against the built site).

## 1. Read the specs

- [x] 1.1 Parse `openspec/specs/` into capabilities and requirements, classifying each as grounded or unverified, and failing on any requirement that cannot be classified. Verify with a unit test covering a grounded requirement, an `UNVERIFIED` one, and one that is neither — asserting the third raises

  `python3 -m unittest discover -s tests -p 'test_render_specs.py'` — 18 tests.
  `classify()` returns grounded only on a `*Grounding: ...*` citation, returns
  unverified on an `<!-- UNVERIFIED -->` marker keeping its reason, and raises
  `UnclassifiedRequirement` naming the file and the requirement when neither
  is present. A sixth test covers the bug the first real build found: a marker
  quoted in a code span is not a marker.

- [x] 1.2 Extract `docs/evidence/` citations from requirement prose and check each path exists, failing with the requirement name and the missing path. Verify with a unit test for a present path and an absent one

  Same suite, `TestEvidenceCitations` — covering a present path, an absent one
  (the failure names both the requirement and the path), prose that is not a
  citation (`/dev/ttyACM0`, `openspec/specs/`), and a path named only inside
  an `UNVERIFIED` marker, which is an intention rather than a citation.

## 2. Render

- [x] 2.1 Render one page per capability, showing each requirement's status and its reason where unverified. Verify by running the renderer over the current tree and confirming a page exists for every `openspec/specs/**/spec.md`

  `tests/test_site_output.py::test_a_page_for_every_capability_spec` walks the
  real `openspec/specs/` and asserts `site/dist/c/<group>-<name>/index.html`
  exists for each. `scripts/build_site.py` runs it after every build.

- [x] 2.2 Render a landing page stating the unverified count before any capability prose. Verify by asserting in a test that the count appears before the first capability heading in the generated HTML

  `test_the_count_comes_before_any_capability_prose` asserts the count's
  offset in the built HTML precedes every section heading and every capability
  name. `test_the_count_matches_the_specs` then re-derives the number from the
  spec tree and asserts the page prints that one — the headline figure is
  checked, not trusted.

- [x] 2.3 Turn evidence citations into working links. Verify by generating the site and confirming every `docs/evidence/` link resolves to a committed file

  `test_every_internal_link_resolves` walks every built page and resolves
  every `href` and `src` against `site/dist`, base prefix included.
  `test_every_cited_evidence_file_has_a_page` asserts a cited path has one.

- [x] 2.4 Confirm nothing from `openspec/changes/` appears in the output. Verify with a test that greps the generated tree for the id of an in-flight change and expects no match

  `test_nothing_from_an_in_flight_proposal_is_published` enumerates the open
  change ids from the filesystem and asserts none appears in any built index
  or capability page. The loader only ever walks `openspec/specs/`.

## 3. Budgets

- [x] 3.1 Measure generation time and output size on the current tree, and set budgets above both with the measured values recorded. Verify by committing the measurements alongside the budgets and noting the date and machine

  `docs/evidence/spec-site-build.txt`: 2026-09-20, `solomon`, Linux
  7.1.9-1-MANJARO x86_64, Ryzen 9 5950X, Python 3.14.7, Node 26.7.0, Astro
  5.18.2. Measured **6.7 s** and **43 KiB** for the whole build — data pass
  plus Astro. Budgets in `scripts/build_site.py` are 120 s and 8 MiB, which is
  ~18x and ~193x. High on purpose: a cold CI runner is slower than a warm
  5950X, and the taxonomy allows fifteen capabilities where this tree has a
  handful.

- [x] 3.2 Fail the build when either budget is exceeded, reporting measured against budget. Verify with a test that forces a breach and asserts the failure names both numbers

  `TestBudgets` asserts the message carries the measured value and the budget
  for time and for size. `./scripts/build_site.py --max-bytes 1` exits 2 and
  prints `output is 43371 bytes against a budget of 1 bytes`.

## 4. Make it runnable

- [x] 4.1 Expose the build as one command that a person and CI both run. Verify by running it from a clean checkout

  `./scripts/build_site.py` — data pass, Astro, budgets, assertions, in that
  order, with a non-zero exit on any failure. It is the only build step in the
  workflow. `npm install --prefix site` is needed once; the data pass itself
  imports nothing outside the Python standard library, so the specs can be
  checked with no npm at all.

  *(This task originally read "add `markdown` to the development shell". The
  dependency was never added: spec prose needs paragraphs, bullets, `code`,
  `*em*` and `**strong**`, which is about forty lines of `re`. And `flake.nix`
  is owned by another change in flight, so the site's Node dependency lives in
  `site/package.json` rather than in the development shell.)*

- [x] 4.2 Gitignore the generated output and document the command in `README.md`. Verify with `git status` clean after a build, and by following the README's instruction from scratch

  `/site/node_modules/`, `/site/dist/`, `/site/.astro/`,
  `/site/src/data/specs.json` and `/site/public/evidence/` are ignored;
  `git status` is clean of build output after a run. README gained a *Reading
  the specs* section under Planning with the URL, the local commands, what
  grounded and unverified mean, and how the build fails.

- [x] 4.3 Resolve the `UNVERIFIED` markers in `docs/spec-site` against the working site. Verify with `openspec validate --all`

  Five of the six requirements are grounded in the build, its tests and
  `docs/evidence/spec-site-build.txt`. The sixth — the published site being
  current — stays `UNVERIFIED`, because the deployment has not succeeded yet
  (see 5.2). Marking it grounded on the strength of a workflow file that has
  never deployed is exactly the move this capability exists to prevent.

## 5. Publish it

- [x] 5.1 Build and deploy from GitHub Actions to GitHub Pages on every push to the default branch. Verify by pushing and confirming the workflow builds the site

  `.github/workflows/spec-site.yml`. Run
  [35536825120](https://github.com/knewter/tdisplay-k230/actions/runs/35536825120)
  installed the dependencies, ran the data-pass tests and built the site
  successfully on `ubuntu-latest`.

- [ ] 5.2 Confirm the URL serves the site. Verify by fetching `https://knewter.github.io/tdisplay-k230/` and finding the unverified count in it

  **Blocked on one manual step, which cannot be done from CI.** Both runs so
  far failed at `actions/configure-pages`: GitHub Pages has never been enabled
  on the repository, and the workflow's attempt to enable it
  (`enablement: true`) was refused — the repository's Actions token does not
  have permission to create a Pages site.

  What has to be clicked, once:

  1. <https://github.com/knewter/tdisplay-k230/settings/pages> → **Build and
     deployment** → **Source: GitHub Actions**.
  2. If that is not selectable, or the next run still fails:
     <https://github.com/knewter/tdisplay-k230/settings/actions> → **Workflow
     permissions** → **Read and write permissions** → Save.
  3. <https://github.com/knewter/tdisplay-k230/actions/workflows/spec-site.yml>
     → latest run → **Re-run all jobs**. Any push to `main` also works.

  Once a deployment completes, this box and the `UNVERIFIED` marker on *The
  published site is current without anyone maintaining it* are resolved
  together, grounded by the deployment and the fetched page.
