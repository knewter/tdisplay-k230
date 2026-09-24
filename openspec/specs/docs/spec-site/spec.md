# docs/spec-site Specification

## Purpose
Defines how this project's specifications are published for reading, and what
the rendered site is obliged to tell a reader about how much of it is proven.

## Requirements

### Requirement: The site is rendered from the specs, and only from the specs

The accepted-spec ledger SHALL be generated from `openspec/specs/` and SHALL NOT be hand-maintained. A separately labeled public work board MAY show committed in-flight proposals, but SHALL identify them as drafts and SHALL NOT include their requirements in the accepted-spec ledger or its verification tally.

Building SHALL be a single command, and it SHALL be the same command locally
and in CI, so that what a person sees before pushing is what gets published.

*Grounding: `scripts/render_specs.py` walks `openspec/specs/**/spec.md` and
reads nothing else, on the Python standard library alone.
`scripts/build_site.py` is the one command; the workflow runs it and nothing
else. `docs/evidence/spec-site-build.txt` records both. The existing accepted
ledger test excludes in-flight change identifiers from index and capability
pages. `docs/evidence/spec-site-work-board/README.md` records the focused
work-board tests and the published page at revision `95595a8e`.*

#### Scenario: A capability's spec is edited

- **WHEN** a spec file changes and the site is rebuilt
- **THEN** the change appears, with no other file edited by hand

#### Scenario: An in-flight change exists

- **WHEN** the site is built while proposals are open
- **THEN** the accepted-spec ledger and requirement tally exclude it, while the separate work board may link to it with a visible draft label

### Requirement: The site leads with what is unproven

Every requirement SHALL be shown as either grounded or unverified. The landing
page SHALL state how many requirements are unverified before it presents
anything else.

This is the site's reason to exist. On this board the documentation and the
hardware disagree routinely — a datasheet described a working radio whose
enable line is never driven, and a vendor page described the Wi-Fi as an
ESP32-S3 that the schematic contradicts. A reader's first question is which
claims have been observed, and the site SHALL answer it without being asked.

*Grounding: the landing page's `<h1>` is the count itself, emitted before any
capability is named. Tests against the built site assert that the count's
position in the HTML precedes every capability name and every section heading,
and that the number printed matches what the spec tree actually contains
rather than what the page claims. Status is carried as a colour on every
requirement and as one proportional bar summarising the whole tree, in both
light and dark.*

#### Scenario: A reader opens the site

- **WHEN** the landing page is loaded
- **THEN** the number of unverified requirements is visible before any capability's prose

#### Scenario: A requirement carries an UNVERIFIED marker

- **WHEN** a requirement is marked unverified
- **THEN** it is rendered as unverified wherever it appears, and its stated reason is shown alongside it

### Requirement: Evidence is reachable from the requirement it grounds

Where a requirement cites a path under `docs/`, the site SHALL link to that
file. A boot log or photograph that grounds a requirement SHALL be one click
from it, for a reader on the web and not only in a checkout.

A path named only inside an `<!-- UNVERIFIED -->` marker is not a citation.
Those markers routinely name the evidence that *would* ground a requirement,
which has not been captured yet, and treating that as a citation would report
a missing file for every requirement honestly waiting on one.

*Grounding: cited files are rendered into the site as pages of their own, and
listed on the landing page under "Evidence on file". A test walks every built
page and asserts that every link resolves to a file that exists. Another
asserts that a cited path has a page. `docs/rtsmart-boot-log.txt` reaches the
site with the two NUL bytes a serial capture left in it shown rather than
removed.*

#### Scenario: A requirement cites a committed boot log

- **WHEN** that requirement is rendered
- **THEN** the cited path is a working link to the committed file

#### Scenario: A requirement cites evidence that does not exist

- **WHEN** a cited evidence path is missing from the repository
- **THEN** the build fails and names the requirement and the missing path

### Requirement: The renderer fails rather than guessing

The site depends on conventions carried in prose — the `<!-- UNVERIFIED -->`
marker and the citation of a read path as grounding. Where the build cannot
determine a requirement's verification status, it SHALL fail and name the file
and the requirement, rather than rendering it as grounded.

A silent default would make the count of unverified requirements untrustworthy,
and that count is the only reason to build this.

Failing SHALL mean a non-zero exit that names every such requirement. It SHALL
NOT mean withholding the site: the output is still written, and a requirement
that declared no status is shown on it as a defect, in its own colour, with the
capability it came from. A front door that reports "three requirements never
said" is more useful than no front door, and a defect nobody can see is one
nobody fixes.

