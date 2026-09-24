# Touch-first top shade and zero-bar card layout: host proof

Source commit `b94e3240bd1d254b769b3ad0e362a5c7e34b4596` extends the opt-in
card route without changing the rollback session. When
`SWAY_K230_CARD_TOUCH_FIRST=1`, the adapter accepts a zero-height top bar
reservation, shows an empty-deck "Swipe up for Apps" cue, and owns a top-edge
downward gesture from either a normal app or the live deck. A recognized gesture
spawns the trusted absolute helper with fixed `--surface shade` arguments. The
same helper supports `--surface drawer`; the integration may set
`SWAY_K230_CARD_SURFACE_HELPER`, with the earlier drawer-helper variable retained
as a compatibility fallback. The helper contract is independent of the UI
implementation language. It does not require the prototype launcher to remain
written in C.

The top-edge route is restricted to the edge band, waits for a downward
direction/distance threshold, cancels on a second contact, and never executes
an event-supplied shell string. The mapped shell layer retains the underlying
scene and gates card input. Shade app/keyboard focus and physical edge
arbitration still require integrated and board tests.

Narrow commands and results:

```sh
python3 tests/test_card_shell_route.py               # PASS, 1 test
python3 tests/test_card_shell_chrome.py              # PASS, 1 test
python3 tests/test_card_shell_state.py               # PASS, 23 tests
nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths
# PASS /nix/store/z7m5y470ydm7db5c73mx51wmrb805k0g-k230-card-shell
python3 tests/test_card_shell_touch_first_runtime.py # PASS, QEMU/Wayland
```

The runtime test supplied the exact cross-built Sway executable from this
package and an existing source-built Wayland probe client. It injected a top
gesture in deck and normal-app states and observed the fixed helper request;
it also repeated the earlier real mapped-layer capture/input assertions. Input
was test IPC, not a real finger. This does not claim production Rust/C client
integration, an installed image, panel visual quality, physical touch
acceptance, frame timing, or a CPU speedup. Continuous app-to-deck and
deck-to-drawer finger-tracked transforms are not implemented by this route:
the current edge policy resolves to deck when its entry threshold is crossed,
and the drawer helper is requested on release. The coherent-shell motion and
physical gates remain open.
