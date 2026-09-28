# Tap-to-apply chooser harness passes under QEMU (task 10.6b)

Host, 2026-09-28, branch `close/themes` (base `38c264e4`). **QEMU user-mode
proof with a synthetic theme backend and synthetic Wayland touch only.** No
board, panel or real finger was involved. This result is not physical touch
or timing evidence.

## Command

```sh
nix build .#handheld-shell-rust --no-link --print-out-paths --max-jobs 1 --cores 6
# -> /nix/store/r5017cgy0vp7m1b86ibagy7ij5q2anv0-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0
nix build .#card-shell --no-link --print-out-paths
# -> /nix/store/j57c5im42d3rq5gxdar2ikmh22717zvc-k230-card-shell
python3 tests/rust_theme_chooser_qemu.py \
  --sway /nix/store/0a2f857nc1rz65gnjdfn46h32zsyxm18-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/r5017cgy0vp7m1b86ibagy7ij5q2anv0-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --output /tmp/q106
```

Result: `PASS paired Sway/Rust theme carousel QEMU touch, synthetic backend; no physical touch`.

The `--sway` argument must be the *unwrapped* binary that `.#card-shell`'s
`swaymsg` symlink resolves to. Passing `card-shell/bin/sway`, which links to
the wrapped `sway-1.12`, fails under `qemu-riscv64-static` with `Exec format
error`, and the harness then times out waiting for the compositor. That was
this session's first attempt. The output directory must also be short
because it holds the Wayland socket path.

## Synthetic command log (`theme-commands.jsonl`, 11 requests)

```
["list"]
["preview", "000000000000000000000000"]
["preview", "000000000000000000000001"]
["preview", "000000000000000000000002"]
["preview", "000000000000000000000002"]
["activate", "000000000000000000000002", "--expected-generation", "bbbbbbbbbbbbbbbbbbbbbbbb"]
["preview", "000000000000000000000002", "--background", "dddddddddddddddddddddddd"]
["activate", "000000000000000000000002", "--expected-generation", "eeeeeeeeeeeeeeeeeeeeeeee", "--background", "dddddddddddddddddddddddd"]
["preview", "000000000000000000000003"]
["preview", "000000000000000000000004"]
["activate", "000000000000000000000004", "--expected-generation", "bbbbbbbbbbbbbbbbbbbbbbbb"]
```

This shows the following:

- **One-tap theme apply:** a single centred tap activates the theme with its
  prepared generation. No separate Preview/Apply step exists.
- **Background tap:** the tap first prepares the exact background choice.
  It then activates that selection's own distinct generation (`eeee…`), not
  the previous background's generation. This is task 16's correction.
- **Rapid-tap coalescing:** theme `…03` was requested and then superseded.
  It was never activated, and only the later tap (`…04`) was activated.

## Captures (not committed)

The run produced eight native headless PNGs plus a fixture preview. They are kept out of the repo to
avoid adding binaries for synthetic output; their SHA-256 hashes are below.

```
c71d60314cfc83fb88a1d9886e9cb669b42f2cb033cfac81c33b0ad1a99d9a60  theme-list.png
884a425c35976b2395835ec0e8c53a8d50298df452ae0536fa2f9178eaa8f4f4  theme-list-dragged.png
dfd1856a95b64f8729356f7c818cf84efb6a4910b00f3ba85602d293744f4c24  theme-list-recentered.png
2db1f4e64a21fac5b5706f68f34b3d7be961d050ce915eafe9b9d5cd490da019  theme-tap-apply.png
e39f20d5922c476811ab87ee0ffef2ed75561aa2b8d4db3a6bba41cebe254811  theme-background-dragged.png
ddb715a02a191d06aa7bd073b8890e66089ec089ba1086f8c61f2db779619d36  theme-background-selected.png
a6258fa82fc85ab4c2cccbbd3c205af00502d00eae1e3706b212f92c51a8db85  theme-rapid-tap-coalesced.png
8f2dd65ccbd2e27e628fe2188de86be29213469a3dd51321367c8fa8403b95fe  settings.png
```

## Limits

This proves the harness's own synthetic flow on the current source. It does
not establish panel layout fit, on-glass latency or real-finger behaviour.
Those remain task 10.7 and task 14.4.
