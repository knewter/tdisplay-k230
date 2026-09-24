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
