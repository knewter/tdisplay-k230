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

## 3. Manual reboot scope canceled — 2026-10-09

The operator dropped original tasks 3.1–3.3 and the Settings reboot/self-revert
requirement because automatic cable switching works. These tasks were not
performed and are not marked complete. The parked prototype at `58498320` and
unmerged draft at `6b0ad375` are historical, with no shipping requirement or
physical recovery claim. See `docs/evidence/hdmi-hotplug/live-switch/scope-decision-2026-10-09.md`.

## 4. Hot-plug automation without a reboot (board-gated, physically accepted)

The staged monitor and combined trials passed their named host and physical
gates. Their historical records retain the distinction between cable status,
visible output, input modes and navigation acceptance. Precise timing was
explicitly deferred by the operator, not measured or passed.

- [x] 4.1 Design and, if the group-1 probe (task 1.4) did not rule it out,
      prototype a device tree where the LT9611 exists as a plain I2C
      client (able to probe and poll HPD without requesting or enabling
      its shared-GPIO23 interrupt) without being the `&dsi` `port@1`
      endpoint, coexisting
      with the active panel node. Verify the DTB compiles and the LT9611
      driver probes (a kernel log line, not yet a working bridge) with the
      panel still the active display. Host proof:
      `nix build .#kernelMainlineDrmShellHpdMonitorBootFiles`; the bundle
      includes the kernel and `deviceTreeMainlineDrmHpdMonitor`. Board proof:
      `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=5 "dmesg | grep -i lt9611"`.
      If this cannot be made to probe without contending with touch (per
      the shared GPIO24 reset polarity mismatch in `docs/research/hdmi-hotplug.md`
      §1), record that finding and stop this task group here.
      *2026-10-09 source preflight: the existing driver rejects a node with
      no remote DSI input and then attaches a DSI device on successful
      probe. A DT-only standalone monitor is insufficient; see
      `docs/evidence/hdmi-hotplug/live-switch/source-preflight.md`. The matching volatile monitor boot and real
      unplug/replug now pass serial/sysfs checks on an unchanged boot ID,
      with the panel connected/enabled throughout and the operator affirming
      the panel/replug. This completes the named monitor/probe gate; real
      touch and visible handoff remain unproved in task 4.3. No live-switch
      result is claimed. The
      status-only prototype now exposes `/sys/bus/i2c/devices/*-003b/hpd`,
      masks the bridge's HPD IRQ sources and leaves all DSI/GPIO ownership
      unchanged; plug/unplug observations are required before task 4.2.*
- [x] 4.2 If 4.1 succeeds, implement the explicitly re-planned persistent
      consumer arrangement in `design.md`: keep panel and LT9611 attached,
      give them separate non-cloning encoders on the single CRTC, and use
      complementary connector detection with 250 ms HPD work and generic
      DRM polling as fallback. Select each
      consumer's lane/PHY settings, preserve panel callbacks and splash
      handoff, and mask LT9611 interrupt sources when no bridge IRQ exists.
      Touch remains the sole owner of GPIO23/24 throughout; do not hand
      those shared nets between drivers or tear down live DRM components.
      Enable the existing input relay in the daily mainline system, choose
      trackpad only for enabled HDMI scanout, and restore direct panel
      mapping/calibration on return. Expose the combined tree through the
      separate `kernelMainlineDrmShellHotplugBootFiles` trial bundle before
      promoting it to normal boot/`sdImage`. Host proof:
      `nix build .#kernelMainlineDrmShellHotplugBootFiles --max-jobs 1 --cores 16`,
      matching compiled graph/boot-bundle inspection, plus native relay
      `cargo test` and `cargo clippy --all-targets`. These do not prove 4.3.
      *2026-10-09: the first persistent-consumer bundle built, passed the
      compiled graph and 15 inspector fixtures, and booted with the
      operator confirming HDMI/trackpad → panel/direct touch → HDMI. Relay
      44 unit and two integration tests plus Clippy passed. Exact tuple and
      report: `docs/evidence/hdmi-hotplug/live-switch/runtime-first-serial-boot.json`
      and `runtime-first-operator-report.json`. The faster 250 ms worker
      passes object compilation, the full matching bundle build, compiled graph
      and 15 inspector fixtures. The matching faster volatile trial is accepted
      by the operator: HDMI replug takes a couple of seconds, panel return is
      almost instant. See `fast-host-checks.json`, `fast-runtime-serial-boot.json`
      and `fast-runtime-operator-report.json` in the same evidence directory.
      The later navigation qualification is recorded under 4.3; precise
      sampled latency is explicitly deferred by the operator; approximate
      visible timing is not a sampled HPD measurement.*
