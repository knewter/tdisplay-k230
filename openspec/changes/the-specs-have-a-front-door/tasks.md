# Tasks

This change needs no hardware. Every command below runs on the build host.

The renderer is `scripts/render_specs.py`; its tests are
`tests/test_render_specs.py` and run with
`python3 -m unittest discover -s tests`. The measurements behind the budgets
are committed at `docs/evidence/spec-site-build.txt`.

## 1. Read the specs

- [x] 1.1 Parse `openspec/specs/` into capabilities and requirements, classifying each as grounded or unverified, and failing on any requirement that cannot be classified. Verify with a unit test covering a grounded requirement, an `UNVERIFIED` one, and one that is neither — asserting the third raises

  `python3 -m unittest discover -s tests -k TestClassification` — five tests.
  `classify()` returns grounded only on a `*Grounding: ...*` citation, returns
  unverified on an `<!-- UNVERIFIED -->` marker keeping its reason, and raises
  `UnclassifiedRequirement` naming the file and the requirement when neither
  is present.

- [x] 1.2 Extract `docs/evidence/` citations from requirement prose and check each path exists, failing with the requirement name and the missing path. Verify with a unit test for a present path and an absent one

  `python3 -m unittest discover -s tests -k TestEvidenceCitations` — four
  tests, covering a present path, an absent one (the failure names both the
  requirement and the path), prose that is not a citation (`/dev/ttyACM0`,
  `openspec/specs/`), and a path named only inside an `UNVERIFIED` marker,
  which is an intention rather than a citation and must not be checked.

## 2. Render

- [x] 2.1 Render one page per capability, showing each requirement's status and its reason where unverified. Verify by running the renderer over the current tree and confirming a page exists for every `openspec/specs/**/spec.md`

  `test_the_real_tree_gets_a_page_for_every_spec_file` renders the real
  repository and asserts one page per `spec.md`, whatever the tree holds at
  the time. Also run by hand over a tree staging nine capabilities:
  twelve pages, recorded in `docs/evidence/spec-site-build.txt`.

- [x] 2.2 Render a landing page stating the unverified count before any capability prose. Verify by asserting in a test that the count appears before the first capability heading in the generated HTML

  `test_landing_page_states_the_count_before_any_capability_prose` asserts the
  count's offset in the generated HTML precedes the "Capabilities" heading,
  the capability's name, and the first distinctive word of its purpose. The
  count is the page's `<h1>`.

- [x] 2.3 Turn evidence citations into working links. Verify by generating the site and confirming every `docs/evidence/` link resolves to a committed file

  `test_evidence_citations_become_working_links` asserts every non-external
  `href` in a generated capability page resolves to a file that exists, and
  that the cited boot log's text is present on the page it resolves to. Cited
  files are copied into the site, so a link resolves wherever it is served
  from and not only inside a checkout.

- [x] 2.4 Confirm nothing from `openspec/changes/` appears in the output. Verify with a test that greps the generated tree for the id of an in-flight change and expects no match

  `test_nothing_from_openspec_changes_reaches_the_output` renders the real
  repository, enumerates the open change ids from the filesystem, and asserts
  none appears in any generated index or capability page. The loader only ever
  walks `openspec/specs/`.

## 3. Budgets

- [x] 3.1 Measure generation time and output size on the current tree, and set budgets above both with the measured values recorded. Verify by committing the measurements alongside the budgets and noting the date and machine

  `docs/evidence/spec-site-build.txt`: 2026-09-20, `solomon`, Linux
  7.1.9-1-MANJARO x86_64, Ryzen 9 5950X, Python 3.14.7. Two runs — the
  published tree, and a tree staging every capability the open proposals will
  add. The second is the one the budget is set against: **0.017 s** and
  **78 KiB** over nine capabilities and twelve pages. Budgets are 5.0 s and
  4 MiB, roughly 290x and 54x above, deliberately high so that growth toward
  the fifteen capabilities the taxonomy allows cannot turn them red.

- [x] 3.2 Fail the build when either budget is exceeded, reporting measured against budget. Verify with a test that forces a breach and asserts the failure names both numbers

  `python3 -m unittest discover -s tests -k TestBudgets` — four tests. Two
  assert the message carries the measured value and the budget for time and
  for size; one runs the command with `--max-bytes 1` and asserts a non-zero
  exit; one asserts the real tree is inside its budgets.

## 4. Make it runnable

- [x] 4.1 Add `markdown` to the development shell and expose the renderer as one command. Verify by running it from a clean shell with no network

  **The dependency was dropped rather than added.** Spec prose needs only
  paragraphs, bullets, `code`, `*em*` and `**strong**`; that is about forty
  lines of `re`, and it buys the requirement that rendering needs no network
  outright rather than by arranging for one. There is no `markdown` in the
  development shell because the renderer imports nothing outside the standard
  library.

  Verified from a bare environment with no `HOME`, no user site-packages and
  nothing on `PATH` but `/usr/bin:/bin`:

  ```
  $ env -i HOME=/nonexistent PATH=/usr/bin:/bin sh -c \
      'cd <repo> && ./scripts/render_specs.py'
  <repo>/public: 1 pages, 13939 bytes, 0.000 s
  0 of 0 requirements unverified
  ```

- [x] 4.2 Gitignore the output directory and document the command in `README.md`. Verify with `git status` clean after a build, and by following the README's instruction from scratch

  `/public/` (and Python bytecode) added to `.gitignore`; `git status` is
  clean of build output after a run. README gained a *Reading the specs*
  section under Planning, giving the one command, what grounded and unverified
  mean, how the renderer fails, and where the budget measurements live.

- [x] 4.3 Resolve the `UNVERIFIED` markers in `docs/spec-site` against the working renderer. Verify with `openspec validate --all`

  All five markers replaced with grounding that cites the renderer, its tests,
  and `docs/evidence/spec-site-build.txt`. `openspec validate --all`: 4 passed,
  0 failed.

  One requirement gained prose and a scenario rather than only losing its
  marker. *The renderer fails rather than guessing* now says what failing
  means: a non-zero exit naming every unclassifiable requirement, **and** the
  site still written with those requirements shown as defects in their own
  colour. Withholding the site would hide the defect from the only person
  positioned to fix it.
