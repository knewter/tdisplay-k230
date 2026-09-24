## Context

Layer: static documentation site. The board already renders committed proposal documents inside a dialog and retains separate source/device states. Evidence is currently a flat set of links. Images and videos are committed under `docs/`, with binary inventory and evidence records.

## Decisions

- Discover direct committed evidence citations in each change and images/videos associated with cited evidence records. Never use private worktree files or external arbitrary media URLs. Reviewed media metadata can choose a preferred cover and precise provenance; discovery remains automatic for newly committed artifacts.
- Use a representative image or video preview as the card cover. Inside the existing dialog, render all discovered images and controlled video players. Header evidence links expose reports, logs and media without navigating through proposal prose.
- Clicking a gallery image or its enlarge action opens a second, viewport-sized media modal above the card. Preserve aspect ratio with contain sizing, provide image/video gallery navigation by swipe and arrow keys, retain video controls without autoplay, and restore the card scroll position and trigger focus on close. Raw artifact links remain separately available.
- Evidence file links open in a document modal over the current card or board. Render Markdown reports using the existing local evidence reader, show bounded plain text for logs/code/data, and provide an explicit original-file link for downloads or unsupported formats. Close restores the prior reading position; ordinary activation never replaces the board with a raw URL.
- Keep one primary card link with a stretched hit area; separate header evidence links remain independent anchors. Avoid nested anchors, autoplay and a separate View details button.
- Pin media to the published source revision. Large videos stay outside the static bundle, with lazy loading and native controls. Images retain their original bytes and aspect ratio; a visual preview never upgrades a proposal's proof status.
- Rebuild discovery on every normal site publication. No archive or task-completion gate is required to publish newly landed evidence.

## Risks / Trade-offs

- Ambiguous provenance → label it as evidence with provenance in the linked record; use reviewed mockup/QEMU/board labels only when supported.
- Unrelated assets near an evidence record → follow explicit citations and direct sibling media, not a repository-wide image scan; allow a reviewed cover override.
- Large galleries → lazy image loading and video metadata loading, no video autoplay or large media duplication in the site bundle.

## Migration Plan

Land this plan, implement extraction/rendering, verify committed fixtures and browser behavior, publish and inspect the exact deployed revision. A source revert restores text-only cards. No board or image deployment is involved.
