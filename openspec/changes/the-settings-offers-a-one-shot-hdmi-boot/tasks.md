## Scope preservation

This copies original HDMI tasks 3.1–3.3 with every implementation and proof
command retained. All remain unchecked. Split/archive approval is pending;
the original proposal still owns this scope until the operator approves.

## 1. Recovery guarantee decision

- [ ] 1.1 Before implementation, establish a mechanism that satisfies the
      original next-boot guarantee even when Linux fails before restoration,
      or obtain an explicit scope revision. Record recovery boundaries and
      protected serial command. Proof: `openspec validate
      the-settings-offers-a-one-shot-hdmi-boot --strict` validates planning;
      it does not prove recovery on the board.

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
      *Shipping target: use the group-7 mainline kernel/DTBs and additionally
      build `.#kernelMainlineDrmShellBootFiles`. Keep the vendor `k230`
      toplevel build as a rollback regression check. The controller changes
      `force_dtb` atomically instead of overwriting the panel payload; see
      design's mainline implementation decision and recovery limits.*
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
      pattern). Record the operator's observation of the external monitor
      showing the shell and commit it with the console transcripts under
      `docs/evidence/hdmi-hotplug/manual-switch/`. The operator explicitly
      waived a monitor photograph on 2026-10-09; the existing accepted
      group-7 HDMI trial does not prove this separate Settings sequence.

## 4. Planning validation

- [x] 4.1 Run `openspec validate the-settings-offers-a-one-shot-hdmi-boot --strict`;
      publish the reviewed successor proposal without claiming implementation.

Planning validation passed 2026-10-09. Implementation and physical proof remain open.
