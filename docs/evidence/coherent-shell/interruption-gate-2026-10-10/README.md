# Live interruption gate 4.3 — 2026-10-10

All five named cases passed on the newly built compositor and unchanged selected
Rust shell. [Results](result.json), [command output](command.log) and
[provenance](provenance.json) preserve exact commands, source revisions, executable
hashes, UTC timestamps and capture origins. This completes task 4.3's named QEMU
integration gate. The separate [operator report](operator-acceptance.md) records
the user's acceptance without asking them to repeat existing checks.

```sh
CARD_SHELL_SWAY=/nix/store/awym9l5znn6599q37wnhnnch77ggghjh-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
CARD_SHELL_CLIENT=/nix/store/yjb89ap4bq5vb29szdzkr5sv9lpw1sz6-card-composition-probe-client-0.1/bin/card-composition-probe-client \
K230_SHELL_RUST=/nix/store/q2rxmp980f9kxi962f29333z9pbixvbk-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
python3 tests/test_shell_motion.py --case reverse --case retarget --case unmap \
  --case refusal --case private-no-flash --output /home/jadams/tmp/k230-m43-proof3
```

## Cancellation correction and observations

Back previously called immediate `cs_leave`, resetting an unfinished entry or
expansion. Second contact used the same immediate path. The policy now seeds
reversal from the current progress, offset and anchor; canceled contact streams
remain consumed until release. Entry-mode releases drain through the same
blocked-contact handling as other modes. Ordinary Back and hard-loss restoration
retain their established paths. This fixes the existing command, without adding
the successor's side-edge gesture.

- `reverse`: finger reversal grows the held live app continuously; release
  restores it. Back reverses held entry through intermediate rectangles while
  retaining original focus and draining the canceled contact. Back also reverses
  a captured unfinished expansion to the original Overview rectangle.
  [Held](entry-held.png), [finger reversal](finger-reverse.png),
  [Back entry](back-entry-reverse.png), [expanding](back-expand-middle.png),
  [expansion reversal](back-expand-reverse.png).
- `retarget`: second contact reverses current entry geometry, consumes both
  contact releases and preserves the app. A new contact during expansion returns
  to Overview; its remaining stream cannot activate or close the card. A fresh
  tap then expands the original app successfully.
  [Second contact](second-contact-reverse.png), [new-contact interruption](new-contact-middle.png),
  [return](new-contact-reverse.png).
- `unmap`: the actual native neighbor/source process exits during held entry,
  and a selected source exits during unfinished expansion. Remaining apps stay
  visible and focus returns to a valid survivor; sampled recovery frames contain
  zero retired-source colors. [Survivor](source-unmap-recovered.png),
  [expansion before exit](expansion-unmap-middle.png),
  [recovered](expansion-unmap-recovered.png).
- `refusal`: the native client receives exactly one graceful close request and
  refuses it. Actual sampled frames retain live content while pending and after
  timeout; the policy reports message 6, the client remains mapped, keyboard input
  reaches it after return and a fresh entry works.
  [Pending](refusal-pending.png), [timeout](refusal-timeout.png).
- `private-no-flash`: the public control contains 60,745 neighbor-colored pixels.
  Changing that live neighbor to private during held entry yields zero identifying
  content/icon pixels in four moved, held samples and every captured settlement
  sample. Selecting its card shows the neutral placeholder while its app remains
  mapped. [Public control](privacy-public-control.png),
  [private held transition](privacy-transition.png), [placeholder](privacy-placeholder.png).

The prior compositor fails both early cancellation checks:
[control identities/results](old-controls.json), [Back failure](old-back-control.log),
[second-contact failure](old-second-control.log). Controls used the committed
`844be7e0` fixture; its held-entry checks are unchanged in the final fixture.
The later raw-capture change affects only unfinished expansion.

All eight task-4.1/4.2 compatibility cases pass on the new compositor:
[result](compatibility-result.json), [output](compatibility-command.log).
That run used committed `d5eb34e4`; the eight cases and default PNG capture have
identical behavior in the final fixture. The host policy suite passes all 38
cases, including exact preservation of current geometry, stream drainage and
normal/reduced-motion reversal: [host output](policy-host.log).

The expansion fixture reads actual raw PPM screencopy pixels, checks an
intermediate row, sends the interruption and queries its state before encoding
the evidence PNG. This avoids spending the 160ms live input window encoding and
decoding PNG. It does not slow the product animation or inject a fabricated
policy timestamp. Final recovery requires both the settled IPC mode and actual
destination pixels, since a screencopy can precede the next IPC state.

## Build and retained dependencies

The guarded [component build](component-build.log) succeeds, producing
`/nix/store/dicjv65r9b3gkmwhmdj2k11vzj6bnjsj-k230-card-shell`.
Only five changed compositor/wrapper derivations build. The prior task-4.2
retention repair preserves unchanged graphics outputs; no Cairo/Pango/HarfBuzz,
kernel, image or Rust rebuild occurs. [Input comparison](input-comparison.json)
shows identical old/new Sway dependency derivations and exactly the three changed
adapter/policy source inputs, with copied store bytes matching committed source.

The [verified retention receipt](retention.json) extends the previous all-output
farm to 10,266 currently realized paths, including 13 new component paths.
The durable root is
`~/.local/state/tdisplay-k230/retained-builds/coherent-interruption-2026-10-10/build-closure`.
Every retained path passed validity checking; the new compositor's actual GC-root
query resolves to this root. Global GC policy and prior roots are unchanged;
unrealized outputs are not rebuilt just for pinning. The earlier specific GC
deletion event remains unverified.

## Ownership and remaining gates

Worktree `/home/jadams/tmp/k230-coherent-closeout-2026-10-10`, branch
`closeout/coherent-integration-2026-10-10`, task base `b156d47d`.
Owned paths: motion and policy fixtures, adapter and policy source, this evidence
directory, blob inventory, coherent task record and its work-board override.
No board or serial reservation was taken. The temporary build slot is released.

Evidence class: headless Pixman, RISC-V processes under QEMU user emulation,
native Wayland clients and injected wlroots input. Settings inputs are synthetic;
audio and notification services are unavailable. Captures contain synthetic
content. The absence checks cover sampled composed frames, not every output
presentation or camera-visible instant. No physical latency measurement, board
installation, system-mode boot or real-finger feel is claimed.

The umbrella is 29/39 complete and remains open. Accessibility task 1.5 and the
separately named physical/trace/polish gates remain. The existing operator command
for task 5.2 remains `python3 tools/capture-feature.py coherent-cards --provenance
real-touch --duration 60 --description 'Card motion and close recovery on glass'
--output-dir docs/evidence/coherent-cards`, with an identified installed artifact,
board reservation and actual camera proof. This host closeout does not perform it.
