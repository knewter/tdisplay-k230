## MODIFIED Requirements

### Requirement: The site is rendered from the specs, and only from the specs

The accepted-spec ledger SHALL be generated from `openspec/specs/` and SHALL NOT be hand-maintained. A separately labeled public work board MAY show committed in-flight proposals, but SHALL identify them as drafts and SHALL NOT include their requirements in the accepted-spec ledger or its verification tally.

Building SHALL be a single command, and it SHALL be the same command locally
and in CI, so that what a person sees before pushing is what gets published.

*Grounding: `scripts/render_specs.py` walks `openspec/specs/**/spec.md` and
reads nothing else, on the Python standard library alone.
`scripts/build_site.py` is the one command; the workflow runs it and nothing
else. `docs/evidence/spec-site-build.txt` records both. The existing accepted
ledger test excludes in-flight change identifiers from index and capability
pages. The separate work-board allowance is planned and remains unverified
until its focused test and published page have been checked.*

#### Scenario: A capability's spec is edited

- **WHEN** a spec file changes and the site is rebuilt
- **THEN** the change appears, with no other file edited by hand

#### Scenario: An in-flight change exists

- **WHEN** the site is built while proposals are open
- **THEN** the accepted-spec ledger and requirement tally exclude it, while the separate work board may link to it with a visible draft label

## ADDED Requirements

### Requirement: A public work board explains what remains

<!-- UNVERIFIED: This site behavior is planned; host build and published-page proof are pending. -->
The documentation site SHALL provide a touch-readable work board with planned, in-progress, verification/review, and shipped/archived lanes. Each work item SHALL show its task progress, next concrete action or evidence gate, dependencies, and links to committed proposal, accepted spec, or evidence where available. Where source code has landed but physical proof remains, the two states SHALL be distinct. A checked task count alone SHALL NOT imply shipment, deployment, or physical verification.

#### Scenario: A reader looks for remaining work

- **WHEN** a reader opens the work board on a narrow touch screen
- **THEN** the reader can scroll through each lane and identify the next action and evidence gate for an open item

#### Scenario: Source is landed but board proof is pending

- **WHEN** an item's committed source is awaiting physical verification
- **THEN** the card shows both facts and remains outside the shipped/archived lane

### Requirement: Work-board status is reproducible and dated

<!-- UNVERIFIED: This generator and published-page check are planned. -->
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