- [x] 4.3 If 4.2 produces something that boots, verify on the board that
      plugging an HDMI cable while the panel is active switches the visible
      output within a bounded time and without a reboot, and that
      unplugging switches back with direct touch working again afterward.
      Use a 30-second ceiling per transition. Record operator-visible
      timing separately from sampled HPD timing. The operator explicitly
      deferred precise latency measurement on 2026-10-09; the ≤1 second
      HPD-to-connector and ≤3 seconds HPD-to-enabled targets are future
      measurement targets, not acceptance gates for this delivered path.
      The first generic-poll trial switched correctly but was
      judged too slow by the operator.
      verify another replug after the return, and retain the accepted HDMI
      portrait rotation and trackpad behavior. Capture
      operator observations of both transitions (panel→monitor,
      monitor→panel), alongside their console records. The operator waived
      a monitor photograph on 2026-10-09; retain the distinction between
      console state and observed glass transitions. Commit under
      `docs/evidence/hdmi-hotplug/live-switch/`.
      *2026-10-09: physical fast switching is accepted (HDMI a couple of
      seconds, panel almost instant), and the response "it works great land it"
      confirms the requested real-touch navigation checks. Matching state
      retains the trial boot ID, portrait rotation and virtual touchpad.
      `fast-runtime-qualification.json` records the exact question context.
      The bounded watcher captured no cable transitions: `fast-runtime-latency.json`
      correctly returns INCOMPLETE_OR_SLOW with an empty transition list.
      The operator subsequently said "ignore latency measurement good enough
      for now". The named physical switching and
      navigation gate is complete; precise timing is deferred, not performed
      or passed. No failed measurement is inferred from the empty watch.
      See `docs/evidence/hdmi-hotplug/live-switch/closeout-2026-10-09.md`.*
- [x] 4.4 Whether or not 4.1–4.3 succeed, record the outcome plainly in
      `specs/display/hdmi/spec.md`'s no-reboot requirement: either resolve
      its `<!-- UNVERIFIED -->` marker against working board evidence, or
      restate it as a known-infeasible-with-current-architecture finding
      with the specific blocker named, so a future change does not have to
      rediscover it.
      *2026-10-09: recorded working mainline no-reboot switching against the
      accepted faster physical trial and exact qualification. The normal bundle
      and default SD image now match that accepted candidate; persistent
      installation and ordinary autoboot pass in
      `docs/evidence/hdmi-hotplug/live-switch/normal-hotplug-install-serial.json`.
      Precise sampled timing is explicitly deferred in 4.3; manual reboot scope is now canceled, landscape transfers to its successor,
      and unrelated historical UNVERIFIED markers remain explicit.*

## 5. Landscape scope transferred — 2026-10-09

Original tasks 5.1–5.4 and their layout/physical requirements are preserved in
`the-hdmi-shell-works-in-landscape`, landed as a separate proposal before this
archive. Its implementation and real monitor gates remain unchecked. Shared
geometry work continues to belong to `the-shell-adapts-to-output-resolution`.
Task 5.1 now uses automatic switching and exclusive outputs rather than the
canceled reboot path, retaining its original rollback build command and adding
the shipping mainline bundle check. See the committed scope-decision report.

## 6. Proposal validation

