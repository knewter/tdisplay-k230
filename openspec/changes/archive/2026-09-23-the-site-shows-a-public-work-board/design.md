## Context

See proposal.md. The existing userspace site build renders archived `openspec/specs/` through `scripts/render_specs.py`; its accepted-spec index intentionally rejects active proposal IDs. OpenSpec tasks and archive directories are committed repository data, while source-landed, review, and physical-proof states are not always represented by checkboxes. The current site has an 8 MiB output budget and is statically published.

## Goals / Non-Goals

**Goals:** A legible public snapshot that answers what is planned, underway, awaiting evidence, or shipped; every claim traceable to a committed revision and accessible source. Preserve the accepted-spec ledger's meaning.

**Non-goals:** Live worktree or agent tracking, auto-promoting checklist completion to deployed status, querying private CI/board state at page load, editing tasks from the browser, or new device behavior. Layer: documentation userspace and its static build, not Nix image or board runtime.

## Decisions

1. **Separate generator and page.** Add a deterministic work-data pass beside `render_specs.py`, reading committed active changes, archived changes, and a small reviewed status file. Render `/work/` from generated data in Astro; link it from index and handheld. The accepted-spec generator and requirement tally remain sourced solely from `openspec/specs/`. Rejected alternative: inserting active proposals into the existing spec index, which would make drafts look accepted and weaken its current test.

2. **Stable lane classification with an explicit exception file.** Archive means shipped/archived only when committed proof and deployment state are recorded; archived status alone means the OpenSpec work closed, so the card should name any residual deployment limit. Active zero-progress proposals are planned. Active checked tasks with incomplete work are in progress unless a reviewed status record identifies a specific review or evidence gate, when they enter verification/review. The override records change ID, lane, source state, physical state (or not applicable), next action, dependency IDs, evidence links, rationale, and review revision. Task totals and links are derived, never duplicated. Schema validation rejects unknown IDs, stale paths, empty next steps, contradictory archived state, and unsupported status terms. Rejected alternative: checkbox ratios as shipment state, because several changes land source before physical verification.

3. **Committed snapshot provenance.** Embed the source Git revision and UTC build time in generated data and page. Read tracked files at the build revision rather than neighboring worktrees or live process state. Stable sort by lane, priority/updated date, then ID; a content diff should reflect a source or reviewed override change. Rejected alternative: live GitHub API or agent telemetry, which adds network dependence and can reveal private work.

4. **Links and public safety.** Link proposal pages, accepted capability pages, and published `docs/evidence/` pages through existing URL helpers. Use only repository-relative, tracked paths; reject absolute paths, traversal, remote private URLs, and known secret-bearing fields. The source override carries display-safe text, and the generated JSON is inspected by a test. Do not mirror uncommitted task logs. Existing site link checks include the work page. A proposal link is a labeled draft and never added to the accepted index. Rejected alternative: raw Markdown task dump, which is hard to scan and can expose local details.

5. **Responsive Kanban layout.** On wide screens, four aligned columns allow comparison; at narrow widths, lanes stack in document order with scroll position and clear headings. Each card shows its title, badge, `done/total`, separate source/physical status if relevant, next gate, dependencies, and compact links. Use native links and CSS; no drag-and-drop or client data fetch is required. Preserve keyboard focus, contrast, and comfortable tap targets. Rejected alternative: horizontally clipped four-column board on the 568-pixel panel.

6. **In-dashboard card detail.** Include proposal, design, task and delta-spec text from the same committed Git snapshot in generated data. Render it at build time with the site's existing Markdown processor, escaping raw HTML and resolving repository-relative evidence links to local evidence pages when published. Missing or oversized source inputs fail with the item/path named; do not fetch Markdown at click time. Each card is one native link with a direct detail URL; normal click or keyboard activation opens an accessible native dialog, while open-in-new-tab remains available. Move secondary proposal, task, evidence, dependency and status-source links into the dialog so cards contain no nested controls. The dialog displays summary, progress and scrollable labeled document sections. Close button, Escape and browser Back restore focus to the card and preserve board scroll position. A `?work=<id>` URL can reopen the selected card directly; invalid IDs return to the board without a broken modal. Keep pinned GitHub source references in a secondary “source files” area. Rejected alternative: primary card clicks navigating to GitHub, which interrupts the board and makes comparison difficult; rejected alternative: raw preformatted Markdown, which hides headings, tables and links.

## Risks / Trade-offs

- Committed metadata can drift from reality → require rationale/source links and a review revision, then make stale or inconsistent records a build error.
- A large archive can overwhelm readers → show concise cards with a clear archived count and optional details, retaining accessible links.
- Existing spec-site exclusion tests may flag proposals → scope their check to accepted-ledger pages, add an explicit work-page draft test, and leave all other site checks intact.
- Static status ages between pushes → show UTC as-of time and revision; do not claim live telemetry.
- Many full documents can enlarge HTML → cap individual input size, retain the 8 MiB site budget, and measure the resulting page on mobile and desktop.

## Migration Plan

The first board is published. Land this refinement to the proposal promptly, then implement and validate the committed document pass and accessible dialog. Build with `python3 scripts/build_site.py`, inspect selected-card and close behavior at mobile and desktop widths, then merge/push and inspect the revised published `/work/` URL at the landed revision. No board or Nix build reservation is required. If deployment fails, the prior published site remains in place while the failed revision is corrected.
