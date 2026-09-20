# docs/spec-site Specification

## Purpose
Defines how this project's specifications are published for reading, and what
the rendered site is obliged to tell a reader about how much of it is proven.

## Requirements

### Requirement: The site is rendered from the specs, and only from the specs

The site SHALL be generated from `openspec/specs/`, and SHALL NOT be
hand-maintained. It SHALL NOT publish in-flight proposals: a proposal is a
draft, and a published draft is read as a decision.

Building SHALL be a single command, and it SHALL be the same command locally
and in CI, so that what a person sees before pushing is what gets published.

*Grounding: `scripts/render_specs.py` walks `openspec/specs/**/spec.md` and
reads nothing else, on the Python standard library alone.
`scripts/build_site.py` is the one command; the workflow runs it and nothing
else. `docs/evidence/spec-site-build.txt` records both. A test renders the
real repository and asserts that no in-flight change identifier appears in any
published index or capability page.*

#### Scenario: A capability's spec is edited

- **WHEN** a spec file changes and the site is rebuilt
- **THEN** the change appears, with no other file edited by hand

#### Scenario: An in-flight change exists

- **WHEN** the site is built while proposals are open
- **THEN** nothing from those proposals appears in the output

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

<!-- UNVERIFIED: the workflow builds the site in CI, but the deployment step
has not yet succeeded: GitHub Pages is not enabled on the repository, and the
Actions token was refused when the workflow tried to enable it. Grounded once
a deployment has completed and the URL serves the page. -->

#### Scenario: A change is archived and pushed

- **WHEN** `openspec archive` adds a capability and the commit reaches the default branch
- **THEN** the published site shows that capability, and its requirements in the count, without anyone rebuilding anything

#### Scenario: A push carries a requirement the build rejects

- **WHEN** the build fails on that requirement
- **THEN** the previously published site is left standing, and the failure is attributed to the commit that caused it
