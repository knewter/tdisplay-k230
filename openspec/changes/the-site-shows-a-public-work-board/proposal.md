## Why

Readers can see accepted specifications and scattered progress notes, but cannot see which proposals are planned, being implemented, awaiting review or physical proof, or complete. The current spec site intentionally excludes in-flight changes, so it needs a clearly separate work view that does not present drafts as accepted capabilities.

## What Changes

- Add a public, touch-scrollable `/work/` board linked from the front door and handheld page. Its lanes distinguish planned, in progress, verification/review, and shipped/archived work.
- Generate card identities, task counts, and archive state deterministically from committed OpenSpec files at a named source revision and build time. Add a small reviewed, committed status record only where the task checklist cannot distinguish source landed from physical evidence pending.
- Show each card's next concrete action or evidence gate, dependencies, and links to its proposal, accepted spec, and relevant evidence. Expose separate source and physical-proof states where they differ, with an explicit “as of” label; a static page is not live agent telemetry.
- Keep the accepted specification ledger authoritative. A proposal shown on the work board remains marked draft and cannot silently enter the accepted requirement count.

**Non-goals:** Live agent or GitHub issue telemetry, automatic inference that checked boxes mean a deployed feature, a task-editing UI, or new hardware behavior. No physical board or Nix build is needed for this documentation change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `docs/spec-site`: permit a separately labeled proposal/work board alongside the accepted-spec ledger, with deterministic status generation and evidence-aware claims.

## Impact

The site data pass, Astro page and navigation, focused tests, and site build checks change. The generated board may link to committed proposal and evidence pages, but neither alters the OpenSpec source tree nor the spec ledger's accepted requirement count. The existing 8 MiB site budget remains in force.
