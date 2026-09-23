## Context

See `proposal.md` and the delta specs. The current shell is a Sway/Pixman
session with a persistent touch bar, keyboard, and launcher. Its implemented
window overview carries metadata only; it is not a live application surface.
The physical panel is 568x1232 RGB565, and the default compositor path is CPU
Pixman. Existing gesture timing is specific to launcher cards and cannot be
reused as a live-composition result.

This change is userspace work. It does not assign work to stage 1, the kernel,
or the device tree. Nix owns packaging and image integration after an
architecture decision; the shell owns its control handoff; the board owns
acceptance of panel, touch, and live-content behavior.

## Goals / Non-Goals

**Goals:**

- Establish an implementable live-card interaction contract without reducing it
to text metadata.
- Keep the existing shell recoverable throughout a live-card failure or exit.
- Make the default Pixman path a first-class acceptance path and measure it
before selecting an optimization.

**Non-Goals:**

- Selecting the composition architecture here, bypassing the sibling
`the-shell-has-a-card-composition-plan` decision.
- Blocking early state-machine, eligibility, and recovery work on every future
whole-shell UX successor.
- Relying on a VGLite experiment, Mesa/GL, or an additional CPU core.

## Decisions

1. **Gate the composition boundary, not the whole change.** The sibling
architecture proposal must land with a decision and evidence before code that
captures or composes live application content is integrated. It can select a
Wayland-client or compositor boundary within the single-owner display path,
and must establish ownership,
input/focus semantics, source availability, privacy, and failure behavior.
State-machine tests, deck policy, and recovery contracts can proceed without
that choice.

2. **Consume the whole-shell UX audit as an interaction contract.** The
`the-handheld-has-a-coherent-ux-plan` audit must supply its applicable visual
and interaction findings before final card visual hierarchy, motion constants,
and close gesture behavior are accepted. It is not a dependency on completing
all of the audit's successor changes: the card deck remains a bounded core
deliverable.

The UX audit has not yet arrived at proposal time; this is a gate on final
card visual and motion acceptance, not a claim that its findings have been
incorporated.

3. **Use live content only where the selected boundary can represent it
safely.** Eligibility is explicit. An unavailable or private surface gets a
non-live card and recovery path; it is never replaced by another application's
pixels. A text-only overview was rejected because it cannot meet the requested
visual-card behavior.

4. **Separate direct manipulation from decorative animation.** Finger position
maps to the selected card while held; the deck is horizontal; release resolves
to a card or returns to a stable deck. An upward throw requests graceful close.
No springs, blur, thumbnail effects, or general animation framework belong in
this change.

5. **Make performance a decision gate.** The implementation declares its
frame/update, input-to-visible-update, and additional-memory budgets before
board acceptance. If the default Pixman implementation misses, the result is a
recorded choice among reduced behavior, a specifically justified composition
optimization, or rejection. Any reduction retains live visual cards, finger-following,
deck selection, tap expand, and recoverable throw-close; otherwise the work
stays open or becomes an explicitly authorized successor. An optional VGLite
trial is measured separately; it does not change the default acceptance
requirement.

## Risks / Trade-offs

- [The architecture cannot obtain safe live content] → retain the existing
launcher/metadata routes and stop live-card integration until the sibling plan
identifies an owned boundary.
- [A protected or private application leaks pixels] → default it to a visible
non-live state, test it explicitly, and preserve Apps/Windows/Home exit paths.
- [The close gesture loses work] → use graceful close only, bound waiting, and
restore the card plus recovery on refusal or failure.
- [Pixman misses the interaction budget] → retain a stable deck rather than a
half-transition; accept only a mitigation that keeps every core interaction,
or leave the change open/seek authorization for a successor.
- [Injected input overstates touch usability] → label host/model, native,
injected, and physical evidence separately; only a focused physical recording
closes glass interaction tasks.

## Migration Plan

1. Land this proposal and the architecture/UX-audit proposals on master.
2. Land host-side eligibility, deck-state, and recovery work behind the
selected composition boundary without replacing current shell controls.
3. Build the narrow userspace derivation, then the system/image only after its
budget and integration checks pass.
4. On the board, collect native, injected, and real-finger evidence separately.
5. If the card surface fails, disable or remove only that surface and retain the
current Apps, Windows/Home, Keyboard, System, and Help controls.

