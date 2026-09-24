# Public work-board data and host checks

The `/work/` page is a static snapshot of committed repository state. `scripts/render_work_board.py` reads the build checkout's `HEAD` through Git, counts checked and open OpenSpec tasks, and classifies active versus archived changes. `docs/work-board-status.json` holds reviewed exceptions where task checkboxes do not identify source or physical-proof state. An override names an existing review commit, rationale, next gate and committed evidence path. It does not have to name the snapshot commit itself. The normal generator ignores uncommitted edits; `--working-tree` is an explicit fixture and pre-commit mode and is labeled as such in its output.

The accepted requirement ledger remains generated only from `openspec/specs/`. Its in-flight proposal exclusion test still applies to index and capability pages. The work board labels active proposals as drafts and links to their source at the snapshot revision. A task count, archived OpenSpec change, source checkpoint, and physical verification are not interchangeable claims. The page displays its source revision and UTC build time; it is not live agent telemetry.

Host validation during implementation on 2026-09-23/24 UTC:

```text
python3 tests/test_work_board.py         10 tests passed
python3 scripts/build_site.py --local    155 pages, 4,886,224 bytes, 16.61 s; built-site tests passed
python3 scripts/build_site.py            155 pages, 4,908,798 bytes, 9.93 s; built-site tests passed
openspec validate the-site-shows-a-public-work-board --strict   passed
```

The first production-prefix build used candidate revision `7ed1dd56a8bbfa10927426473c9cff49e4101b45`. After the final task-count and dependency-cycle correction, `01d84a43b4b4cb7dda721be4bc2dc53501637a00` passed the same full build: 155 pages, 4,908,560 bytes, 7.25 s. Its generated board contains 6 planned, 7 in-progress, 2 verification/review and 16 archived changes. The splash change counts 20/27 tasks, including alphanumeric subgroup IDs; the launcher gesture change counts 15/16. Chromium host previews at 1440×1100 and 568×1232 were inspected for column and stacked-lane readability. These are browser layout checks, not photographs of the handheld. The public `/work/` deployment and its exact landed revision remain to be recorded after merge and push. No board or Nix build was used.
