# Work card media and evidence access

Host browser proof recorded 2026-09-24 at source
`4133cdf5398db99f58fd0b3398ebfec22f288245`.

The work board discovers committed images, videos, reports and logs from
change citations and the associated evidence records. A reviewed override
selects the coherent-shell card's QEMU screenshot; it remains explicitly
labelled QEMU. The gallery and evidence menu do not alter completion or
physical verification state. New evidence is discovered on the next normal
site build, including before a proposal completes or archives.

```sh
python3 tests/test_work_board.py
python3 tests/test_render_specs.py
python3 scripts/build_site.py
python3 tests/work_card_media_browser.py
```

- Discovery: 17 tests passed, including new images and videos arriving while
  a proposal remains open, revision consistency, missing/uncommitted media,
  private sibling names, symlinks, duplicate handling and reviewed video covers.
- Spec rendering: 21 tests passed.
- Full site: 235 pages, 7,663,684 bytes, 27.96 seconds. All 12 output checks
  passed; output is below the existing 8 MiB and 120 second budgets.
- Playwright Chromium: both 1440×1000 desktop and 390×844 mobile passed cover
  coordinate clicks, inline gallery, real video playback, independent evidence
  menu, local Markdown report links, Enter/Escape and focus restoration. No
  horizontal page/dialog overflow or JavaScript errors occurred.

The browser command serves the local build and maps revision-pinned raw
media URLs to the corresponding local repository files. It actually decodes
and advances the existing system-controls MP4. This is host website behavior,
not remote deployment or a new board interaction. Reports render Markdown;
raw logs, tables and media link directly to their pinned revision to keep the
static bundle bounded. Dialog media stays inert until a card opens; videos
have controls and never autoplay.

The coordinator visually inspected these public browser captures:

![Desktop evidence menu on a whole clickable card](desktop-card.png)

![Mobile inline gallery with the QEMU provenance label](mobile-dialog.png)

Publication at <https://knewter.github.io/tdisplay-k230/work/> remains a
separate gate until the exact deployed revision is recorded here.
