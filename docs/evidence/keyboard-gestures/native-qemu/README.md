# Keyboard gesture native QEMU checkpoint

Observed 2026-09-24 UTC from branch `impl/keyboard-touch-gestures`, source
`9fea8e1f61ef4776856a37d567a17c166681be86`. This is a 568×1232
headless Pixman Sway session under `qemu-riscv64-static` with IPC-injected
contacts, the real `wvkbd-mobintl` Wayland surface, and the synthetic live
card probe client. It is **not** a board, panel, or real-finger observation.

The exact narrow cross-build was `nix build .#card-shell --max-jobs 1 --cores 4
--no-link --print-out-paths`: package
`/nix/store/pzjnkai9mpkv11zaxmrs96vyng6rw901-k230-card-shell`, Sway
`/nix/store/nkz1nrjk71pmlslsninjwj4xalgapmfx-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
The keyboard was the already-realized
`/nix/store/n7p6qfbyw30yany09x8kr95j2ar1fh7b-wvkbd-riscv64-unknown-linux-gnu-0.20/bin/wvkbd-mobintl`;
this does not assert the final image's keyboard closure. The fixture client was
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.

Run from the repository root with those exact executables:

```sh
python3 tests/test_keyboard_gestures.py
python3 tests/test_keyboard_gestures_runtime.py \
  --sway /nix/store/nkz1nrjk71pmlslsninjwj4xalgapmfx-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --keyboard /nix/store/n7p6qfbyw30yany09x8kr95j2ar1fh7b-wvkbd-riscv64-unknown-linux-gnu-0.20/bin/wvkbd-mobintl \
  --output /tmp/k230-keyboard-qemu-popup-hit
python3 tests/test_keyboard_gestures_runtime.py \
  --sway /nix/store/nkz1nrjk71pmlslsninjwj4xalgapmfx-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --keyboard /nix/store/n7p6qfbyw30yany09x8kr95j2ar1fh7b-wvkbd-riscv64-unknown-linux-gnu-0.20/bin/wvkbd-mobintl \
  --output /tmp/k230-keyboard-qemu-popup-hit-fail-helper --fail-hide
```

The policy suite passed 16 sanitizer cases. Both native runs passed. The first
kept two contacts down while a 100 px centroid rise moved the painted grip and
usable-area edge to y=1132; a pause held that position without drift; a 50 px
reverse moved it to y=1182. Releasing settled hidden at app height 1232. A
second chord settled shown at app height 756. A 210 px grip drag moved the edge
to y=966; touch cancellation restored the shown keyboard, then an ordinary
keyboard touch delivered one key press to the live client. A fresh 210 px grip
drag again reached y=966, then reversed 40 px to y=926 before continuing past
the midpoint and settling hidden.
Actions were `show, hide, show, hide`. The screenshot files here show the actual
composited pixels at those states. `result.json` retains the numeric checks.

The negative run made the trusted hide helper exit failure; after its bounded
recovery the keyboard returned to app height 756 and a normal key press still
arrived. `fail-hide-result.json` records that result. The earlier source
checkpoint reproduced a Sway scene-descriptor crash on wvkbd teardown; the
corrected compositor completed show→hide→show without that crash. A keyboard
popup elsewhere on the output initially blocked the grip because the old guard
was global; the final source checks popup overlap at the contact and retains
popup ownership if it actually covers the grip.

| State | Committed capture |
| --- | --- |
| Hidden keyboard and full-height live app | [hidden.png](hidden.png) |
| Two-finger held reveal | [held.png](held.png) |
| Two-finger reverse | [reverse.png](reverse.png) |
| Settled keyboard and usable area | [shown.png](shown.png) |
| Grip held at 210 px travel | [grip-held.png](grip-held.png) |
| Grip reversed by 40 px | [grip-reverse.png](grip-reverse.png) |

The machine-readable [positive result](result.json) and
[failed-helper recovery result](fail-hide-result.json) retain numeric outcomes.

An optional repeat with `--foot /nix/store/kv21hqgv043bmdfi5i1f791n9x7crwgg-foot-riscv64-unknown-linux-gnu-1.28.0/bin/foot`
started the real RISC-V Foot terminal with a PTY-backed `/usr/bin/tee` child.
After explicit Foot focus, two wvkbd touches entered the public letter `c`
and Enter; the file contained exactly bytes `63 0a`. The
[Foot capture](foot-typed.png) and [text result](text-entry-result.json) show
the exact result. This closes native text ownership in task 2.3, without
asserting real-finger text entry.

With `--output-reset`, disabling the sole headless output caused wvkbd to exit
after logging `Could not find config for output HEADLESS-1`; the compositor
returned the app to height 1232. After an explicit restart of wvkbd (modeling
a supervisor), a fresh two-finger show, grip hide and ordinary key check
passed. [Output-restart result](output-restart-result.json) retains the action
sequence. The installed coherent session currently starts wvkbd once from
Sway configuration, so automatic resurrection remains an open task 1.2 gate.

The later [guarded installed preview](../installed-preview/README.md) records
the actual system identity and a keyboard shown on the board by `USR2`. That
separate observation does not turn these QEMU contacts into real fingers; it
also predates the supervised keyboard and high-contrast grip source.
Remaining gates for the new source are automatic restart in the installed
unit, real two-finger and grip motion on glass, panel/camera observation,
workload budgets, and user acceptance. These captures cannot establish touch
reachability or physical smoothness.
