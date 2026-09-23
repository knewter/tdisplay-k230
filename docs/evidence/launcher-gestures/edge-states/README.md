# Empty overview and stale selection on the board

Observed 2026-09-23 with the source-built launcher base
`/nix/store/lrir8irpf6q81ffcgqr2r73zxpgvjf32-k230-touch-launcher-riscv64-unknown-linux-gnu-0.1`,
source `e297d6e`, on the prior installed image. Input was injected through uinput;
these native compositor captures are not real-finger/optical proof.

The empty metadata fixture returned zero rows. The overview stayed open with
“No running windows · Back returns to Apps” and “No windows”. Back returned to
Apps; a second Back closed the launcher.

The stale fixture listed only a disposable Foot window named Fixture. After
killing that owned window, tapping its still-visible card re-queried the tree,
kept the overview open, and showed “Window closed; overview refreshed”. No focus
command was sent. Back returned to Apps, then closed it; pre-existing Terminal
and Monitor process identities were unchanged. `results.json` records those
process checks; the coordinator separately inspected all retained PNGs and
confirmed the required visible states.

`fixtures.sh` creates public synthetic metadata helpers with a shell-readable
0755 directory. `check.py` verifies the helpers as the shell user before testing.
An initial attempt had a root-only directory: its process checks passed but
native review exposed the helper-launch error. That attempt was rejected, the
fixture permissions and preflight were corrected, and these captures are from
the repeated successful run. No runtime/source defect was hidden by the fix.

All image bytes are native grim output owned by this project; no external media.
Hashes and sizes are listed in `docs/blob-inventory.md`. Final-image controls and
the focused physical gesture clip remain separate acceptance gates.
