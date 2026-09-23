# Chrome layout and failed-build cache correctness

The adapter already cached unchanged chrome before this fix. This change does
not claim a performance improvement or close the failed Pixman cost gate.

The previous cache key omitted the output's layout origin and footer height,
so moving an output could leave controls at their old positions. It also saved
a key before all scene objects were created, allowing a later identical request
to reuse a partially built tree after an allocation failure. The adapter now
includes every layout value used by the builder and marks the cache valid only
after the complete tree succeeds. Motion with unchanged controls still reuses it.

`TMPDIR=/mnt/MediaVolume/home/jadams python3 tests/test_card_shell_chrome.py`
passes. This executes the actual adapter builder with scene allocation stubs:
output movement, viewport/reservation/footer changes, pressed/message/active
states, repeated unchanged motion, removed trees, and seven injected builder
failures followed by identical retries. Running the same test against the
previous adapter fails at the output-movement assertion. This is a host logic
regression test; its stubs do not prove real rendering or GPU behavior.

`nix build .#card-shell --max-jobs 1 --cores 8 --no-link --print-out-paths`
passes, producing `/nix/store/f89ydirpaaaay26fhhn0dhg01mbfq2sp-k230-card-shell`.
The package remains opt-in. Board timing, default image integration and physical
finger acceptance remain open.

`TMPDIR=/mnt/MediaVolume/home/jadams python3 tests/test_card_shell_recovery.py`
also passes against the built RISC-V Sway under QEMU user emulation and the
native Wayland fixture. All seventeen runtime checks passed, including global
entry, persistent controls, live/privacy transitions, close timeout/exit,
keyboard focus, popup fallback, output loss and clean teardown. The disabled
adapter run also passes. Its input route is direct card IPC; this is headless
protocol/recovery evidence, not actual touchscreen routing or panel acceptance.