Quoting a convention SHALL NOT count as using it. A requirement discussing the
marker inside a code span is not thereby unverified.

*Grounding: `docs/evidence/spec-site-build.txt` records a run over a staged
tree in which three requirements declare neither a marker nor a citation: the
command names each one and exits non-zero, and the page it wrote carries them
under "Build defects". Unit tests assert that the classifier raises on a
requirement carrying neither rather than returning grounded, and that a marker
quoted in a code span is not read as a marker — a bug the first real build
produced, which reported two grounded requirements as unverified.*

#### Scenario: A requirement's status cannot be determined

- **WHEN** the build meets a requirement it cannot classify
- **THEN** the build fails and names the file and the requirement

#### Scenario: The build has failed on an unclassifiable requirement

- **WHEN** a reader opens the site that build wrote
- **THEN** the requirement is shown as a defect rather than as grounded, and the capability it belongs to is named

### Requirement: The build stays fast and small

Generation SHALL complete within a recorded time budget and the output SHALL
stay within a recorded size budget, both enforced by the build. The budgets
SHALL be set above what the tree currently produces, so that a breach means
something changed rather than that the numbers were always tight.

*Grounding: `docs/evidence/spec-site-build.txt` records the date, the machine,
the Python, Node and Astro versions, and the measured build. The budgets in
`scripts/build_site.py` are set well above it, with the headroom stated and
the reason for it. A test forces a breach and asserts the failure names the
measured value and the budget.*

#### Scenario: The site grows past its budget

- **WHEN** generation exceeds its time or size budget
- **THEN** the build fails and reports the measured value against the budget

### Requirement: The published site is current without anyone maintaining it

The site SHALL be published at a URL, and that URL SHALL be rebuilt from
`openspec/specs/` on every push to the default branch. A reader SHALL NOT have
to clone the repository or run anything to learn what is unproven.

A build that fails SHALL NOT be published. The count on the URL is only worth
reading if it could not have been published while the specs were in a state
the build rejects.

*Grounding: observed from a machine that is not the build host, over one
push. Before: `https://knewter.github.io/tdisplay-k230/` served
"generated 2026-09-21 02:55 UTC" and "1 of 11 requirements is unverified".
Commit `e70934a` was pushed to `main` at 2026-09-22 00:21 UTC. Fifty-odd
seconds later the same URL served "generated 2026-09-22 00:21 UTC", "1 of 18
requirements is unverified" and six capability pages, with nothing else done
by anyone. Recorded in `docs/evidence/spec-site-build.txt`, which also
records that the previous day's failing builds were not published — the URL
served the last good build across five pushes while the tree was in a state
the build rejects — as an inference from what the URL served rather than
from the CI logs, which were not read.*

#### Scenario: A change is archived and pushed

- **WHEN** `openspec archive` adds a capability and the commit reaches the default branch
- **THEN** the published site shows that capability, and its requirements in the count, without anyone rebuilding anything

#### Scenario: A push carries a requirement the build rejects

- **WHEN** the build fails on that requirement
- **THEN** the previously published site is left standing, and the failure is attributed to the commit that caused it

### Requirement: A public work board explains what remains

*Grounding: `docs/evidence/spec-site-work-board/README.md` records the host layout and link checks and the published four-lane page at revision `95595a8e`.*
The documentation site SHALL provide a touch-readable work board with planned, in-progress, verification/review, and shipped/archived lanes. Each work item SHALL show its task progress, next concrete action or evidence gate, dependencies, and links to committed proposal, accepted spec, or evidence where available. Where source code has landed but physical proof remains, the two states SHALL be distinct. A checked task count alone SHALL NOT imply shipment, deployment, or physical verification.

#### Scenario: A reader looks for remaining work

- **WHEN** a reader opens the work board on a narrow touch screen
- **THEN** the reader can scroll through each lane and identify the next action and evidence gate for an open item

#### Scenario: Source is landed but board proof is pending

- **WHEN** an item's committed source is awaiting physical verification
- **THEN** the card shows both facts and remains outside the shipped/archived lane

### Requirement: Work-board status is reproducible and dated

