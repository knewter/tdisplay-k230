# Findings — second handheld UX review

Findings use stable IDs for this round. Severity is user impact when the
current artifact demonstrates it; confidence describes support for the
diagnosis, not certainty about physical impact. Evidence absence is recorded
as an evidence gap rather than a defect.

| ID | Finding and reproducible state | Severity / confidence | Correction, existing owner, dependency, effort | Observable acceptance and remaining gate |
| --- | --- | --- | --- | --- |
| UX2-01 | The current Home capture shows a large stacked time with conspicuous dark stroke/shadow over a bright, detailed wallpaper. Relative to the quieter typographic clock in the authored [interaction study](../../../design/handheld-prototype/README.md), the clock attracts more weight than the current app grid and the study’s hierarchy suggests. This is a subjective polish comparison, not a functional failure. | P3 optional refinement / medium confidence in the pixel comparison; impact unknown | Ask the user whether a quieter clock treatment is desired. Preserve the selected wallpaper and palette; test a lighter outline/shadow or other existing clock style only as a labeled proposal. Owner: Home clock appearance in `the-shell-presents-a-pinned-home-screen`; design input in `docs/design/clock-widget-research.md`. Effort: small visual exploration; no hardware claim. | Compare current and proposal over the same bright/dark wallpaper without reducing legibility; keep unchanged unless the user accepts the visual direction. Physical contrast needs glass review. |
| UX2-02 | Current-source card deck appearance is not represented by a reviewed capture in this baseline. The available [Overview image](../../../evidence/home-screen/navigation/overview.png) is source `f39cb7eb`, while the persistent system is source `5bb67db128210f830dab4de0d20a4b0eca13c578`. | No severity assigned; confidence high that evidence is missing | No pixel correction inferred. Owner: integrated card candidate recheck in this change’s task group 3, coordinated with card/compositor owners. Dependency: serialized board/candidate capture. Effort: one focused review session. | Capture current-source Overview and inspect native pixels. The three exact-candidate operator-accepted real-finger checks are in [operator-navigation.json](../../../evidence/boot-verification/coherent-manual-candidate/operator-navigation.json); this review does not repeat them or extend them to other card interactions. |
| UX2-03 | The output picker in [the board native capture](../../../evidence/shell-polish/settings-volume-layout/board/output-picker.png) overlays Keyboard/Motion rows and displays a second volume slider beside the underlying Settings control. This demonstrates layout/content density, not a blocked action; overlays normally cover background content. | No severity assigned; optional refinement only; user impact `UNVERIFIED` | Keep current selection semantics and authored theme. Consider reducing redundant volume presentation or adjusting contrast/placement only if a finger review finds confusion or obstruction. Owner: Rust Settings/output-picker route under `the-handheld-presents-a-coherent-shell`; physical follow-up includes that proposal’s 6.4. Effort: visual review first; no source change authorized by this finding. | Review the opened/closed state with actual finger input. If unrelated control access and dismissal are clear, retain current layout. Current evidence is native capture plus injected input, not finger acceptance. |
| UX2-04 | The drawer’s current authored-theme render leaves a large quiet lower area after eight entries. The available host render does not show catalog overflow. | No severity assigned; low confidence as a usability problem | Do not compress or add permanent controls based only on whitespace. Existing owner: `the-launcher-explains-app-actions`. Dependency: representative long-list fixture/current board capture. Effort: evidence-only until a concrete discovery failure appears. | Show a realistic larger installed catalog and verify scroll/search, with existing target sizes retained. Do not carry forward old full-width generic-row recommendations as current defects. |

## Reconciled and superseded audit claims

- The September visual-gap audit’s outlined generic full-width launcher rows
  predate the current icon-grid authored render. Keep the desire for
  real-catalog overflow coverage; retire its row-layout recommendation.
- Earlier Settings dead-space and uneven-row-spacing findings are superseded
  for the loaded volume/settings states shown in the 2026-10-01 physical
  dark/light captures. Do not generalize this to every Settings route.
- Earlier “Settings still loading” evidence is stale for the captured current
  source. Conversely, the new picker overlap is current native evidence, not a
  claim about finger difficulty.
- Older card title/identity/motion findings cannot be confirmed or cleared by
  the current Home-only image. Keep those owners’ source-level and physical
  gates intact; this review adds no card implementation claim.
- Prior user decisions remain constraints: preserve theme/wallpaper/icon
  choices; no permanent extra buttons/borders; long-press remains grab/drag;
  mouse secondary click is the app menu. They are not new acceptance of other
  current journeys.
- The user's exact-candidate real-finger report accepts Home→All apps,
  handle→Overview, and Terminal open/return for this exact `p1a1hz` / `3hy6`
  source after manual matching-kernel boot. Ordinary reboot later preserved
  those exact identities; it did not repeat the gestures. Reuse those accepted
  observations without widening them to Home editing, search, keyboard,
  card-motion, or mouse-menu acceptance.

## Independent coordinator review

The root coordinator reviewed the captures, journey and findings draft on
2026-10-01. The first review rejected the picker as a demonstrated failure;
this revision treats it only as optional density/consistency work and keeps
physical impact `UNVERIFIED`. It also added the exact-source operator-accepted
Home/Overview/Apps/Terminal interactions and the subjective Home-clock
hierarchy comparison, then reordered priorities around the measured picker
motion gap, remaining integrated card/keyboard recheck, and existing theme
consumer consistency work. The final sheet corrections are recorded in
[visual-review.md](visual-review.md). The coordinator agrees the host critique
and reconciliation are sufficient for tasks 2.1 and 2.3. No disagreement
remains on the scope or severity of the four findings; all physical and
unexercised journey limits remain explicit.


## Candidate recheck — 2026-10-09

[The current recheck](candidate-recheck.md) reviews all four findings on the
identified normal runtime. No P0/P1 severity was assigned or newly established.
UX2-02's missing current Overview image is resolved for the observed one-card
state; UX2-04 now has a 19-entry installed-catalog capture. Clock/picker ideas
remain optional, and no optical/motion/overflow assertion is added. Existing
implementation and physical owners retain their gates.
