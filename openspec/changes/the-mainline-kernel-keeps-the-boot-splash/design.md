## Context

Layers: stage 1 (done, archived with the predecessor), kernel (mainline
panel/DRM driver, not yet shown to preserve a lit panel), device tree
(mainline DT lacks the splash reservation), Nix (image selection), userspace
(the minimal DRM owner `k230-drm-splash`, already in the closure).

The predecessor proved, on the vendor kernel and mostly on warm resets over
USB, that stage 1 lights the panel and that the opt-in preservation patches
carry it to the shell. It did not perform the second-card power-on procedure,
and it never ran against the mainline kernel the board uses now.

## Decisions

1. **Carry the predecessor's open tasks unchanged.** Their text and proof
   commands are copied verbatim into `tasks.md`; the proof for each is
   unchanged, so nothing is relaxed by moving it.
2. **Mainline prerequisites come first.** Without a `reserved-memory` node the
   mainline kernel may allocate the splash buffer, so no handoff task is
   meaningful before it. The node takes `reg` from the same flake constant as
   U-Boot's Kconfig symbol.
3. **The mainline driver is re-proved, not assumed.** The vendor patches
   (`docs/evidence/kernel-patches.md`) do not apply to the mainline driver;
   the handoff gate must be satisfied by whatever the mainline panel/DRM tree
   carries, and recorded there with a drop condition.
4. **Default flips only on physical proof.** `k230.panelConsole` stays `true`
   for the daily shell until the film in the power-on task shows no dark
   frame; the `false` image is built and flashed to a second card first.

## Rejected

- Plymouth: measured at 897.3 MiB against the 875 MiB budget
  (`docs/evidence/boot-splash-owner.md`), so the DRM owner was selected.
- Reusing the predecessor's change id and leaving it open: it held 20 done
  tasks hostage to hardware work blocked on a kernel switch.

## Risks

Corrupted scanout after the Linux handoff is the defect that forced
`panelConsole = true`; it has not been reproduced or fixed on mainline. A
`false` image may show it, which is why the second-card rule applies.
