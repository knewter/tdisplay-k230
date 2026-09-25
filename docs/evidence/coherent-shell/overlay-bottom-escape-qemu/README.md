# Bottom-edge overlay escape: paired QEMU injected-touch regression

Observed 2026-09-25 on a headless 568×1232 Pixman output under
`qemu-riscv64-static`, in response to the operator's literal report: "if in
settings swiping up from bottom does nothing it should be like any app
really." Traced by `docs/design/shell-ux-critique.md` §1.1 to
`nix/card-shell/adapter.c`'s `input_down`, which ceded every touch to a
mapped Drawer/Shade/Settings overlay before the compositor's own bottom-edge
recognizer ever ran. Fixed in `nix/card-shell/adapter.c`,
`nix/card-shell/route.c`, and `nix/rust-shell-client/src/service_ui.rs`; see
`openspec/changes/the-shell-behaves-as-one-coherent-system/` slice E
(tasks E.1-E.3) for the full spec/task record.

Positive (fixed) targets:

- Sway: `/nix/store/vysdsfyh2i3k00n6sp8wpfa2hj07qvvc-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
  (built via `nix build .#card-shell --max-jobs 1 --cores 6`)
- Rust client: `/nix/store/3y57vjkizci06plvq8dldqvxdc26yni6-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`
  (built via `nix build .#handheld-shell-rust --max-jobs 1 --cores 6`)
- Client fixture: `/nix/store/03pqadqmfvr2yci8cvq2rf68rx32bf6y-card-composition-probe-client-0.1/bin/card-composition-probe-client`

```sh
python3 tests/test_rust_overlay_bottom_escape_runtime.py \
  --sway /nix/store/vysdsfyh2i3k00n6sp8wpfa2hj07qvvc-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/3y57vjkizci06plvq8dldqvxdc26yni6-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/03pqadqmfvr2yci8cvq2rf68rx32bf6y-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-sa-3
```

PASS (`result.json`). Four scenarios, all real injected `wl_touch` via the
compositor's own `card_shell test-touch` hook (`SWAY_K230_CARD_TEST_INPUT`),
real Sway/Wayland protocol traffic, no board access:

1. **Bottom-edge swipe up from Settings over a running app reaches the
   overview.** With Settings mapped over `k230.card.one`, a touch down at
   the bottom edge (284, 1200) followed by an upward motion to (284, 1100)
   and release is claimed by the compositor: `sway.log` logs
   `K230_CARD_SHELL mirror id=` (the same card-entry mirror an app's own
   swipe produces) and settles in `state mode=1` (`CS_DECK`, the overview).
   `rust.log` logs `unmap` — the overlay was dismissed as part of the same
   gesture, via the pre-existing `Route::Hide` now reachable from
   `card_shell_launch_surface("hide")`.
2. **Bottom-edge sideways swipe from Settings switches to the neighbour
   app.** With `k230.card.two` focused and Settings mapped over it (a second
   app, `k230.card.one`, also running), a touch down at (284, 1200), motion
   up to (284, 1100), then sideways to (420, 1100), then release switches
   focus directly to `k230.card.one` (`sway.log`'s `restored focus=`
   incrementing and matching that window's id; `focused()` over the Sway
   IPC tree confirms it) — the same already-approved two-axis quick-switch
   mechanics (`the-handheld-presents-a-coherent-shell` design decisions
   11/12) an app's own swipe already used, now reachable from the overlay
   too.
3. **Settings' own top-area Close control stays reachable.** A plain tap at
   (520, 50) — well outside the qualified bottom edge band — still reaches
   the overlay's own touch handling: `rust.log` gets a new `unmap` (the
   overlay's own `PanelIntent::Hide` tap logic fired) with **no** additional
   `K230_CARD_SHELL mirror id=` line in `sway.log` — confirming the
   bottom-edge carve-out does not overreach into the overlay's own controls.
4. **Settings' local dismiss direction now matches Shade's.** A downward
   swipe near the top (200, 60) → (200, 400) no longer dismisses Settings
   (`unmap` count unchanged); the same swipe reversed — upward, (200, 150) →
   (200, 40) — does dismiss it, matching Shade's pre-existing direction.

