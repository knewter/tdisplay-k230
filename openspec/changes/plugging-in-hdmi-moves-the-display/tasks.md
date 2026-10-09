## 1. Read-only board probe (board-gated)

No GPIO is driven differently from today's boot in this group; every step
reads state only. This is the first work this change may run on hardware.

- [x] 1.1 Under the reserved board/serial lock, with the board booted
      normally (panel DTB, touch running, nothing in this change installed
      yet), confirm the LT9611 answers on `&i2c3` alongside touch:
      `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 "i2cdetect -y 3"`.
      Record which adapter number Linux assigned to `&i2c3` from
      `/sys/class/i2c-adapter/*/name` in the same session rather than
      assuming `3`, since adapter numbering is not guaranteed to match the
      DT alias. Expect `0x3b` (LT9611) and `0x5d` (GT9895, already known
      working) both listed.
- [x] 1.2 Read-only LT9611 register probe, no write beyond the register
      address byte `i2cget` itself sends:
      `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 "i2cget -y 3 0x3b 0x00"`
      (or the adapter number from 1.1). Record the returned byte and
      whether the chip acknowledges at all; do not yet attempt to decode it
      against the LT9611 register map without a datasheet read (not yet
      done in this change) — this step establishes "something answers,"
      not "the chip is initialized correctly."
      *Done 2026-09-29 on adapter 1: `0x00` read back. The same session
      also made the mainline driver's page-select writes to read chip ID
      `0x17 0x02`. That deviation is recorded in
      `docs/evidence/hdmi-hotplug/probe/lt9611-probe-2026-09-29.md`.*
- [x] 1.3 Read current GPIO23/GPIO24 direction and level with touch
      running and untouched:
      `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 "cat /sys/kernel/debug/gpio"`
      (or `gpioinfo`/`gpioget` against the `gpio0_ports` chip if
      `debugfs` is unmounted). Record both lines' direction, active state,
      and whether GPIO23's consumer is already the touch driver (expected,
      since no LT9611 node is loaded yet).
- [x] 1.4 Attempt to determine whether the LT9611's `INT_ATST_GPIO3`
      output and the GT9895's interrupt output are open-drain (needed
      before any shared-IRQ design in group 4): read the GPIO23 pull
      configuration and any available driver/debugfs description of drive
      type from the same session as 1.3. If this cannot be determined from
      software alone, record that explicitly rather than guessing — this
      remains an open question in `design.md` either way.
- [x] 1.5 Commit the sanitized console transcripts from 1.1–1.4 (no
      addresses, no credentials — none expected in this output, but check)
      under `docs/evidence/hdmi-hotplug/probe/`, and resolve the two
      `<!-- UNVERIFIED -->` markers in `specs/display/hdmi/spec.md`'s
      "The LT9611 is present and addressable" requirement against what was
      actually observed.

## 2. Driver and device-tree build (host build only, no board changes)

- [x] 2.1 Patch `drivers/gpu/drm/canaan/canaan_dsi.c`'s bridge-attach branch
      in `canaan_dsi_bind()` to call `drm_bridge_connector_init()` and
      attach the resulting connector to the encoder, mirroring the existing
      panel branch's connector setup immediately above it in the same
      function. Add the patch to `nix/kernel.nix` alongside the existing
      documented patches (goodix-berlin backport, panel reset-timing fix,
      etc.), with the same kind of comment explaining what upstream is
      missing and why. Verify with `nix build .#kernel`.
      *Done 2026-09-28: `nix/patches/canaan-dsi-bridge-connector.patch`,
      applied from `nix/kernel.nix`. `nix build .#kernel` succeeded
      (`/nix/store/mvayir0f4aksyd4pnayiz2ipvxwy4b4k-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`),
      and the patched line is present in the applied source
      (`drivers/gpu/drm/canaan/canaan_dsi.c:733` in the resulting
      `linux-xuantie-k230-src`). Host build only; not booted.*
