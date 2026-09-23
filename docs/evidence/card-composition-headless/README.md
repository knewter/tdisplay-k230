# Actual compositor probe under headless RISC-V emulation

Recorded 2026-09-23T06:28Z on `apply/card-composition-plan`, worktree
`k230-card-composition-apply`, implementation base `ded2576a12eceea087ae4b4729ea172d9a11001f`.
The companion client/harness commit is `d2f2a758112c82ab08975e4dc2a27d6f57c8e03f`
(cherry-picked here as `3d74287`). The board and UART were not used.

**Evidence class: actual cross-built Sway and real Wayland clients, headless
Pixman rendering under QEMU user emulation, explicitly injected input.** This
is not physical touch, panel presentation, physical keyboard/OSK, normal-shell
restoration, or on-board performance proof. Those gates remain UNVERIFIED.

## Build

```sh
nix build .#card-composition-probe --max-jobs 1 --cores 8 --no-link --print-out-paths
```

Result: exit 0. Output includes both wrapper and compiled test client:

`/nix/store/n84rdh4asnszcg9b270say3dm18n4xr1-k230-card-composition-probe`

The patch compiles against the pinned Sway 1.12 and wlroots 0.20.2 APIs.
No default-shell package/configuration was changed. The wrapper selects Pixman;
the compositor entry path additionally rejects a non-Pixman renderer.

## Runtime command and results

```sh
python3 tests/card_composition_headless.py \
  --sway /nix/store/bkzw3m5c9j53583ki80zf5d5nbkrqv9v-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-card-headless-live-04
```

Result: exit 0. `result.json` records all assertions. The same test also runs
through the named task gate:

```sh
python3 tests/test_card_composition_probe.py \
  --sway /nix/store/bkzw3m5c9j53583ki80zf5d5nbkrqv9v-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --case two-app-drag --case stale-destroy --case disabled --case select \
  --case close-refused --case app-exit --case keyboard-return
```

The named cases execute the shared C input policy under ASan/UBSan, then the
actual compositor runtime and an additional disabled-session check. Without
runtime executables they fail rather than substitute string checks for scene
lifetime proof. The only structural assertions concern opt-in packaging and
absence of a new DRM-open path.

The runtime checks two actual animated XDG toplevels, each with an independently
committing desynchronized subsurface. While both are shrunken, frame counts
advanced from `[[2,2],[2,2]]` to `[[296,176],[81,80]]`; these are root/child client
counts, not panel FPS. The committed capture shows complete moving app content
and scaled child surfaces in separate card slots. The test also covers:

- Allocation failure after two successful mirror allocations restores normal
  originals and focus; another deck entry then succeeds.
- Continuous injected motion, second-contact abort, touch cancellation,
  adjacent selection and expanded app focus.
- Actual XDG close callbacks: refusal keeps the client alive and leads to the
  compositor's separately labeled 1500ms still-mapped timeout; acceptance
  exits the client and unmaps its card.
- Process termination while a drag is held removes mirrors; the remaining
  release is consumed and focus returns to the surviving app.
- Actual `zwp_virtual_keyboard_v1` key events reach the selected app, reach it
  again after refusal, and reach the fallback app after the other app exits.
  Client logs count keys without logging key codes or contents.
- Output disable cancels the deck; output enable remains usable with no
  compositor crash.
- Exact environment value `0` rejects the IPC probe command and creates no
  card registry/mirror even with both test apps running.

`compositor.txt` contains only the patch's telemetry; client JSON contains only
source-defined synthetic counters and dimensions. Buffer references and mirror
releases are distinct from the clients' observed `wl_buffer.release` counts.
Sampling uses wlroots' scene-surface presentation path; `output-presented`
counts headless output events, not panel presentation. CPU/memory on the K230
are not inferred from this emulation. Scene discovery intentionally uses a
16ms timer and conservative damage; its board cost remains to be measured.

## Remaining operator gate

With the root coordinator holding the board and sole compositor reservation:

```sh
K230_CARD_DURATION=120 tools/card-composition-board-session.sh \
  --probe /nix/store/n84rdh4asnszcg9b270say3dm18n4xr1-k230-card-composition-probe/bin/card-composition-probe \
  --restore-shell
tools/card-composition-board-session.sh --collect
tools/card-composition-board-session.sh --verify-restored
```

This runs on the board after the closure is installed. Set `K230_CARD_KEYBOARD`
to the normal keyboard executable when exercising OSK return. Enter through
the bottom 48 logical pixels, tap a card to expand, and drag upward beyond
120 pixels to request close. Record real touch separately from IPC injection,
photograph/capture changing app pixels, record CPU/memory/render signals, and
verify normal Apps, keyboard and terminal after restoration. The harness's
service check alone does not prove those interactions. The OpenSpec change
remains open until these physical requirements are committed.
