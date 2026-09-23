# Opt-in live application cards

`nix build .#card-shell --max-jobs 1 --cores 8` builds a separate source-built
Sway/Pixman package. Its wrapper supplies D-Bus, coreutils and bash in PATH. `bin/card-shell --sway --config FILE` starts it in a reserved
single-compositor session; `--enter` and `--back` send IPC commands. The normal
image and the architecture probe remain separate. This package has not passed
product acceptance on the panel.

The adapter consumes `../card-shell-policy/` directly. It enumerates mapped XDG
views by stable Sway node ID, with no two-app allowlist. Eligible content is a
complete SHM XRGB8888, ARGB8888, or RGB565 surface tree. Mirrors are actual
wlroots scene-surfaces, retaining protocol buffer lifetime and independent
subsurface commits, transforms, clipping, frame callbacks, and presentation
sampling. Only visible copies are sampled. Unsupported trees get a fixed
unavailable card. Allocation or source loss restores ordinary Sway routing;
originals are hidden only after every card has been reconciled successfully.

Mark a view `k230_card_private` to exclude its pixels and title, or
`k230_card_unavailable` for an unavailable fixture. The optional colon-separated
`SWAY_K230_CARD_PRIVATE_APP_IDS` is an exact app-ID exclusion list. Privacy is
reconciled before rendering every frame, including while a card is visible.
`SWAY_K230_CARD_REDUCED_MOTION=1` preserves direct manipulation and the same
stable endpoints; there is no decorative transition animation in this slice.

Swipe upward from the lower content edge or tap Cards. Drag horizontally;
tap a live card to expand; throw upward to request graceful close. Previous,
Next, Close, and Back provide button routes. A closing app gets a stable card
and Closing feedback immediately; a still-mapped client reaches a separately
labeled 1500 ms timeout. Wayland does not expose explicit close refusal, so
continued mapping is never labeled protocol refusal or process exit. Source
unmap removes only that source. Stable IDs are revalidated before focus/close.

The existing 56-pixel top bar remains protected. A top-bar touch restores
normal app routing before the existing Apps, Windows/Home, Keyboard, System,
Help, terminal, monitor, or Back path runs. Actual Sway usable-area reservations
keep cards above the keyboard. Mapping the existing `k230-launcher` layer
leaves cards. XDG and input-method popups occupy a separate Sway layer;
while any popup is mapped, new card entry is rejected and an active deck
returns to normal mode before rendering. Popups are an explicitly unsupported
composition boundary in this slice. Second contacts over the card, top bar,
or keyboard cancel the gesture; both contacts are consumed and drained.
New card input is suppressed while the launcher owns the overlay or another
application already owns a touch sequence. Device removal and stream
cancellation use `cs_stream_cancel` and require no later up event. Output
loss restores normal routing. Session lock suppresses card content.

For host tests, first build this package and the native
`nix/card-composition-probe-client` derivation, then run:

```
python3 tests/test_card_shell_composition.py
python3 tests/test_card_shell_gestures.py
python3 tests/test_card_shell_recovery.py
python3 tests/test_touch_menu.py
```

Tests resolve cached pinned derivations without building them. Override
`CARD_SHELL_SWAY` with the unwrapped executable and `CARD_SHELL_CLIENT` with the
client executable if needed. They execute actual Wayland clients and the
cross-built compositor under QEMU user emulation, with injected input; missing
artifacts fail rather than downgrade to source-text assertions.

Benchmark IPC: `card_shell benchmark physical|injected` arms in normal mode;
wait at least three seconds with the same mapped apps, enter and exercise the
deck, use Back, wait at least three seconds, then `card_shell benchmark-stop`.
The session header is emitted at first entry; earlier baseline samples retain
the run token. `K230_CARD_BENCH` input IDs map to successful output commits and
actual presentation events. Submission time is captured immediately before
commit dispatch, then emitted only on success. CPU scopes include input,
rendering, timer reconciliation and preparation, with nested work counted once.
Final release means the visual manipulation settled, including a stable
Closing card; it does not mean the close handshake completed.

Compositor RSS and CPU are measured directly. Set
`SWAY_K230_CARD_BENCH_CGROUP=1` only when the operator has placed this compositor
and its test apps in their own cgroup v2 session; this additionally reads actual
`memory.current` and `cpu.stat`. It never logs the cgroup pathname. Without
isolated session samples the memory gate is incomplete. Use the separately
reviewed `tools/card-shell-benchmark.py` parser and contract. Headless timings,
virtual keys, and injected input never establish physical latency or usability.

The runtime suite builds `tests/card_popup_client.c` against native Wayland
headers and the stable XDG protocol XML using `cc`, `pkg-config`, and
`wayland-scanner`. A separate native routing test may opt in with exact
`SWAY_K230_CARD_TEST_INPUT=1` under a headless backend and use
`card_shell test-touch init|down ID X Y|motion ID X Y|up ID|cancel|remove`.
This registers a real wlroots touch device and emits device signals through
Sway's input manager, cursor, seat, and client protocol path. It is rejected on
DRM even if the test environment variable is set. Device removal and compositor
shutdown finish the fixture device normally. The production wrapper never
sets this test variable.
