# C drawer reference cross-build

On 2026-09-24, the coordinator built the integrated source at
`c04d5e25e0ba803a4953a9a63c39e68b55be86d0`:

```sh
nix build .#touch-launcher --no-link --print-out-paths --max-jobs 1 --cores 8
```

Result: `/nix/store/lcaaq64mi2h6hcn9qjqawrzdlx7y8brr-k230-touch-launcher`.
Its native RISC-V client is
`/nix/store/iqhfm7j6yf0n31kj7sh6k211jdwfdd5y-k230-touch-launcher-riscv64-unknown-linux-gnu-0.1/bin/k230-touch-launcher`.

The integrated host checks passed: nine drawer gesture cases, the bounded route
socket test, three legacy navigation tests, eight icon resolution/cache/theme
cases, and nine theme preparation cases including immutable background choice.
The source includes the reviewed fixes for preserved drag velocity, viewport
hit bounds, nonblocking route requests, bounded app launch handoff, and failed
child-reaping recovery.

This proves a cross-built C reference client. It does not prove the drawer
running over live cards on the panel, physical touch, complete Settings or
notification rendering, or accepted performance. The separate live-card test
uses an actual Wayland layer fixture; it is not this production launcher.

The user's Rust direction is now explicit in the coherent-shell proposal.
This C client is retained for comparison and rollback. The Rust client probe,
Qt Quick evaluation, and remaining cross-surface implementation are open;
none is completed by this build. No new image was installed for this result.