## Negative control: the unmodified pre-fix compositor reproduces the bug

The identical scenario-1 touch sequence against the **unmodified**
`origin/master` `nix/card-shell/adapter.c`/`route.c` (temporarily restored
via `git show HEAD:...`, `nix build .#card-shell` re-run, then the fixed
sources restored — the store path
`/nix/store/s8r1x1wfhk7ch3z40w7ialcrb7w4br9r-k230-card-shell` was not kept)
times out after 5s waiting for `K230_CARD_SHELL mirror id=`.
`negative-control/rust.log` shows the touch reaching the Rust client
directly (`touch-down 10`/`touch-move 10`/`touch-up 10`, its own logging),
i.e. Sway forwarded the whole gesture to the still-mapped overlay exactly as
`shell-ux-critique.md` §1.1 traced; `negative-control/sway.log` never logs a
`K230_CARD_SHELL mirror id=` line for this touch. This is the literal
"swiping up from the bottom of Settings does nothing" behavior being
reproduced under QEMU, not merely inferred from source.

## Regression sweep (same fixed binaries unless noted)

- `python3 -m unittest test_card_shell_state` (run from `tests/`): 29/29 —
  the C policy driver fixture is untouched by this change (no edits to
  `card-shell-policy.c`).
- `python3 tests/test_card_shell_route.py`: 1/1 — extended to also assert
  `card_shell_launch_surface("hide")` now succeeds.
- `python3 tests/test_card_touch_routing.py --sway <fixed sway>`: 7/7
  existing cases (`launcher-footer-pairing`, `hidden-card-button-pairing`,
  `second-contact-bar-drain`, `second-contact-keyboard-drain`,
  `normal-app-touch-pairing`, `cancel-without-up`,
  `device-removal-without-up`) unaffected.
- `CARD_SHELL_SWAY=<fixed sway> CARD_SHELL_CLIENT=<probe client> python3
  tests/test_card_shell_two_axis_runtime.py`: PASS — the already-approved
  two-axis quick-switch mechanics (held/reversed drag, direct release,
  vertical Home settlement, privacy) are unaffected by this change.
- `CARD_SHELL_SWAY=<fixed sway> CARD_SHELL_CLIENT=<probe client> python3
  tests/test_card_shell_touch_first_runtime.py`: PASS — the native
  deck-to-drawer route and continuous reveal IPC (exercised through a
  non-Rust layer-shell fixture, not through `card_shell_launch_surface`) are
  unaffected, confirming `prepare_impl`'s `overlay_escaping` guard did not
  weaken the pre-existing cancel-on-remap defensive cleanup for the case it
  was originally written for.
- `python3 tests/test_card_shell_gestures.py`: 17/17 cases including
  `global-edge-entry`, unaffected.
- `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`:
  221/221 across all test binaries, including the new
  `service_ui::tests::shade_and_settings_share_one_upward_dismiss_direction`.

### Pre-existing, unrelated QEMU pixel-capture issue (not a regression)

`tests/test_rust_shade_dismiss_runtime.py` and
`tests/test_rust_drawer_interaction_runtime.py` both fail a pixel-comparison
assertion (`app_shade.getpixel(...) != app.getpixel(...)`, respectively
`opened.getpixel(...) != deck.getpixel(...)`) in this sandbox. Verified this
is **not** caused by this change: the identical failure reproduces against
the unmodified pre-fix `adapter.c`/`route.c` binary too. Neither script
touches the bottom-edge or dismiss-direction code paths this change edits.
Consistent with this repository's own prior finding of the same class
(commit `68796fe8`, "Record the QEMU run attempt: environment-blocked, not
a code regression"), this is recorded as an environment limitation of this
sandbox's `grim`/headless capture, not a source regression, and is left for
a separate investigation.

## Limits

Real Sway/Wayland protocol runtime and real injected touch under QEMU; no
physical panel, finger, or board evidence. This proves the compositor
routing and Rust surface logic behave as specified; task E.4
(`docs/evidence/coherent-shell/overlay-bottom-escape/`, not yet captured)
remains the required real-glass acceptance gate before slice E can be
considered physically verified.
