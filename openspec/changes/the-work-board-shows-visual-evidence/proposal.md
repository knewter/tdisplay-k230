## Why

The work board hides screenshot evidence behind text links, so readers cannot see what a proposal has produced while scanning cards. Screenshots should accompany their change and provide a useful card cover without implying that a mockup or QEMU capture proves hardware behavior.

## What Changes

- Discover committed images and videos linked by change documents and their cited evidence records.
- Show a representative image at the top of each illustrated kanban card and a media gallery inside its existing detail dialog.
- Expose all related evidence through each card header and update on every evidence publication, before archive.
- Allow reviewed preferred covers and captions; retain explicit evidence-class labels and text-only cards where no image exists.
- Preserve whole-card activation, keyboard access, revision-pinned image sources and the current source/device-proof distinctions.

Non-goals: generating new shell evidence, recropping committed evidence, changing proposal acceptance, or adding a new photo-upload service. No physical board is needed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `docs/spec-site`: show proposal-related visual evidence on the work board and its inline detail view.

## Impact

Static work-board data extraction, Astro card/dialog rendering, reviewed status metadata and narrow site tests. No image, kernel, shell runtime or board change.
