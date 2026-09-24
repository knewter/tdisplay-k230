The named work-board generator and test commands below are proposed interfaces to create during implementation; they do not yet exist or provide evidence.

## 1. Generate an honest committed snapshot

- [x] 1.1 Add a deterministic work-data generator for committed active/archived changes, checkbox counts, revision, UTC build time, and valid links; verify `python3 tests/test_work_board.py` on real and synthetic fixture trees.
- [x] 1.2 Add a reviewed status override file and validation for lane, source/physical state, next action, dependencies, rationale, and safe public paths; cover stale, contradictory, untracked, and secret-like input failures with `python3 tests/test_work_board.py`.
- [x] 1.3 Populate reviewed overrides for current active work where checkboxes cannot express a source-landed or physical-evidence state; inspect generated data against committed proposals/evidence and run `python3 tests/test_work_board.py`.

Proof: `python3 tests/test_work_board.py` is host repository-data proof only; it does not assert device behavior.

## 2. Publish the work board

- [x] 2.1 Render `/work/` with four clear lanes, task progress, next gates, dependencies, draft/accepted labels, links, and source/physical distinctions; verify rendered HTML assertions with `python3 tests/test_work_board.py`.
- [x] 2.2 Add responsive touch-scrollable styling and links from the front door and handheld page; inspect narrow and desktop browser captures and verify link targets through `python3 scripts/build_site.py`.
- [x] 2.3 Keep accepted-spec exclusion and tally tests intact while allowing labeled proposals only on `/work/`; add a focused regression assertion and run `python3 scripts/build_site.py` within the existing 8 MiB budget.

Proof: `python3 tests/test_work_board.py` and `python3 scripts/build_site.py` prove a host site build and link/size checks, not publication.

## 3. Land and verify publication

- [x] 3.1 Commit the implementation and a concise data-provenance note; run `openspec validate the-site-shows-a-public-work-board --strict` and `python3 scripts/build_site.py` at the exact candidate revision.
- [x] 3.2 After review and push, inspect the published `/work/` URL and its front-door/handheld links at the landed revision, record URL, revision, UTC timestamp, and any deployment failure in `docs/evidence/spec-site-work-board/README.md`; verify with `python3 scripts/build_site.py`.
- [ ] 3.3 Archive and sync only after the built and published page meets every task; run `openspec validate --all --strict`, then check the resulting master, CI and Pages revision. Keep the change open if publication or evidence remains unverified.

Proof: the exact host commands above and published URL inspection. No physical board or Nix build is required for this documentation capability.
