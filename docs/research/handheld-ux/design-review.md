# Coordinator visual review

Reviewed by the root coordinator on 2026-09-23. Status: accepted as an audit and
successor-facing design contract; proposed pixels are not shipped behavior.

The review inspected the native launcher empty/stale captures and the retained
keyboard, Apps, and overview evidence cited by the audit, and rendered all three
SVG sheets at their declared dimensions. The current panels are explicitly dated
schematics. Proposed keyboard-visible composition retains New terminal and page
navigation; its footer stays above the reserved keyboard area. The Apps sheet
illustrates action wording, not the entire future installed-app inventory.

The review required corrections before acceptance: remove the battery-only boot
target (the user has no battery); ground actual product issues instead of treating
missing footage as a UI defect; preserve keyboard paging and built-ins; label
schematic provenance; fix text layout; and treat persistent-bar placement as a
design choice while preserving visible recovery. P0/P1 implementation is routed
to two bounded successors plus the existing card/video owners. The cold USB boot
timing gap remains an explicit future observation rather than a fabricated P1
usability failure.

The current overview remains metadata-only. The proposed live-card schematic
cannot prove global shrink, finger tracking, adjacent-card continuity, or
throw-close/refusal; those are owned by the card architecture and product changes.
Reduced motion preserves those core interactions. The source color ratios and
minimum geometry are review criteria; actual optical readability, edge reach,
physical motion, and unmeasured startup timing remain UNVERIFIED. This document
accepts planning coherence, not those hardware claims.
