# Second-round UX review: host publication

Evidence class: **host documentation and design mockups**. Recorded
2026-10-02. The review was independently checked and landed at
`9d7437b08b1c6429748af29b62b4f8a522ea8dd7`; exact-revision site run
[36967302130](https://github.com/knewter/tdisplay-k230/actions/runs/36967302130)
passed. These drawings are proposals, not newly installed device screens.

The [report](../../research/handheld-ux/review-round-2/README.md),
[baseline and identities](../../research/handheld-ux/review-round-2/baseline.md),
[findings](../../research/handheld-ux/review-round-2/findings.md),
[recommendations](../../research/handheld-ux/review-round-2/recommendations.md),
and [render commands and review corrections](../../research/handheld-ux/review-round-2/visual-review.md)
retain the distinction between current captures, older references and targets.

Annotated comparisons and motion storyboard:

- [Apps comparison](../../research/handheld-ux/review-round-2/visuals/apps.svg)
- [Cards comparison](../../research/handheld-ux/review-round-2/visuals/cards.svg)
- [Keyboard and recovery comparison](../../research/handheld-ux/review-round-2/visuals/keyboard-recovery.svg)
- [Overview to Apps storyboard](../../research/handheld-ux/review-round-2/visuals/overview-to-apps.svg)

Five host tasks are complete. Current-source journey execution and the focused
integrated-candidate recheck remain open. Publication does not close those
gates or archive the analysis. The next three priorities remain owned by
existing theme-motion, card/keyboard and theme-consumer proposals.

## Work-card discovery correction

Build-tested source: `096a66e4a7ab1925b18484d81b697cd076606af8`.

The work board previously discovered cited documents only under evidence and
design folders. The review's research folder was omitted. The discovery fix
adds cited research paths without scanning unrelated research trees. Reviewed
per-file metadata labels all four annotated sheets as design mockups; a
mixed research/capture fixture checks that a captured image keeps its own
provenance. Invalid, duplicate and conflicting metadata are rejected.

Host commands:

```sh
python3 tests/test_work_board.py
python3 scripts/render_work_board.py --working-tree --output "$HOME/tmp/k230-ux-review-publication-snapshot.json"
nix develop --command python3 scripts/build_site.py
```

Results: 22 tests passed; the snapshot exposes all four correctly labeled
sheets; the full site build passed with 503 pages, 15,026,169 bytes and 43.93
seconds, within the existing 16 MiB / 120 second budgets. The kernel auditor
independently approved the citation bounds and per-file labels. This checks
publication integrity, not physical UX acceptance.
