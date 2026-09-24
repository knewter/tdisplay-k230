## 1. Discover committed evidence and media

- [x] 1.1 Add image/video and report/log discovery from change citations and associated evidence records; retain reviewed cover/provenance overrides and reject private, missing or uncommitted assets.
- [x] 1.2 Verify discovery, duplicate handling, revision pinning, image/video selection, absent media and new media arriving before archive with `python3 tests/test_work_board.py`.

## 2. Render accessible covers, galleries and evidence menus

- [x] 2.1 Add image/video card covers, header evidence links and inline detail galleries while retaining one whole-card action, keyboard access and no autoplay.
- [x] 2.2 Verify generated markup and site budgets with `python3 scripts/build_site.py`; inspect desktop/mobile card and dialog behavior in a browser, including direct evidence links and a video player. Record exact commands/results in `docs/evidence/work-card-media/README.md`.
- [ ] 2.3 Add a viewport-sized media modal/gallery with contain sizing, swipe/keyboard navigation, video controls, Escape/close and restoration of the underlying card position/focus. Verify with `python3 tests/work_card_media_browser.py` and `python3 scripts/build_site.py`; extend the committed evidence record.
- [ ] 2.4 Open evidence files in document modals with rendered Markdown or bounded text, original-file access, Escape/close and position/focus restoration. Verify header and inline file links on desktop/mobile with `python3 tests/work_card_media_browser.py` and `python3 scripts/build_site.py`.

## 3. Publish and reconcile

- [ ] 3.1 Validate `openspec validate the-work-board-shows-visual-evidence --strict`, land/push and inspect CI plus the exact revision published at the work board URL.
- [ ] 3.2 Once all named proof exists, archive/sync the docs/spec-site delta and publish the reconciled result. No physical-board claim is part of this change.
