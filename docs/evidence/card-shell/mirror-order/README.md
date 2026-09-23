# Preserve mirror sibling order during scene synchronization

Source `194f3357a18408456d819269500a6593c97dc41a` replaces unconditional
raise-to-top operations with placement after the preceding mirrored source.
Traversal still follows the current source paint order, including descendants;
real restacks still apply. The previous-node pointer is local to one traversal,
so it cannot survive mirror destruction or a privacy transition. Filtering,
source clipping, surface commits and callbacks are unchanged.

The prior loop cycled every mirrored parent and child through the top on each
sync, invalidating scene regions even when the final order was unchanged. This
candidate removes that avoidable work; a board comparison is required before
claiming any cost improvement or budget pass.

```sh
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
  python3 tests/test_card_mirror_order.py
nix build .#card-shell --max-jobs 1 --cores 8 --no-link --print-out-paths
```

The test executes the actual adapter helper with the pinned wlroots 0.20.2
ordering functions and real Wayland linked lists; only damage notification is
stubbed to count calls. All 24 four-node permutations, removal and insertion
preserve the requested order. Repeating the final order generates zero updates;
the old raise-every-node loop generates four while producing the same order.
ASan/UBSan pass. Set `WLROOTS_SOURCE` to the pinned derivation source when its
store path differs on another checkout; this is not a substitute implementation
of the wlroots ordering operations.

Cross-build result: `/nix/store/gk20p9l39pqs5xg3akgg3fxm4jc7cb5x-k230-card-shell`.
The actual RISC-V Sway under QEMU user emulation passes all 17 native-input
runtime checks plus four delayed-source-time checks with
`tests/card_shell_runtime.py --native-touch --benchmark --delayed-touch` and the
native probe client. `headless.json` records live parent/child updates, drag,
privacy transitions, focus, close recovery, output loss and teardown. This is
headless evidence, not panel timing or physical-finger acceptance.

The [board comparison](board/README.md) now includes two candidate runs and a
repeat of the original package, with all interaction and restoration checks
passing. Tracking and CPU budgets still fail; this is removal of redundant
scene updates, not a measured smoothness improvement.
