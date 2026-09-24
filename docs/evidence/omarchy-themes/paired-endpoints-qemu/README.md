# Paired Sway/Rust appearance transaction under headless QEMU

Observed 2026-09-24 05:34 UTC. This is a synthetic 568×1232 Pixman compositor
run under `qemu-riscv64-static`, not a device or panel observation. The Sway
deck binary came from the appearance target
`/nix/store/qwja5838kgidxzvii70l0smf72snzsqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
(source deck endpoint through `f7644dcd`; integrated source at `d5aee9a1`).
The Rust binary was
`/nix/store/rx393c3q7j3ch30zk3l3w0ws8hyi96b1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`
(source `3bd2d35b`, including persistent selected-generation startup and
wallpaper remap recovery). The live card source was the public synthetic
`card-composition-probe-client` from
`/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`.
The test worktree was based on `origin/master` `d5aee9a1`, with the reviewed
Rust wallpaper source `0a56fb1c` cherry-picked as `a1073eb2` for source
context. It executed the *exact target binaries above*, not a local build.

```sh
python3 tests/test_paired_theme_endpoints_runtime.py \
  --sway /nix/store/qwja5838kgidxzvii70l0smf72snzsqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/rx393c3q7j3ch30zk3l3w0ws8hyi96b1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-paired-theme-qemu-final-01 --check-restart
```

PASS. The real Python two-endpoint coordinator prepared and committed a
synthetic still generation to both private sockets. [The live deck](themed-deck.png)
showed the wallpaper through transparent canvas: upper `(240,20,20)`, lower
`(20,20,240)`. [The mapped Rust drawer](themed-drawer.png) painted its authored
green `(34,170,34)` above the live deck. [The expanded live app](app-after.png)
retained its original center pixel after the wallpaper was selected; the
wallpaper layer has an empty input region in source, but this pixel check is
not a physical touch-routing test.

The fixture then prepared another generation and injected a Rust commit
transport failure *after Sway committed*. The real coordinator restored its
`active` pointer and issued rollback to both real endpoints. The drawer and
[deck after rollback](rollback-deck.png) matched the prior generation pixels.
After Rust process restart, [deck](restarted-deck.png) and
[drawer](restarted-drawer.png) still matched the selected generation from the
private `current/active` pointer. The injected failure is a coordinator
transport fault, not a decoder or hardware fault. The adjacent `result.json`
records the exact binary paths and asserted pixels.

The six PNGs were visually reviewed. They contain only a public synthetic
card and four temporary `Public Fixture` desktop labels, with no real app
content. QEMU capture proves compositor output pixels and protocol order; it
does not prove panel photons, real finger routing, video backgrounds, memory
usage, image latency on the K230, or the full opt-in image boot. Those remain
separate physical and integration gates.
