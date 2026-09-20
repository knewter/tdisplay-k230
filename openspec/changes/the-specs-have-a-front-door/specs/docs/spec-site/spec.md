## Purpose

Defines how this project's specifications are published for reading, and what
the rendered site is obliged to tell a reader about how much of it is proven.

## ADDED Requirements

### Requirement: The site is rendered from the specs, and only from the specs

<!-- UNVERIFIED: no renderer exists yet. -->

The site SHALL be generated from `openspec/specs/`, and SHALL NOT be
hand-maintained. It SHALL NOT publish `openspec/changes/`: an in-flight
proposal is a draft, and a published draft is read as a decision.

Rendering SHALL be a single command that needs no network and no CI, so that
reading the specs never waits on a pipeline.

#### Scenario: A capability's spec is edited

- **WHEN** a spec file changes and the site is rebuilt
- **THEN** the change appears, with no other file edited by hand

#### Scenario: An in-flight change exists

- **WHEN** the site is built while `openspec/changes/` is non-empty
- **THEN** nothing from those changes appears in the output

### Requirement: The site leads with what is unproven

<!-- UNVERIFIED: no renderer exists yet. -->

Every requirement SHALL be shown as either grounded or unverified. The landing
page SHALL state how many requirements are unverified before it presents
anything else.

This is the site's reason to exist. On this board the documentation and the
hardware disagree routinely — a datasheet described a working radio whose
enable line is never driven, and a vendor page described the Wi-Fi as an
ESP32-S3 that the schematic contradicts. A reader's first question is which
claims have been observed, and the site SHALL answer it without being asked.

#### Scenario: A reader opens the site

- **WHEN** the landing page is loaded
- **THEN** the number of unverified requirements is visible before any capability's prose

#### Scenario: A requirement carries an UNVERIFIED marker

- **WHEN** a requirement is marked unverified
- **THEN** it is rendered as unverified wherever it appears, and its stated reason is shown alongside it

### Requirement: Evidence is reachable from the requirement it grounds

<!-- UNVERIFIED: no renderer exists yet. -->

Where a requirement cites a path under `docs/evidence/`, the site SHALL link
to that file. A boot log or photograph that grounds a requirement SHALL be one
click from it.

#### Scenario: A requirement cites a committed boot log

- **WHEN** that requirement is rendered
- **THEN** the cited path is a working link to the committed file

#### Scenario: A requirement cites evidence that does not exist

- **WHEN** a cited evidence path is missing from the repository
- **THEN** the build fails and names the requirement and the missing path

### Requirement: The renderer fails rather than guessing

<!-- UNVERIFIED: no renderer exists yet. -->

The site depends on conventions carried in prose — the `<!-- UNVERIFIED -->`
marker and the `docs/evidence/` citation form. Where the renderer cannot
determine a requirement's verification status, it SHALL fail and name the
requirement, rather than rendering it as grounded.

A silent default would make the count of unverified requirements untrustworthy,
and that count is the only reason to build this.

#### Scenario: A requirement's status cannot be determined

- **WHEN** the renderer meets a requirement it cannot classify
- **THEN** the build fails and names the file and the requirement

### Requirement: The build stays fast and small

<!-- UNVERIFIED: no renderer exists yet, so no budget has been measured. -->

Generation SHALL complete within a recorded time budget and the output SHALL
stay within a recorded size budget, both enforced by the build. The budgets
SHALL be set above what the tree currently produces, so that a breach means
something changed rather than that the numbers were always tight.

#### Scenario: The site grows past its budget

- **WHEN** generation exceeds its time or size budget
- **THEN** the build fails and reports the measured value against the budget
