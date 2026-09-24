# Notification history motion: paired headless QEMU

2026-09-24 host run, **not a board or real-finger result**. The fixture ran the
cross-built Rust shade and Sway together on the 568×1232 headless Pixman
output. Sway's `card_shell test-touch` injected one-contact gestures. A private
local fake notification broker returned twelve invented events; no real history,
app identity, credential, address, or physical notification was used.

Exact candidate Rust source: `0a4144343993d07b4524af086f7ad5a91c309a7c`
with the preceding motion source `031e0dfc5bd03868630883b5b28fad3eccdeed2b`.
`nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#handheld-shell-rust`
passed: derivation
`/nix/store/3l1k5s4h36nii837a1cgfnwk2dc99s5g-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv`,
output
`/nix/store/z9nrjxcm3ky6yd2xvqj3846azvi6zxn6-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
The exact Sway input was the card-shell-patched `sway-unwrapped` inside
`nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#card-shell`
(output `/nix/store/8p7ryh0zw8fkhc74xc6v52br3rif9j7d-k230-card-shell`, built
from `origin/master` `69e23b3f` sources): `/nix/store/m1im24g1h70xylmia55s1qvjwa76jn9x-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`.
`.#shell-compositor` is the unpatched Sway and rejects `card_shell` commands.
This run does **not** prove the latest integrated system closure.

```sh
python3 tests/rust_notification_motion_qemu.py \
  --sway /nix/store/m1im24g1h70xylmia55s1qvjwa76jn9x-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/z9nrjxcm3ky6yd2xvqj3846azvi6zxn6-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --output /tmp/k230-notif-v9
env CARD_SHELL_SWAY=/nix/store/m1im24g1h70xylmia55s1qvjwa76jn9x-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  K230_SHELL_RUST=/nix/store/z9nrjxcm3ky6yd2xvqj3846azvi6zxn6-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  python3 tests/test_notification_center.py --case history-flick-stop \
    --case swipe-cancel --case swipe-dismiss --case critical-retained
```

Both commands passed. The named test runs the same paired client fixture after
its broker critical-retention check. Pixels show the critical row fixed,
horizontal row tracking and reversal, a non-jumping release-to-rest, a row
swipe that returns while the same finger is still down once it turns vertical
(`swipe-vertical-held.png` → `swipe-vertical-cancel.png`, no dismiss sent), two
distinct post-release vertical history frames and a stationary state after
tap-to-stop, and the next row occupying the dismissed row's
slot after the delayed fake broker reply. The fixture also checks that a tap on
the old slot during that pending reply sends **no notification action**. The
same fixture against the preceding `031e0dfc` binary failed that last check,
which is a useful negative control for the `0a414434` correction.

`swipe-return.mp4` and `scroll-stop.mp4` were encoded from sequential `grim`
captures of this actual paired QEMU session at 12 presentation frames per
second. The source captures are sampled unevenly by host/QEMU scheduling;
the files illustrate ordering and continuity, **not** measured animation speed
or panel cadence. The PNGs are unedited session captures. Source and Cargo
tests cover bounded easing, reverse, stop, and event identity separately.

Remaining gates: native compositor and Rust integration in the next complete
image, real-glass finger feel, private/critical content policy under actual
apps, and the notification physical acceptance in task 5.4. No physical task
is checked by this host run.