- [x] 6.1 Validate this change and preserve every unresolved hardware
      requirement as `<!-- UNVERIFIED -->` until its named evidence exists;
      verify with
      `openspec validate plugging-in-hdmi-moves-the-display --strict`.
      *2026-10-09: strict validation passed after recording the mainline
      live workaround. Group 7's HDMI trial is subsequently accepted;
      automatic switching is subsequently physically accepted under 4.3; historical
      probe/vendor-only limitations retain their UNVERIFIED markers.*
- [x] 6.2 Run `python3 scripts/render_work_board.py > /dev/null`, commit,
      and hand off to the coordinator for an early merge to `master` per
      AGENTS.md, independent of whether groups 3–5 have started — the
      proposal and the research document are the reviewable deliverable at
      this point, not a private preface to the board work.

      *2026-10-09: the work-board renderer passed. The planning artifacts
      were already landed at `94196f97`; the continuation commits preserve
      the remaining source and physical gates for the landing handoff.*

## 7. Mainline kernel port (the board's default since 2026-10-08)

The board now boots mainline 7.3.0-rc5 by default
(`openspec/changes/archive/2026-10-08-the-board-boots-mainline-by-default/`),
and there `/sys/class/drm` shows only `card0-DSI-1`: no HDMI. The mainline DRM
port already carries the K230 LT9611 driver (`nix/patches/mainline/drm/lontium-lt9611-k230.c`,
`DRM_LONTIUM_LT9611=y`) and `drm_bridge_connector_init()` in `canaan_dsi.c`.
The accepted automatic implementation runs on mainline. Landscape transfers
to its separate successor; the manual Settings reboot scope is canceled.

- [x] 7.1 Make the mainline LT9611 driver's reset GPIO and IRQ optional (HPD by connector polling without an IRQ), as vendor `nix/patches/lt9611-dsi-port-b.patch` does, because GPIO24/GPIO23 belong to the GT9895 touch. Proof: `nix build .#kernelMainlineDrm`.
- [x] 7.2 Add `nix/dts/k230-tdisplay-mainline-drm-hdmi.dts` (LT9611 on `&i2c3` at 0x3b, DSI port@1 → LT9611 port@1 (Port B) → `hdmi-connector`, touch keeps GPIO24/23, no panel), a `dtsFile` parameter for `nix/device-tree-mainline-drm.nix`, and flake outputs `deviceTreeMainlineDrmHdmi` and `kernelMainlineDrmShellHdmiBootFiles` (the normal bundle with the HDMI DTB under `k230-tdisplay.dtb`). Proof: DTB builds and decompiles; host inspection of the bundle.
      *2026-10-09: the corrected full kernel and HDMI bundle build, DTB
      graph/reset inspection, bundle identity inspection and 15 inspector
      fixtures pass. Commands and immutable hashes are recorded in
      `docs/evidence/hdmi-mainline/fixed-host-checks.json`,
      `fixed-dtb-check.json` and `fixed-bundle-inspection.json`.
      This is host proof, not a board boot.*
- [x] 7.3 On the board with a monitor attached, stage and volatile-trial-boot the HDMI bundle with `tools/coherent-shell-board-boot.py` (a plain reboot returns to the panel). Record the `HDMI-A-1` connector, EDID mode, LT9611 probe and `hsfreqrange` messages, a native `grim` capture, and the operator's report of the picture and touch-as-trackpad. Tune `canaan,hsfreqrange` if the link fails. Proof: serial record and operator report in `docs/evidence/hdmi-mainline/`.
      *2026-10-09 continuation: the original trial recovered HDMI after
      touch's shared reset and the operator reported "screen works".
      The corrected kernel/bundle then built, staged and passed a matching
      fresh volatile trial with automatic HPD, a 256-byte EDID, native
      terminal/Home captures and the configured relay grabbing touch.
      An ordinary protected panel reboot also passed serial checks.
      Evidence is committed in `docs/evidence/hdmi-mainline/README.md`.
      The operator subsequently accepted the fresh trial: "yeah hdmi works
      great it's perfect continue lmk what you need". Exact report and
      matching read-only state are in `operator-acceptance.json`; no
      photograph, per-gesture trace or latency measurement is inferred.*
