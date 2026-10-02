# Recommendations — second handheld UX review

## What works in the reviewed evidence

The ordinary-reboot Home image shows a complete portrait layout with a useful
separation between the app grid, time/date, page indicator, dock and system
gesture handle. Authored dark drawer rendering has recognizable icons, concise
labels and search without heavy row outlines. The new loaded Settings captures
show consistent filled controls in both dark and light appearances. These are
pixel-level observations in the evidence classes named in [baseline](baseline.md),
not blanket glass acceptance.

## What remains unfinished

The output-picker capture has an optional visual-density question, not a
demonstrated blocked action. The current Home clock’s heavy outline/shadow
draws strong attention against the chosen wallpaper; any quieter alternative
needs user review and must preserve their background choices. Current-source
card presentation and keyboard-visible reachability are not in the new
integrated capture set. Drawer overflow/search and empty/loading/stale/error/
denied states need their own recheck; missing states are not reported as
product defects here. The three unchanged real-finger checks accepted on the
exact candidate are recorded in [operator-navigation.json](../../../evidence/boot-verification/coherent-manual-candidate/operator-navigation.json);
they were not repeated after ordinary reboot.

## webOS-inspired gap

The useful reference gap is continuity and discoverable recovery: direct
interaction should make the active object and resulting state apparent, while
common app and escape routes remain visible. Palm webOS’s card/launcher
structure and webOS OSE’s app bar/launchpad are contextual comparisons, not a
template. K230’s separate drawer, Overview, Home and fixed shell controls
should remain coherent on their own terms. No blur, stack, tile grid, extra
chrome or copied iconography is recommended by this round.

## Shared visual and interaction direction

Reuse the existing [portrait interaction contract](../interaction-contract.md)
as the shared source of truth: 568×1232 logical portrait composition; 8/16/24px
micro/control/content rhythm; 56px minimum primary target; distinct title,
state and value roles; text/state cues that do not rely on color alone; and
visible fallback for gesture routes. Keep the authored Omarchy palette,
wallpaper and icon inputs intact. Current settings/home/drawer work already
shows that quieter filled surfaces and icon-led discovery fit those rules;
the picker should reposition within them instead of adding outlines or a new
button. Card transitions should preserve the same object/context during drag
and preserve close/refusal/recovery semantics. Under reduced motion, settle
without removing the interaction or its visible result.

The performance boundary is similarly restrained: prefer layout/paint changes
that reuse current primitives. Do not add blur, shadow layers, previews, or
per-frame animation as a polish shortcut. Theme chooser evidence records that
pending thumbnail work once forced continuous redraws on the single-core board;
keep redraws tied to real state changes and any loading pulse bounded to actual
pending work. This review contains no new CPU/memory measurement, so any
renderer-heavy successor must record its own budget and rollback path.

## Next three priorities

| Order | Priority | Existing route and dependency |
| --- | --- | --- |
| 1 | Resolve reported picker cadence/release-settling concerns against a current matched baseline/candidate and complete the already-scoped motion work. | `the-shell-swaps-themes-without-a-python-stall` tasks 11.3, 17.3, 18.2 and 18.4, plus the retained wider 13/15 gates. The persistent system now has the combined source, but the old pair used a different Rust source; no fresh board timing or finger evidence is inferred here. |
| 2 | Review current card/keyboard motion and recovery as one focused integrated candidate session, reusing the exact Home/Overview/Apps/Terminal interactions already operator-accepted. | This change tasks 3.1–3.2 plus the existing card/keyboard owners. New optical/finger capture only for changed or still-unknown motion/reach claims; keep accepted behavior and avoid a redundant broad capture. |
| 3 | Reconcile theme-authored token/control/icon consistency across Home, drawer, Settings and deck without changing the user's selected Omarchy palettes, wallpaper or upstream icons. | `the-shell-loads-omarchy-themes` remaining consumer/icon coverage and `the-handheld-presents-a-coherent-shell` task 6.4; preserve each owner’s board and real-finger gates. Start with matched host captures/source review; no new borders or permanent controls. |

Priorities 2 and 3 are review/acceptance work, not claims that the
implementation is defective. The clock and picker items remain optional visual
questions, not selected work. These recommendations do not alter Omarchy
themes, colors, backgrounds or icons and do not duplicate GPU, card, recovery,
or launcher implementation proposals. This list and the findings reflect the
coordinator critique received 2026-10-01; group 3’s still-needed focused
candidate review and task 4.2 publication remain open.
