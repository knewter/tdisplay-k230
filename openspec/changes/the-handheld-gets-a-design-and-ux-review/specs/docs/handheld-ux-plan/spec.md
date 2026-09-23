## ADDED Requirements

### Requirement: The project SHALL provide a repeatable whole-product design critique

<!-- UNVERIFIED: the second-round critique has not been performed. -->

The documentation SHALL expose a dated design and UX review spanning shell, launcher, cards, keyboard, terminal, media, Help, System, startup, and recovery. It SHALL assess visual consistency and complete user journeys using a reusable rubric. Each finding SHALL distinguish functional status, design quality, evidence confidence, and unobserved behavior, and identify the reviewed revision and installed or experimental artifact. Documentation owns the critique; runtime owners retain implementation responsibility.

#### Scenario: A reviewer asks whether the shell is refined
- **WHEN** the reviewer opens the design review
- **THEN** they can identify working flows, specific sources of friction, visual inconsistencies, and missing observations without interpreting passed implementation tests as design acceptance

#### Scenario: A surface is available only in an experimental package
- **WHEN** the review compares that surface with the installed shell
- **THEN** its status and artifact are labelled separately and the review does not describe it as a shipped default

### Requirement: Design recommendations SHALL include inspectable visual and interaction comparisons

<!-- UNVERIFIED: new comparisons and their critique remain to be created. -->

The review SHALL provide at least three annotated current-versus-target comparisons covering Apps, cards, and keyboard/recovery composition, plus a transition storyboard. It SHALL identify reference sources and observed interaction principles, including a concrete comparison with the intended webOS-inspired experience. Proposed layouts SHALL be marked as proposals, and recommendations SHALL explain user benefit, consistency with the shared visual/touch contract, and relevant performance constraints.

#### Scenario: A reviewer evaluates a proposed refinement
- **WHEN** they inspect the corresponding comparison at the panel's portrait geometry
- **THEN** they can see the current issue, proposed correction, affected journey, and implementation owner, and can distinguish a drawing from a device capture

#### Scenario: A reference interaction needs unproved hardware support
- **WHEN** a recommendation depends on rendering or timing that has not been demonstrated
- **THEN** the review records that dependency and a usable fallback or deferral instead of claiming the effect is achievable on this board

### Requirement: A review round SHALL close with a candidate recheck and owned next work

<!-- UNVERIFIED: candidate recheck, independent critique, and successor reconciliation remain open. -->

The review SHALL retain an independent critique, severity-ranked findings with separate confidence, and a recheck of P0/P1 findings against an identified integrated candidate. Each finding SHALL identify an existing owner or a bounded successor, an observable acceptance condition, dependencies, and whether it can proceed without the board. Unimplemented or physically unverified findings SHALL remain explicit. The report SHALL name the next three implementation priorities and ensure new priority proposals are validated and published on master.

#### Scenario: Parallel work is scheduled
- **WHEN** the coordinator selects the next tranche
- **THEN** the report identifies disjoint research or implementation ownership, integration dependencies, and serialized board needs without duplicating existing proposal scope

#### Scenario: The candidate still has an unresolved design issue
- **WHEN** the reviewer compares the candidate with the baseline
- **THEN** the report records the remaining issue and owner without marking the runtime requirement complete merely because the analysis round is complete

#### Scenario: Only native or injected evidence is available
- **WHEN** the review reaches a judgment about physical motion, touch reach, or optical readability
- **THEN** that judgment remains UNVERIFIED unless matching real-finger or optical evidence is cited, and earlier accepted observations are reused only for unchanged behavior
