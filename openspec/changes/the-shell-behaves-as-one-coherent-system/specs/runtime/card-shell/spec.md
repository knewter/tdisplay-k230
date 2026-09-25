## ADDED Requirements

### Requirement: The card overview shows enough of each neighbor to identify it

<!-- UNVERIFIED: planning only; no implementation, host render, or board
observation exists yet. Grounding for the defect being fixed:
nix/card-shell-policy/card-shell-policy.c:29-38 (cs_default_config) and
:192-210 (deck layout), read directly against origin/master 80817e3d.
card_width = .84*(width-48) = 436.8px at the real 568px panel width; pitch =
card_width+gap = 452.8px; a neighbor at offset=1 lands at x=518.4, leaving
568-518.4 = 49.6px (8.7% of the neighbor's own width) on screen. -->

While the card overview (`CS_DECK` mode) is settled and not being dragged,
the compositor SHALL show enough of each adjacent card at the screen edges
that a person can identify which app it is — at minimum its resolved icon
badge at a legible size, once `the-handheld-presents-a-coherent-shell` task
1.4 supplies a real per-card icon — without paging to it first. The peek
width SHALL be large enough to contain that icon badge plus its existing
margin at the badge size already used in card headers, not merely a sliver
of background color. This requirement governs the idle overview's static
layout; it does not change the two-axis drag/quick-switch gesture's own
geometry or thresholds, which `the-handheld-presents-a-coherent-shell`
design decision 11 already settles separately.

#### Scenario: Two apps are open and the person reaches the overview

- **WHEN** a person reaches the settled card overview with at least one
  neighboring card in the deck
- **THEN** the neighboring card's icon badge is identifiable at the screen
  edge without a horizontal drag, at a peek width recorded and justified in
  this change's evidence rather than an unmeasured guess

#### Scenario: Only one app is open

- **WHEN** exactly one card exists in the deck
- **THEN** the overview shows that card at its existing width with no
  neighbor peek, unchanged from current behavior

#### Scenario: The overview is mid-drag

- **WHEN** a person is actively dragging the deck horizontally (the existing
  `cs_motion`/`cs_entry_motion` paths)
- **THEN** the live drag geometry and settle behavior are unchanged by this
  requirement; only the released, idle layout's peek width changes
