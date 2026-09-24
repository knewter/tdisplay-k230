## 1. Discover committed evidence and media

- [ ] 1.1 Add image/video and report/log discovery from change citations and associated evidence records; retain reviewed cover/provenance overrides and reject private, missing or uncommitted assets.
- [ ] 1.2 Verify discovery, duplicate handling, revision pinning, image/video selection, absent media and new media arriving before archive with `python3 tests/test_work_board.py`.

## 2. Render accessible covers, galleries and evidence menus

- [ ] 2.1 Add image/video card covers, header evidence links and inline detail galleries while retaining one whole-card action, keyboard access and no autoplay.
- [ ] 2.2 Verify generated markup and site budgets with `python3 scripts/build_site.py`; inspect desktop/mobile card and dialog behavior in a browser, including direct evidence links and a video player. Record exact commands/results in `docs/evidence/work-card-media/README.md`.

## 3. Publish and reconcile

- [ ] 3.1 Validate `openspec validate the-work-board-shows-visual-evidence --strict`, land/push and inspect CI plus the exact revision published at the work board URL.
- [ ] 3.2 Once all named proof exists, archive/sync the docs/spec-site delta and publish the reconciled result. No physical-board claim is part of this change.
