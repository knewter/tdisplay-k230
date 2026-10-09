## Context

`docs/research/hdmi-hotplug.md` is the research this design builds on; read
it first. The load-bearing facts, restated only where a decision hinges on
them:

- No mux chip. The SoC's four DSI data lanes and clock are wired to both
  the RM69A10 panel and the LT9611 bridge as bare parallel copper
  (schematic `T-Display K230_V1.0_NEW.pdf`, sheets "K230" and "HDMI+ETH").
- The panel/touch and the LT9611 share their reset (GPIO24) and interrupt
  (GPIO23) lines as single physical nets (schematic sheet "Video," the
  `HDMI_RSTN`→`TP_RST` and `HDMI_INT`→`TP_INT` net-label ties), with
  disagreeing polarity/trigger-type requests between the vendor LT9611 DT
  node and our own touch node on that same wire.
- `drivers/gpu/drm/canaan/canaan_dsi.c`'s `canaan_dsi_bind()` resolves
  `&dsi`'s single downstream port exactly once, at boot, via
  `drm_of_find_panel_or_bridge()`. There is no runtime re-attach path.
- The bridge-attach branch of that same function never creates a DRM
  connector (`drm_bridge_connector_init()` is not called anywhere in our
  kernel's canaan DRM driver) — a real, small gap that blocks HDMI output
  entirely today, independent of switching.
- The only working HDMI path anyone has demonstrated on this silicon
  (LILYGO's shipped `ui_hdmi_test.c`) is a double-tap-confirm, reboot-based,
  self-reverting device-tree swap. No source found — LILYGO's, Canaan's
  reference tree, or ours — switches without a reboot.
- The physical HDMI cable's hot-plug-sense pin is wired only to the LT9611
  itself, not to any independent K230 GPIO, so detecting a plug event at
  all requires the LT9611 to already be a live, probed I2C device.

## Goals / Non-Goals

**Goals:** get a real `HDMI-A-1` output working on this board's own device
tree (not a copy of the unrelated reference tree); provide a working,
self-reverting manual switch a person can trigger from Settings; attempt
no-reboot automatic switching as an honestly-graded, separately staged
effort; make the minimum shell/card-shell changes needed to show something
coherent in landscape once an HDMI output exists.

**Non-goals:** adopting LILYGO's 800x480@60 output as our target mode;
HDMI audio or CEC; a full landscape redesign of every shell screen in this
change (tracked separately if it grows beyond what HDMI needs); rewriting
`canaan_dsi.c`'s DSI-host architecture in general — only the specific,
minimal changes this capability needs.

## Decisions

1. **Our own board DT node for the LT9611, not LILYGO's reference-tree
   fallback.** LILYGO's own working path reuses the unrelated Canaan
   `k230-canmv-v3.dts` wholesale (no RM69A10 panel node, no GT9895 touch
   node, 800x480@60). Copying that would give us a working HDMI output with
   the wrong resolution and would not exercise this board's actual GPIO23/24
   sharing at all, since that tree never has touch present to conflict with.
   We instead add an LT9611 node to a variant of `nix/dts/k230-tdisplay.dts`,
   using this board's own I2C3/GPIO23/GPIO24 wiring (schematic-confirmed),
   targeting 720p60 first. *Rejected: copying LILYGO's reference-tree DTB
   verbatim — faster to a working demo, but it would not be this board's
   HDMI path, and 800x480 is a worse target than 720p for a monitor.*
2. **Fix the missing bridge connector in `canaan_dsi.c` before anything
   else.** Without `drm_bridge_connector_init()`, no DTB, ours or LILYGO's
   copied one, produces a usable `HDMI-A-1` under our kernel. This is a
   kernel patch, reviewed and host-build-proved like any other patch in
   `nix/kernel.nix`, before the first board boot with an LT9611 node
   present.
3. **The reboot-based switch is the deliverable that ships, independent of
   whether no-reboot automation ever lands.** It directly reuses a
   mechanism LILYGO has already proven works on this exact silicon
   (double-tap-confirm, one-shot self-reverting DTB swap). Building our own
   version against `nix/sd-image.nix`'s existing `force_dtb`/`lcd_dtb`/
   `hdmi_dtb` U-Boot selector files (already present and hardware-tested,
   currently all pointed at the panel DTB) is strictly additive: write a
   second DTB, flip the selector file, reboot; write the restore marker
   first so any subsequent reboot for any reason reverts to the panel.
   *Rejected: gating the whole proposal on no-reboot automation working —
   would leave HDMI unusable indefinitely if stage 4 proves infeasible,
   contradicting AGENTS.md's "keep changes moving."*
4. **No-reboot automation is staged separately and may fail.** The three
   concrete blockers in `docs/research/hdmi-hotplug.md` §5 (LT9611 must be
   live while the panel DT is booted to detect a plug at all; the shared
   GPIO24 reset net forbids independently resetting either chip after
   initial power-on; `canaan_dsi.c` has no live re-attach path today) are
   none of them cosmetic. This stage's tasks are written to produce a clear
   pass/fail/infeasible record rather than to assume success. If it proves
   infeasible, the Settings-triggered reboot switch from decision 3 remains
   the shipped capability and this change closes with that scope, per
   AGENTS.md's "preserve every remaining requirement... in an explicit
   successor proposal" if a split is later authorized.
5. **Landscape support is scoped to what showing *something* on HDMI
   needs, not a full redesign.** `nix/shell.nix`'s Sway config gets an
   `HDMI-A-1` output/input stanza; `rust-shell-client`'s design-space
   transform (`lib.rs`'s `DESIGN_ASPECT` and the `568.0`/`1232.0` literals
   it feeds) is parameterized on the actual output geometry rather than
   hardcoded. Per-screen landscape layout quality (grid reflow, navigation
   chrome) is out of scope for this change and tracked as follow-on work;
   the acceptance bar here is "usable and not visually broken," not
   "redesigned for landscape."

## Risks / Trade-offs

- [A bad LT9611 DT node or GPIO polarity mistake hangs the board on next
  boot] → use a matching qualified kernel/tree and retain serial baseline
  recovery. The Linux restore unit resets the selector after a successful
  boot reaches it; a failure before that point is not repaired merely by
  power cycling. See the mainline implementation's explicit recovery limit.
- [Sharing GPIO23/24 between touch and the LT9611 causes real contention —
  wrong reset polarity, non-open-drain interrupt lines] → the read-only
  probe task (tasks.md group 1) checks GPIO state and I2C identity before
  any GPIO is driven differently from today; the no-reboot stage does not
  proceed past its own read-only sub-steps if the probe shows contention
  risk (e.g., if either interrupt line is confirmed push-pull rather than
  open-drain).
- [The no-reboot stage turns out to need a genuine `canaan_dsi.c`
  rearchitecture, well beyond this change's board time] → accepted
  explicitly by decision 4: the manual switch ships regardless, and this
  risk is recorded rather than hidden if it materializes.
- [476 shell/card-shell call sites assume 568×1232 portrait] → only the
  minimum subset blocking a coherent HDMI picture is touched here; the
  rest is named as follow-on scope rather than silently left for someone
  to discover later.

## Migration Plan

No data migration. Boot-path migration is additive and reversible: a second
DTB file and a flipped selector text file, both reversible by reboot (see
decision 3 and `docs/research/hdmi-hotplug.md` §6). The kernel patch
(bridge-connector creation) is unconditional and has no effect on the panel
boot path, since it only executes when `dsi->bridge` is non-NULL, which
never happens without an LT9611 DT node present.

## Mainline reset ordering and mouse profile (2026-10-09)

The first mainline HDMI trial initializes LT9611 before Goodix probes.
Goodix then asserts their shared GPIO24 and erases the bridge's setup,
including I2C access enable, while the bridge's cached `power_on` stays true.
Restoring I2C access and cycling the output recovered a 256-byte EDID and a
working monitor picture. See `docs/evidence/hdmi-mainline/README.md`.

The kernel driver now defers LT9611 probe until its optional
`lontium,shared-reset-owner` I2C device has finished binding and adds a
managed consumer link. The HDMI DTB points that property at touch.
Rejected: a fixed delay or another bridge-owned reset pulse; neither
establishes reset ordering, and the second resets already-initialized touch.
The matching full build and fresh volatile board trial passed. Goodix
registered before LT9611, automatic HPD returned a 256-byte EDID, and the
operator accepted the monitor trial. Exact evidence classes and limits are
recorded in `docs/evidence/hdmi-mainline/README.md`.

The Nix layer supplies a separate `k230-mainline-drm-shell-hdmi` profile
with the existing touchscreen-to-touchpad service and `uinput` loaded.
The original mainline HDMI bundle had neither service nor virtual-input
module. The ordinary panel profile retains its direct-touch setup.

## Manual switch on the shipping mainline system (2026-10-09)

The implementation targets `k230-mainline-drm-shell`, now the default
`sdImage`, using the matching mainline panel/HDMI trees from group 7. The
vendor system remains a rollback target, not the source of a DTB for a
mainline boot. Image assembly adds `k230-tdisplay-hdmi.dtb` with the same
system boot arguments; `force_dtb` still selects the intact panel tree.

`tools/display_switch.py` verifies the installed Image, panel recovery
DTB and bootargs against the running system before selecting HDMI. It
writes/fsyncs a fixed panel restore marker, prepares the HDMI tree with
those same bootargs, atomically replaces `force_dtb`, remounts `/boot`
read-only and requests a reboot. A failed write or denied reboot restores
the panel selector. The root helper has an exact sudo command; Settings
uses the existing short-lived, single-use confirmation token protocol.

The early `k230-display-restore` unit restores the panel selector before
Sway starts and removes the marker. This needs Linux to reach the restore
unit: it cannot recover a kernel/initrd failure before that point. The
previous assertion that any bad DTB can be repaired by a power cycle is
not established by a Linux-only marker. Use a qualified, matching boot
bundle, retain the staged protected baseline and serial recovery, and keep
task 3.3 open until the Settings-driven forward/return sequence is proved.
No stage-1 change or pre-Linux rollback guarantee is claimed.

One installed system includes the existing relay and `uinput`. Its mode
check keeps direct touch on a connected panel and grabs Goodix only for
connected HDMI; it does not infer that an HDMI-capable kernel means HDMI
is active. The explicitly named HDMI trial profile remains available.
The accepted output geometry is preserved.

The extra Settings row appears only when the controller is installed.
Its confirmation uses the same scaled geometry for painting/hits and
keeps its buttons within the current output; older Settings fixtures keep
their existing row rhythm and pixels.

## Open Questions

- Does U-Boot's own `k230_set_dtb`/`hdmi_dtb`/`lcd_dtb` fallback
  (`nix/sd-image.nix:142-156`) perform any live display-presence probing of
  its own, independent of a userspace-written selector file? Not resolved
  by this research (our U-Boot ships as a prebuilt blob; the C source was
  not read). If it does, that may be a cheaper place to do boot-time
  auto-selection than anything proposed here, and is worth a follow-up
  before deep investment in stage 4.
- Are the LT9611's `INT_ATST_GPIO3` output and the GT9895's interrupt
  output both open-drain? Not determinable from the schematic (drive type
  is not a schematic-visible property) or from any source read. The
  read-only probe task must establish this, or record it as still
  unknown, before any shared-IRQ design proceeds.
