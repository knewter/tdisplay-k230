## Layer

Userspace: the Rust shell client (`nix/rust-shell-client`). No device tree,
kernel, or NixOS module changes.

## Decisions

**Rejected: the first redesign attempt (3→4 columns only).** Kept every
per-app tile as a themed rounded-rect card, the full header and footer,
and search deferred. Coordinator review: "it's the same design with a 4th
column." Correct — only the grid arithmetic changed. Replaced entirely by
the design in `docs/design/app-drawer-review.md`: no tile plate, header/
footer removed, search implemented.

**Rejected: reusing the WiFi password entry's on-screen keyboard for
search.** That keyboard (`render.rs`'s `paint_wifi`) is hand-coded to that
screen's own full-height layout (hardcoded literal coordinates throughout,
e.g. `530.0 + row as f64 * 90.0`), with shift/symbols state coupled to
`WifiView`. Reusing it for the drawer would need factoring it into a
generic, position-parameterized component first — real surgery on a
screen this change does not otherwise touch, for a feature (symbols/shift)
search does not need (matching is already case-insensitive, so there is
nothing typing an uppercase letter or a symbol changes about which apps
match). Built a new, smaller, lowercase-only keyboard purpose-fit to
search instead (`navigation::search_keyboard_key_at`).

**Rejected: an alphabetical fast-scroller.** Would need its own hit-region
carved out of the grid's right edge, coupling grid-width layout math to
whether the rail is showing. This device's catalog is capped at 128 apps
and the real installed set is far smaller — a scroll rail solves a
"thousands of apps" problem this handheld does not have. Named as an
explicit non-goal, not silently dropped.

**Rejected (this change): scroll-direction damage-limited blitting** (shift
the already-composited on-screen bitmap by the scroll delta, paint only
the newly-exposed strip). The cached-bitmap architecture actually shipped
(`DrawerGridCache`) already turns the per-frame cost into one blit of a
bounded, viewport-sized area regardless of catalog size — the
order-of-magnitude win was already captured there. A further win from
also avoiding re-blitting the *unchanged* overlap between two adjacent
scroll positions is real but marginal next to that, and adds real
complexity (tracking a previous frame's composited pixels, dirty-strip
edge math). Left as the named next lever (`docs/design/
app-drawer-review.md` §6) if board measurement (open task 5.2) shows the
current architecture still falls short, rather than built speculatively
now.

**Rejected: rebuilding the grid cache incrementally (single-row patch)
instead of wholesale.** A single search keystroke, or a catalog rescan,
can change which apps are in the filtered set at *every* position (not
just append/remove at the end), since filtering re-derives the whole
display list from scratch each time (`service_ui::filter_app_indices`).
Diffing the old and new filtered lists to patch only the changed rows
would be more code for a rebuild that already only happens on a real
content change (not every scroll frame) and, per the host benchmark, costs
under 1ms warmed/33ms cold either way — not on the frame-rate-critical
path a scroll/fling actually exercises.

## Non-goals

- Reaching a *measured* (not estimated) ~20ms/frame board number — gated
  on board access (`tasks.md` 5.2).
- Search: prefix-only matching, fuzzy matching, or ranking results by
  relevance — plain substring containment is what shipped.
- Reusing this change's new compact keyboard for WiFi password entry, or
  any other unification of the two keyboards — explicitly out of scope,
  though now that both exist the shape of that refactor is clearer than
  it was before this change.

## Standard keyboard follow-up (2026-09-30)

The operator accepted reversal and search but immediately noticed search uses a different keyboard from Foot and Wi-Fi. The compact launcher-painted rows were an initial prefix-filter shortcut, not a hardware limitation. Replace them with the normal wvkbd surface, ordinary Wayland text keys and the shared show/hide helper. Reuse Wi-Fi's narrowly scoped keyboard focus approach for an active Search field, and release it on Done/Enter, Escape, app launch, route exit, surface loss or seat loss. Keep Wi-Fi secret state independent from public search text. Size the list's visible region from the actual keyboard reservation rather than assuming the old 300px custom keypad; its scroll cache remains keyed by the current catalog/filter/theme. Preserve existing edge-intent routing and original desktop-entry launch behavior. The already accepted compact-keyboard check is historical proof; the replacement needs its own real-glass acceptance.