*Grounding: `docs/evidence/spec-site-work-board/README.md` records the committed generator tests, exact build, published revision and link observations.*
The work board SHALL be generated from committed repository state at an identified revision and build time. Any status that cannot be derived from proposal, task, archive, or evidence files SHALL come from a reviewed committed override with a rationale and source link. Missing or inconsistent overrides and broken links SHALL fail the build. The page SHALL describe itself as a dated snapshot, not live task or agent telemetry, and SHALL exclude private workstation paths, addresses, credentials, and uncommitted work.

#### Scenario: A proposal task changes

- **WHEN** a committed task checkbox changes and the site rebuilds
- **THEN** the work board updates its count for that revision without changing a second hand-maintained count

#### Scenario: A status claim needs human review

- **WHEN** source-landed or physical-proof status cannot be derived from the checklist
- **THEN** the published claim appears only if a committed, linked status override supplies its basis

#### Scenario: A public link is stale

- **WHEN** a work-board link points to a file the site cannot publish
- **THEN** the build fails with the work item and link named

### Requirement: A work card opens its committed detail inside the dashboard

*Grounding: `docs/evidence/spec-site-work-board/README.md` records the bounded source and Markdown tests, browser interaction checks, and successful Pages deployment of the whole-card detail at revision `a8b3c747`.*
The work board SHALL make each entire card a single keyboard-accessible control that opens its committed proposal, design, tasks and delta specification inside the dashboard, with readable headings, tables, code and links rather than raw source text. The detail SHALL identify the same status, task progress and snapshot revision as the card. Published evidence links SHALL remain on the site where a local evidence page exists, and pinned external source links SHALL be secondary. The reader SHALL be able to close the detail with touch, keyboard Escape or browser Back and return focus to the selected card; a direct detail URL SHALL reopen the item. The detail SHALL use only committed content from the displayed snapshot, without a live GitHub fetch.

#### Scenario: A reader opens a card

- **WHEN** the reader taps a card or activates it from the keyboard
- **THEN** a scrollable in-dashboard detail shows formatted proposal, design, tasks and delta spec sections for that card

#### Scenario: A reader returns to the board

- **WHEN** the reader closes the detail, presses Escape or navigates Back
- **THEN** the detail closes and focus returns to the selected card without losing the board position

#### Scenario: A reader follows a direct item URL

- **WHEN** the board opens with a valid work-item selection in its URL
- **THEN** that item's detail opens using the same revision as the visible board

### Requirement: Work cards expose their visual evidence
<!-- UNVERIFIED: host-browser and published-site proof is recorded in docs/evidence/work-card-media/README.md; this is not physical K230 grounding. -->
The work board SHALL discover committed images and videos associated with a change's cited evidence, show a representative visual cover when available, and present the discovered media inside that card's detail view. Videos SHALL provide playback controls, start playback when opened or selected in the media viewer, and support Space to toggle play/pause without closing it. Card previews SHALL remain paused. Captions and evidence-class labels SHALL not imply physical validation from mockups or automated captures. Changes without visual evidence SHALL remain readable text cards.

#### Scenario: Screenshot and video arrive during implementation
- **WHEN** screenshot or video evidence is committed for an open change and the site publishes that revision
- **THEN** the card and detail view expose the new media without waiting for task completion or archive

#### Scenario: A reader opens a card
- **WHEN** the reader clicks the card outside its evidence links or activates its primary link by keyboard
- **THEN** the existing inline detail view opens with its media and documents, without a separate View details button

#### Scenario: Enlarge media while reading a card
- **WHEN** the reader activates an image or the enlarge action for a video in the card detail
- **THEN** a gallery modal displays that media at the largest size that fits the viewport while preserving its aspect ratio, supports adjacent-media navigation by touch swipe and arrow keys, and returns to the same card position when closed

### Requirement: Card headers expose related evidence records
<!-- UNVERIFIED: host-browser and published-site proof is recorded in docs/evidence/work-card-media/README.md; this is not physical K230 grounding. -->
Each work card with related evidence SHALL expose directly usable evidence links from its header area, including reports, logs, screenshots and videos. Those links SHALL identify their artifacts, refer to the published revision, and remain separately usable from the primary whole-card action. Discovery SHALL exclude uncommitted, missing, unsafe and unrelated paths.

#### Scenario: Open a report from a card header
- **WHEN** the reader activates a report or log in the card's header evidence menu
- **THEN** the named evidence opens in a document modal over the board, with Markdown rendered and text readable, without replacing the board with a raw URL; closing restores the reader's place and an explicit original-file link remains available