- [x] 2.2 Add an LT9611 device-tree node to a new
      `nix/dts/k230-tdisplay-hdmi.dts` (or equivalent alternate top-level
      board file sharing `k230-tdisplay.dts`'s includes), wired to this
      board's own `&i2c3`/GPIO23/GPIO24 facts from
      `docs/research/hdmi-hotplug.md` §1–§2 — not a copy of LILYGO's
      reference-tree fallback. Target 720p60 as the initial mode. Verify
      the DTB compiles and the graph resolves with
      `nix build .#deviceTree` pointed at the new `dtbName`
      (`nix/device-tree.nix`'s existing `dtbName` parameter), and inspect
      the compiled DTB with `dtc -I dtb -O dts` to confirm exactly one
      `&dsi` `port@1` endpoint (the LT9611's) and no RM69A10 panel node —
      this task does not attempt to make both coexist in one DTB (that is
      group 4's problem, if it is solved at all).
      *Done 2026-09-28: `nix/device-tree.nix` gained a `dtsFile` parameter
      (default unchanged, `./dts/k230-tdisplay.dts`); `flake.nix` exposes
      the alternate board as `deviceTreeHdmi`
      (`dtbName = "k230-tdisplay-hdmi.dtb"`,
      `dtsFile = nix/dts/k230-tdisplay-hdmi.dts`). `nix build
      .#deviceTreeHdmi` produced
      `/nix/store/048wxyx0pnmb6ydcr9j1q3w3hldnjl36-k230-tdisplay-hdmi.dtb`.
      `dtc -I dtb -O dts` confirms exactly one `&dsi` `port@1` endpoint
      (`dsi_out_lt9611`) and no `rm69a10`/`canaan,universal`/
      `touchscreen` node anywhere in the decompiled tree. The LT9611 node
      deliberately uses `port@0`/`port@2` (not the vendor
      `k230-canmv-v3.dts`'s `port@1`/`port@2`) — see the node's own
      comment and `docs/research/hdmi-hotplug.md` §4 for why, read
      directly from this kernel's `lontium-lt9611.c`. Confirmed the
      default `deviceTree` output is unaffected (`nix build .#deviceTree`
      still builds the byte-identical `k230-tdisplay.dtb` path). Host
      build only; not booted.*
- [x] 2.3 Confirm the full system closure still cross-builds with the
      kernel patch from 2.1 present but no LT9611 node in the *default*
      device tree (`nix/dts/k230-tdisplay.dts` unchanged): verify with
      `nix build .#nixosConfigurations.k230.config.system.build.toplevel`.
      This proves the patch is inert on the panel boot path before any
      board time is spent on it.
      *Done 2026-09-28: succeeded,
      `/nix/store/2hjv5ksw5fbhazi94hxymc91kqzjdz9c-nixos-system-nixos-26.11.20260919.20b1ddd`.
      Default DTB and boot path untouched.*

## 3. Manual switch, reboot-based (board-gated)

- [ ] 3.1 Extend `nix/sd-image.nix` to place the alternate HDMI DTB
      (from task 2.2) on the boot partition alongside the default panel
      DTB, and add a NixOS-side tool (or extend `tools/push-file.py`)
      that: remounts `/boot` read-write, writes a one-shot restore marker
      naming the panel DTB, copies the HDMI DTB over the file the
      `hdmi_dtb`/`force_dtb` U-Boot selector currently names, `sync`s, and
      reboots — mirroring LILYGO's `ui_hdmi_test.c` mechanism cited in
      `docs/research/hdmi-hotplug.md` §3. Add the matching early-boot
      restore step (systemd unit or initrd hook) that checks for the
      marker and reverts the selector to the panel DTB before the next
      boot completes, deleting the marker. Verify with
      `nix build .#nixosConfigurations.k230.config.system.build.toplevel`
      and a host-side test of the marker-write/restore logic that does not
      require the board.
- [ ] 3.2 Add a Settings row that triggers the switch tool from 3.1,
      including the "next boot: HDMI / AMOLED" status readout LILYGO's own
      UI provides (`hdmi_find_connector()` scanning `/sys/class/drm`,
      cited in `docs/research/hdmi-hotplug.md` §3), and a confirm step
      before rebooting. Verify with `cargo test` /
      `cargo clippy --all-targets` for `nix/rust-shell-client` and
      `nix build .#handheld-shell-rust`.
- [ ] 3.3 On the physical board, under the reserved lock: install the
      built kernel/DTBs, trigger the Settings switch, confirm over the
      console that the board reboots into the HDMI DTB and an
      `HDMI-A-1` connector with a live monitor attached reports
      `connected` in `/sys/class/drm/*/status`
      (`flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=15 "cat /sys/class/drm/card*-HDMI-A-1/status"`),
      then reboot again (any means — this proves the self-revert, not just
      the forward switch) and confirm the panel is active again and touch
      still works
      (`python3 tools/console.py /dev/ttyACM0 --wait=15 "cat /sys/class/drm/card*-DSI-1/status"`
      plus an `evtest` touch check per the existing touch evidence
      pattern). Capture a photograph of the external monitor actually
      showing the shell, per the physical-proof distinction in AGENTS.md
      (a console transcript alone does not prove pixels reached the
      monitor). Commit console transcripts and the photograph under
      `docs/evidence/hdmi-hotplug/manual-switch/`.

## 4. Hot-plug automation without a reboot (board-gated, speculative)

This group may end in "infeasible, recorded" rather than a working feature;
`design.md` decision 4 accepts that outcome. Do not force an unproven
design to completion under schedule pressure — record what was tried and
why it did or did not work.

- [ ] 4.1 Design and, if the group-1 probe (task 1.4) did not rule it out,
      prototype a device tree where the LT9611 exists as a plain I2C
      client (able to probe, read HPD status, and raise its shared-GPIO23
      interrupt) without being the `&dsi` `port@1` endpoint, coexisting
      with the active panel node. Verify the DTB compiles and the LT9611
      driver probes (a kernel log line, not yet a working bridge) with the
      panel still the active display:
      `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=5 "dmesg | grep -i lt9611"`.
      If this cannot be made to probe without contending with touch (per
      the shared GPIO24 reset polarity mismatch in `docs/research/hdmi-hotplug.md`
      §1), record that finding and stop this task group here.
- [ ] 4.2 If 4.1 succeeds, design and implement the `canaan_dsi.c` (or a
      new small coordinating driver) logic to tear down the panel
      connector/encoder and bring up the LT9611 bridge connector/encoder
      live, on an HPD-connect interrupt, and the reverse on disconnect —
      including handing touch's ownership of GPIO23/24 to the LT9611 and
      back. This is real kernel design work with no existing pattern to
      copy; scope and re-plan it explicitly once 4.1's findings are in,
      rather than estimating it blind here.
- [ ] 4.3 If 4.2 produces something that boots, verify on the board that
      plugging an HDMI cable while the panel is active switches the visible
      output within a bounded time and without a reboot, and that
      unplugging switches back with touch working again afterward. Capture
      photographs of both transitions (panel→monitor, monitor→panel) per
      AGENTS.md's evidence-class distinctions; a console transcript alone
      does not prove either transition was seen on glass. Commit under
      `docs/evidence/hdmi-hotplug/live-switch/`.
- [ ] 4.4 Whether or not 4.1–4.3 succeed, record the outcome plainly in
      `specs/display/hdmi/spec.md`'s no-reboot requirement: either resolve
      its `<!-- UNVERIFIED -->` marker against working board evidence, or
      restate it as a known-infeasible-with-current-architecture finding
      with the specific blocker named, so a future change does not have to
      rediscover it.

## 5. Shell and card-shell landscape support

Coordinator cross-reference (2026-10-01):
[`the-shell-adapts-to-output-resolution`](../the-shell-adapts-to-output-resolution/tasks.md)
owns output configures, Drawer/Home column reflow, Settings transforms and matching
hit-testing. Its host implementation and paired fixtures are recorded there;
its task group 6 retains physical tap/density, Wi-Fi/theme geometry and dock
follow-up. Use that work for 5.2/5.3 below rather than implementing it twice.
These links do not complete this proposal's HDMI hardware or landscape gates.

- [ ] 5.1 Add an `HDMI-A-1` output stanza to `nix/shell.nix`'s Sway config
      (mode matching task 2.2's target, e.g. `1280x720`, `transform
      normal`), alongside the existing `DSI-1` stanza, and decide (record
      in `design.md` if it changes) whether both outputs are ever active
      in the same Sway session or whether the reboot-based switch means
      only one is ever present at a time in the near term. Verify with
      `nix build .#nixosConfigurations.k230.config.system.build.toplevel`.
- [ ] 5.2 Parameterize `nix/rust-shell-client/src/lib.rs`'s
      `DESIGN_ASPECT` and the direct `568.0`/`1232.0` literals it and
      `render.rs`/`wifi_ui.rs` use for coordinate scaling, so they derive
      from the actual configured output geometry instead of a compiled-in
      constant, without changing the existing portrait behavior when the
      output really is `DSI-1` at `568x1232` (existing tests must keep
      passing unchanged). Verify with `cargo test` and
      `cargo clippy --all-targets` for `nix/rust-shell-client`.
- [ ] 5.3 Make the home grid/navigation chrome
      (`nix/rust-shell-client/src/home_grid.rs`, `navigation.rs`) not
      visually broken (overlapping, off-screen, or unreachable elements) at
      a landscape aspect ratio, without necessarily redesigning the layout
      for landscape — "usable," not "redesigned," is the bar for this
      change. Verify with new unit tests exercising the same functions at
      a landscape geometry (e.g. `1280x720`) alongside the existing
      `568x1232` cases, `cargo test`.
- [ ] 5.4 On the physical board with an HDMI monitor attached (requires
      task group 3's manual switch working), capture a photograph of the
      home screen and Settings actually rendering on the external monitor
      without visibly broken layout. Commit under
      `docs/evidence/hdmi-hotplug/landscape/`.

## 6. Proposal validation

- [ ] 6.1 Validate this change and preserve every unresolved hardware
      requirement as `<!-- UNVERIFIED -->` until its named evidence exists;
      verify with
      `openspec validate plugging-in-hdmi-moves-the-display --strict`.
- [ ] 6.2 Run `python3 scripts/render_work_board.py > /dev/null`, commit,
      and hand off to the coordinator for an early merge to `master` per
      AGENTS.md, independent of whether groups 3–5 have started — the
      proposal and the research document are the reviewable deliverable at
      this point, not a private preface to the board work.

## 7. Mainline kernel port (the board's default since 2026-10-08)

The board now boots mainline 7.3.0-rc5 by default
(`openspec/changes/archive/2026-10-08-the-board-boots-mainline-by-default/`),
and there `/sys/class/drm` shows only `card0-DSI-1`: no HDMI. The mainline DRM
port already carries the K230 LT9611 driver (`nix/patches/mainline/drm/lontium-lt9611-k230.c`,
`DRM_LONTIUM_LT9611=y`) and `drm_bridge_connector_init()` in `canaan_dsi.c`.
Groups 3–5 above apply to mainline once these tasks land.

- [ ] 7.1 Make the mainline LT9611 driver's reset GPIO and IRQ optional (HPD by connector polling without an IRQ), as vendor `nix/patches/lt9611-dsi-port-b.patch` does, because GPIO24/GPIO23 belong to the GT9895 touch. Proof: `nix build .#kernelMainlineDrm`.
- [ ] 7.2 Add `nix/dts/k230-tdisplay-mainline-drm-hdmi.dts` (LT9611 on `&i2c3` at 0x3b, DSI port@1 → LT9611 port@1 (Port B) → `hdmi-connector`, touch keeps GPIO24/23, no panel), a `dtsFile` parameter for `nix/device-tree-mainline-drm.nix`, and flake outputs `deviceTreeMainlineDrmHdmi` and `kernelMainlineDrmShellHdmiBootFiles` (the normal bundle with the HDMI DTB under `k230-tdisplay.dtb`). Proof: DTB builds and decompiles; host inspection of the bundle.
- [ ] 7.3 On the board with a monitor attached, stage and volatile-trial-boot the HDMI bundle with `tools/coherent-shell-board-boot.py` (a plain reboot returns to the panel). Record the `HDMI-A-1` connector, EDID mode, LT9611 probe and `hsfreqrange` messages, a native `grim` capture, and the operator's report of the picture and touch-as-trackpad. Tune `canaan,hsfreqrange` if the link fails. Proof: serial record and operator report in `docs/evidence/hdmi-mainline/`.