## Open Questions

The sibling architecture decision must resolve the composition boundary and
which live-surface classes are available. The UX audit must resolve the
applicable card hierarchy and motion contract. Those questions change the
implementation route, so they are explicit gates rather than assumptions.

## Accepted implementation boundary and UX contract (2026-09-23)

The coordinator reviewed and landed the opt-in source-built Sway probe in
`801af92`. The selected owner is pinned Sway 1.12, with wlroots 0.20.2
scene-surface mirrors inside its single DRM/KMS and Pixman presentation path.
The committed architecture contract is
`docs/research/card-composition-architecture.md`; actual cross-built Sway,
independent subsurfaces, input/focus lifecycle and failure tests are recorded in
`docs/evidence/card-composition-headless/README.md`. These are headless QEMU user
emulation and injected-input results, not board proof. The architecture change's
entire physical evidence group 3 remains open. This decision permits the next
separate opt-in product package; default image integration and physical product
acceptance remain gated by the named board checks.

The product adapter consumes the separate host-testable C policy in
`nix/card-shell-policy/`. Sway owns stable container IDs and live-view
revalidation, client-buffer references, scene lifetime, global touch routing,
keyboard focus and graceful close dispatch. The policy owns horizontal deck
selection, direct finger offsets, entry recognition, normalized recovery states
and bounded close waiting. The adapter must consume actual complete-stream
touch cancellation separately from a locally rejected gesture that still has
pending hardware releases. An unmap is a source-removal observation, not proof
that a process exited; a still-mapped timeout is not a protocol refusal reply.

The bounded initial product package enumerates mapped XDG toplevels dynamically,
not the probe's two-app allowlist. Only source-audited, supported SHM surface
trees may be shown live. Unsupported/unavailable sources receive a non-live
card. A session exclusion (`SWAY_K230_CARD_PRIVATE_APP_IDS`, exact app IDs
separated by colons) or compositor mark `k230_card_private` produces a fixed
private placeholder, without reading/rendering that app's title or pixels.
`k230_card_unavailable` provides an explicit unavailable state. A caller must
classify an unknown source as unavailable rather than assume it is live; no
unimplemented protected-content protocol is claimed. Privacy changes must
release existing mirror references before the next composed frame. No private
or unavailable card may display another app's pixels. Only graceful XDG close
is allowed; timeout/refusal retains the source and existing recovery controls.

The coordinator's accepted UX audit is archived at
`openspec/changes/archive/2026-09-23-the-handheld-has-a-coherent-ux-plan/` and its
synced capability is `openspec/specs/docs/handheld-ux-plan/spec.md`. The applicable
accepted contract and review are `docs/research/handheld-ux/interaction-contract.md`
and `docs/research/handheld-ux/design-review.md`. Their adopted product constraints
are: preserve the existing 56px top bar; title role 40–44px, card title 30–34px
and state/hint 19–22px; at least 24px content inset and 56px control height;
selected/pressed/error states have visible non-color cues; reserve actual
keyboard space and keep Back above it. Use direct finger tracking and immediate
stable endpoints; reduced motion must preserve live cards, selection, expansion,
close/refusal and button recovery. The card deck is horizontal. Entry has an
upward edge gesture and a persistent Cards/Back button; Previous/Next and Close
buttons provide alternatives to browsing and throwing. Existing top-bar control
touches first restore normal Sway routing, so Apps, Windows/Home, Keyboard,
System, Help, terminal, monitor and Back keep their current command owners.
The launcher mapping also returns the card surface to normal application state.

The shared policy's initial edge, tap and throw constants are provisional source
values, not measured physical thresholds. The adapter and runtime fixtures must
use the same constants. The accepted audit's 200ms settled-release ceiling does
not replace the separate finger-tracking/input/frame/memory budget declaration
or the physical review. The product remains opt-in, Pixman-only and independent
of the separate VGLite renderer experiment. Failure disables/restores only the
card scene; the known normal shell package is unchanged.
