# Coordinated shell scene gate 4.2 — 2026-10-10

All five named cases passed against the selected, freshly cross-built Sway
component and the unchanged selected Rust shell. The [actual result](result.json),
[command output](command.log) and [provenance](provenance.json) record source
revisions, executable paths and hashes, UTC timestamps and capture identities.
This closes task 4.2's QEMU integration gate only.

```sh
CARD_SHELL_SWAY=/nix/store/2djjlzlhwpcp0gqc4j4863nlh9alkf4a-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
CARD_SHELL_CLIENT=/nix/store/yjb89ap4bq5vb29szdzkr5sv9lpw1sz6-card-composition-probe-client-0.1/bin/card-composition-probe-client \
K230_SHELL_RUST=/nix/store/q2rxmp980f9kxi962f29333z9pbixvbk-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
python3 tests/test_shell_motion.py --case shrink-live --case drawer-rise \
  --case shade-descend --case expand-live --case focus \
  --output /home/jadams/tmp/k230-m42-final
```

## Observations and drawer correction

- App entry captures progressively smaller live root/subsurface bounds,
  rounded clipping and stable held geometry. Root and child frame/callback
  counters advance while held; release reaches Overview without losing the app.
  [Held card](shrink-held.png), [Overview](shrink-overview.png).
- Navigation uses the accepted app → Overview → pinned Home → Drawer route.
  This is the already implemented route in archived
  `2026-10-09-the-shell-presents-a-pinned-home-screen` task group 10, which
  supersedes the coherent design's original Home-as-deck decision. It is not
  a new navigation decision. Home tracks the held upward gesture before release;
  running windows survive Home and Drawer.
- Drawer edge positions are 1132 and 932 after 100- and 300-pixel upward
  movement, and 32 after settling. Its visible handle is measured in actual
  composed frames; Home remains stationary, the drawer covers Home, and the
  accepted touch stream is not replayed into the Rust overlay.
  [100 pixels](drawer-100.png), [300 pixels](drawer-300.png), [open](drawer-open.png).
- The fixture exposed a stale Sway normalization: drawer travel used 81% of
  output height, while the Rust drawer now travels height minus its fixed
  32-pixel inset. Sway now uses that actual travel. The unchanged final fixture
  with the [old compositor](old-compositor-control-result.json) fails at edge
  1112 instead of 1132: a 100-pixel finger move produces 120-pixel drawer motion.
  The [control log](old-compositor-control.log) and [capture](old-drawer-100.png)
  retain that regression proof. The new compositor passes the same check.
- Shade tracks 100- and 300-pixel downward motion and settles at bottom 801.
  Its Settings target is activated through injected touch, paints a
  content-sized surface ending at 1014, preserves the underlying app rectangle,
  and returns focus through the actual Done target. Only synthetic `status`
  requests occur. [Shade](shade-open.png), [Settings](shade-settings.png),
  [returned app](shade-restored.png).
- Card activation captures intermediate live geometry before the full app,
  with monotonic expansion and no missing live pixels or blank scene.
  [Intermediate](expand-01.png), [returned app](expand-restored.png).
- Browsing a neighboring card does not activate it prematurely. Expansion
  commits its focus; keyboard input reaches that app. Drawer search receives
  text while both app key counts stay unchanged. Hiding search returns to
  Home; selecting the existing second app from Drawer restores its visible
  pixels and keyboard delivery. [Typed search](focus-search-typed.png),
  [restored app](focus-app-restored.png).

The three task-4.1 cases also pass on this new compositor:
[result](compatibility-result.json), [output](compatibility-command.log).
`python3 tests/test_card_shell_reveal.py` and
`python3 tests/test_card_shell_route.py` pass their existing host checks;
[reveal log](reveal-host.log), [route log](route-host.log).

## Build and retention

The guarded [component build](component-build.log) succeeds and produces
`/nix/store/gg7m8cqiixyi5mr7a3jcjz431np9a2na-k230-card-shell`.
It builds 14 graphics/compositor derivations, not the kernel, image or Rust
shell. [Input comparison](input-comparison.json) shows identical old/new Sway
dependency derivations; only the adapter source input changes.

The [retention audit](retention-audit.json) records a gap in the earlier
10,218-path farm: it retained graphics runtime outputs and derivations but
omitted Cairo, HarfBuzz and Pango development outputs. With `keep-outputs=false`,
retaining a derivation does not protect its unreferenced sibling outputs.
The missing coverage explains why that pin could not prevent repeated builds;
the particular historical GC deletion event remains unverified.

A separate durable root at
`~/.local/state/tdisplay-k230/retained-builds/coherent-motion-2026-10-10/build-closure`
now explicitly retains all currently realized outputs enumerated from the prior
selected system/kernel/initrd derivations and this new component, plus the prior
farm's paths and recursive derivation sources. Development/documentation/debug
siblings are enumerated directly from `nix derivation show --recursive`, rather
than assumed to follow runtime references. The audit retains the exact guarded
farm command, counts, manifest hash and actual GC-root queries. Unrealized
outputs are listed in the host-local receipt and are not built just for pinning.
The prior roots remain and global GC policy is unchanged. Changed derivations
still require builds; retention works while these durable roots remain.

## Scope and remaining gates

Worktree `/home/jadams/tmp/k230-coherent-closeout-2026-10-10`, branch
`closeout/coherent-integration-2026-10-10`, task base
`3b9d9ca28c192d3c9c069884c19506bb0dd4839d`. Owned paths: the motion fixture,
`nix/card-shell/adapter.c`, this evidence directory and screenshot inventory,
the coherent task record and its work-board override. No board or serial
reservation was taken. The temporary guarded build slot is released.

Evidence class: headless Pixman captures of the actual RISC-V Sway and Rust
processes under QEMU user emulation, native Wayland clients, injected wlroots
touch and virtual keyboard. Settings inputs are synthetic; audio and notification
services are deliberately unavailable. Captures contain synthetic fixture content.
This is not a system-mode boot, physical panel/finger, latency measurement or
board installation of the new compositor.

Task 4.3's interruption cases are still unimplemented and rejected by the parser.
Accessibility and required physical/trace/polish gates remain open. The umbrella
is 28/39 complete and remains open. Board deployment and physical acceptance of
this updated compositor remain required; existing group-5/6 operator commands
are preserved, including `python3 tools/capture-feature.py coherent-shell
--provenance real-touch --duration 60 --description 'Gesture Home drawer shade
and recovery on glass' --output-dir docs/evidence/coherent-shell` from task 5.1.
