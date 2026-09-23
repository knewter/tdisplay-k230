# Card-composition architecture contract

## Decision

The selected route is a **source-built, opt-in patch to pinned Sway 1.12**.
It keeps Sway as the sole DRM/KMS owner and continues to use the current Pixman
renderer. The normal `shell` service and its unpatched Sway package remain the
default and recovery path. This decision follows the source audit in
[`card-composition-source-audit.md`](card-composition-source-audit.md): the
existing launcher client has no access to another client's live scene surface
or to touch before Sway dispatches it, while pinned Sway owns views, scene
trees, touch seat operations, focus, and close dispatch.

This is a selected **experiment boundary**, not card-feature delivery. The
route has no board proof yet. It must demonstrate actual app pixels and a
complete interaction before `the-shell-manages-apps-as-cards` may claim visual
cards.

## Route comparison

| Boundary | Existing protocol client | Opt-in Sway patch |
| --- | --- | --- |
| Live app surface | Sway exposes foreign-toplevel and image-copy/capture protocols, but capture creates copied images from a separate capture scene rather than sharing a live scene subtree. | `sway_view` owns `scene_tree`/`content_tree`; patch stays at that owner. |
| Touch before app dispatch | No: a layer-shell client receives events after surface selection. | Yes: Sway `seatop_impl` receives down/motion/up/cancel before dispatch. |
| Focus and keyboard return | Client may ask Sway over IPC, but cannot authoritatively restore seat state. | Sway uses `seat_set_focus_container`; patch saves and restores its prior focus. |
| Dismissal | No ownership of another client close request. | Existing `view_close` is the request boundary; actual exit/refusal remains observable. |
| DRM/renderer | Does not provide composition ownership. | Existing sole owner, Pixman, and output pipeline remain in Sway. |

## Contract for the selected probe and consuming product change

The patch adds no external compositor and opens no DRM node. It works only
inside an explicitly started opt-in Sway session. A root-coordinated board
session stops the normal `shell` service first, starts that package as the one
DRM owner, and always restores the known normal service. This planned stop and
start must not be represented as unchanged process invocation IDs.

### Eligible surfaces and identity

The capability probe allowlists exactly two launched XDG toplevel test apps.
For each it records a card ID owned by the Sway patch and the paired
`sway_container`/`sway_view`; it never gives a client process a `wlr_surface`,
buffer, DRM FD, or capture of a non-allowlisted app. The card uses the existing
view scene subtree. The probe logs map, unmap, destroy, output-leave, and any
format/stride observed by Sway.

### Lifecycle and surface ownership

`normal -> deck-entry -> attached -> dragging -> selected -> expanded` is the
selection path. `dragging -> dismissal-requested -> refused -> restored` and
`dragging -> dismissal-requested -> app-exit -> destroyed` are distinct paths.
An unmap, destroy, output leave, unsupported format, allocation failure, or
session abort cancels the gesture, removes/disables the patch-owned card node,
returns focus to a still-live container or workspace, and returns to normal
Sway. A close request is not success: it becomes `refused` unless the observed
app exit/destroy completes it.

The probe may position, clip, and order Sway's existing scene nodes. wlroots
has only per-buffer `wlr_scene_buffer_set_dest_size`, not a whole-XDG-subtree
scale. It must apply the same scale and translated coordinates to every live
content/subsurface buffer on every commit and show that full app content changes
while shrunken, rather than a crop or saved static clone. If it cannot, this
selected route is blocked for product work. It may not copy a client buffer into
a client-owned thumbnail, promise DMA-BUF/zero-copy, or retain a buffer after
Sway's map/unmap/destroy boundary. It must log the observed Pixman format and
stride instead of assuming RGB565 texture support.

### Touch, focus, and keyboard

While a single accepted finger is in `dragging`, the Sway seat operation owns
continuous down/motion/up/cancel routing and updates the card position on each
motion. A second contact, session lock, or loss of the selected surface cancels
the card gesture and restores ordinary Sway routing. During deck interaction,
keyboard focus stays with the saved live container; after expand, refusal,
exit, or abort, the patch calls Sway's focus path to restore that saved
container or a valid workspace. The probe must show there is no focus orphan.

### Completion and measurements

For each run, evidence separates scene damage/commit, client frame-done, and
presentation feedback. A frame callback is not panel presentation. It records
renderer, observed format/stride, buffer-lifetime events, process CPU, RSS,
and timestamps for the two-app drag. No GPU claim follows from this route.

## Required proof before product work

The selected package must provide `card-composition-probe`, remain outside the
default image, and pass host lifecycle fixtures. The board coordinator then
needs an opt-in session proving two live app surfaces, shrink, continuous drag,
adjacent expand, dismissal request plus refusal or exit, keyboard restoration,
and restored normal Pixman shell. It must additionally show a content update
while shrunken, proving live per-buffer scaling. Failure records the failed
state and keeps this proposal open; it cannot be relabelled as metadata cards
or as completed visual-card UX.

## Implemented probe boundary (2026-09-23)

The opt-in patch mirrors each enabled content/subsurface buffer with
`wlr_scene_surface_create`, rather than a raw saved buffer. Pinned wlroots
`types/scene/surface.c` owns independent commit handling, client-buffer locks,
acquire/release synchronization, output sampling and presentation feedback.
Sway's existing frame iterator recognizes these mirror scene surfaces, so
hidden originals do not starve the clients. The mirror geometry pass copies
source cropping, transform, opacity and color representation, applies one scale
and coordinate translation to every descendant, and conservatively clears the
opaque region. A before-render pass prevents an unscaled commit from being
presented. A 16ms discovery timer finds new subsurfaces whose disabled original
scene might not schedule a frame. That timer and conservative damage can cost
CPU; neither is a performance claim.

Only exact `SWAY_K230_CARD_COMPOSITION_PROBE=1` enables registration, and entry
also verifies the renderer is Pixman. Only app IDs `k230.card.one` and
`k230.card.two` are eligible; duplicate IDs, extra outputs and another workspace
are outside this bounded experiment. Supported probe buffers are SHM XRGB8888,
ARGB8888 and RGB565; other buffers abort. Both complete mirrors must exist before
either original is hidden. Source-node/surface destruction removes listeners
and releases mirror references; unmap, seat/output loss, lock and allocation
failure return through the same cleanup path. The original Sway scene restores
its previous enabled state and focus returns through the normal Sway seat API.

After both apps map on the active workspace, touch the bottom 48 logical pixels
to enter. The two live cards occupy separate vertical slots. Tap selects and
expands; upward motion beyond 120 logical pixels requests close. A still-mapped
client after 1500ms is classified `close-refused` (a timeout observation, not a
protocol-level refusal reply). An observed unmap after the request is logged
`app-exit`; client process exit must additionally be checked in client/session
logs. A second contact aborts and consumes remaining contacts through release.

`k230_card_probe enter|down ID X Y|motion ID X Y|up ID|cancel` is an explicit,
opt-in IPC test interface using the same handlers and logging `input=injected`.
`fail-mirror N` injects allocation failure after N new mirror allocations to
exercise partial-setup rollback. Neither interface is evidence of physical
finger interaction. The normal shell package contains none of these changes.
