## Purpose

Defines how this project's specifications are published for reading, and what
the rendered site is obliged to tell a reader about how much of it is proven.

## ADDED Requirements

### Requirement: The site is rendered from the specs, and only from the specs

The site SHALL be generated from `openspec/specs/`, and SHALL NOT be
hand-maintained. It SHALL NOT publish in-flight proposals: a proposal is a
draft, and a published draft is read as a decision.

Rendering SHALL be a single command that needs no network and no CI, so that
reading the specs never waits on a pipeline.

*Grounding: `scripts/render_specs.py` walks `openspec/specs/**/spec.md` and
reads nothing else, on the Python standard library alone — no third-party
package, so no network. `docs/evidence/spec-site-build.txt` records the
command and its output. A test renders the real repository and asserts that no
in-flight change identifier appears anywhere in the generated tree.*

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
capability is named; a test asserts that the count's position in the generated
HTML precedes the first capability heading and the first line of capability
prose. Status is carried as a colour on every requirement and as one
proportional bar summarising the whole tree.*

#### Scenario: A reader opens the site

- **WHEN** the landing page is loaded
- **THEN** the number of unverified requirements is visible before any capability's prose

#### Scenario: A requirement carries an UNVERIFIED marker

- **WHEN** a requirement is marked unverified
- **THEN** it is rendered as unverified wherever it appears, and its stated reason is shown alongside it

### Requirement: Evidence is reachable from the requirement it grounds

Where a requirement cites a path under `docs/`, the site SHALL link to that
file. A boot log or photograph that grounds a requirement SHALL be one click
from it.

A path named only inside an `<!-- UNVERIFIED -->` marker is not a citation.
Those markers routinely name the evidence that *would* ground a requirement,
which has not been captured yet, and treating that as a citation would report
a missing file for every requirement honestly waiting on one.

*Grounding: cited files are copied into the site as their own pages, so a link
resolves wherever the site is served from rather than only inside a checkout.
A test renders a requirement citing `docs/rtsmart-boot-log.txt`, asserts every
non-external link in the generated page resolves to a file that exists, and
asserts the boot log's text is present on the page it resolves to.*

#### Scenario: A requirement cites a committed boot log

- **WHEN** that requirement is rendered
- **THEN** the cited path is a working link to the committed file

#### Scenario: A requirement cites evidence that does not exist

- **WHEN** a cited evidence path is missing from the repository
- **THEN** the build fails and names the requirement and the missing path

### Requirement: The renderer fails rather than guessing

The site depends on conventions carried in prose — the `<!-- UNVERIFIED -->`
marker and the citation of a read path as grounding. Where the renderer cannot
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

*Grounding: `docs/evidence/spec-site-build.txt` records a run over a staged
tree in which three requirements declare neither a marker nor a citation: the
command names each one and exits 2, and the landing page it wrote carries them
under "Build defects". A unit test asserts that the classifier raises on a
requirement carrying neither, rather than returning grounded.*

#### Scenario: A requirement's status cannot be determined

- **WHEN** the renderer meets a requirement it cannot classify
- **THEN** the build fails and names the file and the requirement

#### Scenario: The build has failed on an unclassifiable requirement

- **WHEN** a reader opens the site that build wrote
- **THEN** the requirement is shown as a defect rather than as grounded, and the capability it belongs to is named

### Requirement: The build stays fast and small

Generation SHALL complete within a recorded time budget and the output SHALL
stay within a recorded size budget, both enforced by the build. The budgets
SHALL be set above what the tree currently produces, so that a breach means
something changed rather than that the numbers were always tight.

*Grounding: `docs/evidence/spec-site-build.txt` records the date, the machine
and the Python version, and two measured runs — 0.017 s and 78 KiB over a tree
staging every capability the open proposals will add. The budgets in
`scripts/render_specs.py` are 5.0 s and 4 MiB, roughly 290x and 54x above
those. A test forces a breach and asserts the failure names the measured value
and the budget.*

#### Scenario: The site grows past its budget

- **WHEN** generation exceeds its time or size budget
- **THEN** the build fails and reports the measured value against the budget
