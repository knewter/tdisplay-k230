# Touch-first live-card drawer route: source and headless proof

The opt-in compositor route `SWAY_K230_CARD_TOUCH_FIRST=1` hides the legacy
Cards/Back/Previous/Next/Close controls. The existing live scene-surface mirrors,
bilinear scaling, card tap-to-expand, upward graceful-close request, privacy
placeholders, and bottom application-to-deck gesture remain in Sway. In the deck,
a single upward swipe starting in the footer launches the absolute executable
named by `SWAY_K230_CARD_DRAWER_HELPER` with fixed arguments `--surface drawer`.
No shell parses the path or arguments. If the helper cannot be spawned, the deck
remains usable. Sway's ignored `SIGCHLD` disposition reaps an exited helper.

The `k230-shell-drawer` layer-shell namespace may map above the live deck without
tearing down its mirrors. While mapped, new card touches are gated and an existing
card gesture is cancelled/drained. Drawer cancel only unmaps, revealing the deck;
an app selection must unmap, invoke `swaymsg card_shell back`, then launch/focus
the chosen app. The legacy `k230-launcher` route still returns to normal mode.
The integrated session must start the persistent launcher separately and set
the helper to its installed trusted wrapper; this source checkpoint does not
provide that session wiring.

Cross-build from source commit `f9f6515f58896fd3cf74d9a4b02f9812c233ba2e`:

```sh
nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths
# /nix/store/sigvlj7s8g9rfxzh1xgj2smrpjhp1swz-k230-card-shell
```

The first build after adding the Meson source line failed at patch application
because its added-line count was stale; `bb6d54cd` corrected the hunk. The
final command above passed. Narrow host checks passed:

```sh
python3 tests/test_card_shell_chrome.py
python3 tests/test_card_shell_route.py
```

The headless QEMU test runs the cross-built RISC-V Sway with live Wayland client
surfaces. It compiles a host `zwlr_layer_shell_v1` fixture from the pinned wlroots
protocol, maps an opaque magenta `k230-shell-drawer` overlay, captures the output,
checks that its pixels are above the card deck, verifies card input is gated while
mapped and resumes after unmap, and checks the helper's fixed arguments and
normal focus restoration. It passed:

```sh
python3 tests/test_card_shell_touch_first_runtime.py
```

The old build without scene-order correction failed the mapped-pixel assertion;
the corrected package above passed it. Existing headless composition, gestures,
and recovery suites passed against the preceding build of the same route (before
the scene-order correction). Input is injected by the test IPC route, and the
layer fixture is not the production launcher. This evidence does not establish
physical touch behavior, panel visual quality, on-board cost, production helper
acknowledgment, or an installed integrated image. Card task 4.2 and the physical
acceptance gates remain open. The actual board profile still attributes about
97.5% of repaint CPU to scene build and showed the opt-in scaled-pixel cache
worsening paired CPU results; no performance improvement is claimed here.
