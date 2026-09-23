# Coordinator visual review

- **Status:** PENDING — requires named coordinator review after this host audit
  is handed off.
- **Materials:** `wireframes.md`, `storyboard.md`, `interaction-contract.md`,
  and the citations in `evidence-review.md`.
- **Review questions:**
  1. Are title, state, card, and recovery hierarchy consistent across Apps,
     overview, Help, keyboard-visible, video, and system flows?
  2. Does every proposed gesture retain a visible recovery route?
  3. Are UX-01 and UX-06 scoped to an existing owner or a new narrow successor
     before implementation is authorized?
- **Evidence boundary:** This review can accept document coherence. It cannot
  close optical readability, physical reachability, motion, or cold-boot gates.

## Prepared review set

The review set now includes three parse-checked repository-native SVG sheets at
the 568×1232 target geometry: `apps-comparison.svg`,
`keyboard-comparison.svg`, and `live-card-overview.svg`. The first two compare
accepted native composition with a proposed hierarchy. The third identifies
current metadata cards and a conceptual live-card surface that remains blocked
on the card architecture decision. See `webos-comparison.md` for explicit
principle-level differences rather than a claim of webOS parity.
