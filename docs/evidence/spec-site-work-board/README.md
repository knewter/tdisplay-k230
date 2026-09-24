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

The first production-prefix build used candidate revision `7ed1dd56a8bbfa10927426473c9cff49e4101b45`. After the final task-count and dependency-cycle correction, `01d84a43b4b4cb7dda721be4bc2dc53501637a00` passed the same full build: 155 pages, 4,908,560 bytes, 7.25 s. Its generated board contains 6 planned, 7 in-progress, 2 verification/review and 16 archived changes. The splash change counts 20/27 tasks, including alphanumeric subgroup IDs; the launcher gesture change counts 15/16. Chromium host previews at 1440×1100 and 568×1232 were inspected for column and stacked-lane readability. These are browser layout checks, not photographs of the handheld. No board or Nix build was used.

## Published observation

Commit `95595a8e73a8670e462301acf6becfd8739f422d` reached the default branch. [Pages run 35946341170](https://github.com/knewter/tdisplay-k230/actions/runs/35946341170) completed successfully with build and deploy jobs successful; the coordinator's integrated host build measured 155 pages, 4,908,561 bytes and 36.03 s. At 2026-09-24 02:15:44–45 UTC, independent HTTPS reads returned HTTP 200 for [the work board](https://knewter.github.io/tdisplay-k230/work/), [front door](https://knewter.github.io/tdisplay-k230/) and [handheld page](https://knewter.github.io/tdisplay-k230/handheld/). The work HTML included source revision `95595a8e73a`, four lanes, separate source/device proof labels, splash 20/27 and launcher 15/16; front door and handheld each linked `/tdisplay-k230/work/`. The HTML contained no private workstation path tokens checked by the audit (`/home/`, `/mnt/`, `/tmp/`, `/dev/tty`).

| Published path | SHA-256 of HTTP response body |
| --- | --- |
| `/tdisplay-k230/work/` | `53d59be4d976224a32ffa011d0c0deead96e7bfc63ef68b5966c7ab1813cb7dd` |
| `/tdisplay-k230/` | `656915091fa3031376e7438d6f5f8831485f7e94268560c4f8060b0a05900929` |
| `/tdisplay-k230/handheld/` | `dc3668f5e5747a34920f2094dd9dff67264adecc46f00f20ea90c3e1a815bd2e` |

This is site publication proof for the named revision, not device or live-agent evidence. A later source/task update requires a new build and deployment check; the status override revision may remain an earlier reviewed ancestor rather than the snapshot commit itself.

## In-dashboard detail implementation

The detail view is generated from the same captured Git revision as the board. The generator preflights each committed Markdown blob's size before reading it, caps it at 128 KiB, and rejects missing or private document text. The page renders each proposal, design, tasks and delta spec into a native dialog. Each whole card is a detail link; related records appear inside the dialog, and pinned GitHub files are secondary source references. Relative links resolve only to tracked targets in the captured revision, with published evidence routed to local pages. Unsafe schemes, private hosts and images without a published asset fail the build.

At candidate `34101fb7`, `python3 tests/test_work_board.py` passed 14 cases covering dirty trees, revision pinning, a sparse oversized blob and invalid documents. `node tests/test_work_markdown_links.mjs` passed 15 link assertions. The full `python3 scripts/build_site.py` produced 155 pages and 5,875,221 bytes in 12.25 seconds, including 11 built-site assertions, under the unchanged 8 MiB and 120-second budgets. The follow-up `7a06dbaf` accepted ordinary public HTTPS citations without a hardcoded domain list; its 20 link assertions and full build passed, with 155 pages, 5,875,221 bytes in 7.69 seconds. These are host checks, not device observations.

Chromium host inspection at 568×1232 and 1440×900 opened a selected card, observed rendered Markdown table and four sections, and confirmed no horizontal overflow or JavaScript errors. Escape and browser Back closed the detail; a direct `?work=the-shell-trials-vglite-composition&doc=1` URL opened it; Close removed the selection; focus returned to the selected card control. Body scrolling stayed locked while the modal was open. The responsive captures were inspected locally; they are not handheld photographs.

[Pages run 35948253404](https://github.com/knewter/tdisplay-k230/actions/runs/35948253404) deployed commit `bb6b53c79c3bb0b323599892f58403b594aa0b66` successfully. At 2026-09-24 02:42:21 UTC an HTTPS read of [the work board](https://knewter.github.io/tdisplay-k230/work/) returned HTTP 200, SHA-256 `d52a547f0c18fa2b43c7e7874043944436f7712c5ce71f010896effa39c84a0b`, and HTML reporting the same revision with the detail dialog, selected-item document, formatted Markdown and local evidence URLs. Chromium at 568×1232 directly opened that revision's `?work=the-shell-trials-vglite-composition&doc=1`, found four document sections and a rendered table, and closed with Escape back to `/work/` while returning focus. No JavaScript errors or horizontal overflow were observed. This proves the detail feature's publication at that revision; a subsequent whole-card activation refinement is separately verified below before archive.

The reader-requested whole-card interaction landed as `a8b3c747b7ec56324336fd11c99c0f215c734cd3`. Its [Pages run 35948704810](https://github.com/knewter/tdisplay-k230/actions/runs/35948704810) passed build and deployment. At 2026-09-24 02:49:23 UTC the [published board](https://knewter.github.io/tdisplay-k230/work/) returned HTTP 200, reported that exact revision, and had SHA-256 `f616834deb38c07a4b69f05d2ede8ccb3db5a43bb80b40e2d206fcc06cffc82c`. The HTML had 31 native card links, zero `card-open` controls, and local evidence URLs. Chromium at 568×1232 focused a card, opened it with Enter, read four document sections, related record links and a rendered table, then closed it with Escape. Focus returned to that card, the query selection cleared, and no JavaScript error or horizontal overflow occurred. The host preview also passed whole-card mouse activation, Ctrl-click opening a direct detail URL in a new tab, browser Back and focus restoration at 568×1232 and 1440×900. These observations establish website behavior at the stated revisions; they do not imply board or image verification.
