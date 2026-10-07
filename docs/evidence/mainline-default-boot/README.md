# Mainline kernel becomes the default boot

2026-10-06/07, America/Chicago. Physical board; the root coordinator held
`/tmp/k230-board.lock` and `/dev/ttyACM0` throughout. Evidence classes:
host inspection, reserved physical-board serial boot, ordinary (untouched)
autoboot, native `grim` capture, and an operator real-finger report from an
earlier session (scope below). Raw serial logs and the private transfer host
remain outside Git.

Bundle `/nix/store/rqx0jajd0mhszvyyx7qn2wkv1hagsp6c-k230-coherent-shell-boot-files`
(`.#kernelMainlineDrmShellBootFiles`) selects system `5g3ylmyy…` with kernel
`q1j7zcjh…-linux-…-7.3.0-rc5` and the mainline DRM tree presented as
`k230-tdisplay.dtb`. [host-inspection.json](host-inspection.json) is task 1.1.

## 2.1 Stage

The only missing store paths (4, the bundle and its renamed DTB) were exported
on the host, delivered over the private transport with the manifest,
`stage.py` and `install.py`, imported, and GC-rooted. Then on the board:

```
python3 -I /var/lib/k230/coherent-boot/5g3ylmyy7s1crbskp6m8s8bgxj0zhif7-20261006/stage.py \
  prepare /var/lib/k230/coherent-boot/5g3ylmyy7s1crbskp6m8s8bgxj0zhif7-20261006
```

`prepare` ends by running `check`. It printed `K230_COHERENT_READY` and the
state captured in [staged-state.json](staged-state.json), with all eight
vendor normal files backed up in `<stage>/backup`. The stage tool previously
required the candidate to be the running system, which only held for the
vendor kernel. It now also accepts a candidate that has been imported and
registered (`candidate_present`, 3 tests in
`tests/test_coherent_shell_board_stage.py`).

## 2.2 Trial and qualification

```
python3 tools/coherent-shell-board-boot.py --candidate <bundle> \
  --state ~/tmp/k230-mainline-default-board/state.json \
  --output ~/tmp/k230-mainline-default-board/candidate
```

[trial-serial-result.json](trial-serial-result.json): PASS. CRC-checked
manual loads, then Linux on the candidate kernel, init and system; the profile
was unchanged and all three shell services were active. A native `grim`
capture showed the shell drawing (a terminal window was open).

[qualification.json](qualification.json) records the operator's acceptance.
**Scope:** the operator tested the shell on glass during the earlier mainline
parity session, which ran the same system `5g3ylmyy…`, the same 7.3.0-rc5
kernel and the same shell executable from a trial-layout bundle. The operator
reported then that "the shell responded perfectly everything seems to work".
For this install they re-affirmed that while away from the desk. The three
routes were **not** re-touched during this trial boot ID.

## 3.1 Install and ordinary boot

The first `--install` attempt stopped at its preflight before writing
anything. On a cold page cache under the mainline SD driver, `stage.py check`
needed about 65 s, past the 60 s deadline; a warm run took 9 s. The deadline
is now 180 s. Re-run:

```
python3 tools/coherent-shell-board-boot.py --candidate <bundle> --state <state.json> \
  --qualification <qualified.json> --output ~/tmp/k230-mainline-default-board/ordinary2 --install
```

[install-serial-result.json](install-serial-result.json): installer PASS.
The Image was replaced by root-backed replacement; initrd, DTB and bootargs by
atomic rename. [first-install-journal.json](first-install-journal.json) is the
on-board journal. After the installer, an ordinary `reboot` with no U-Boot
input came back on 7.3.0-rc5 with the mainline system as profile, current
system and init. `shell`, `shell-ui` and `theme-helper` were active,
`systemctl is-system-running` reported `running`, and there were no failed
units. After `swaymsg 'card_shell home'`, a native capture showed Home:

![Native Home on the installed mainline system](installed-home.png)

**Not yet observed:** a reset-button power-on of the installed system. This
needs the operator.

## 3.2 Rollback drill and reinstall

- On-board `install.py rollback <stage>` returned PASS
  ([rollback-result.json](rollback-result.json)). Each restored file was
  re-hashed against its backup digest; the profile was set back to vendor
  `p1a1hz…`.
- An ordinary `reboot` came up on `6.6.36`, profile `p1a1hz…`, all three
  services active, `running` (boot ID `3b7d50f0-…`).
- The first install's result, journal and rollback records were renamed with
  a `-1` suffix on the board.
- The candidate was trial-booted again and the cache warmed with one `check`
  (65 s cold).
- `--install` passed again
  ([reinstall-serial-result.json](reinstall-serial-result.json)) and the
  ordinary reboot was again on 7.3.0-rc5 with the mainline profile and active
  services.

## 4.1 Protected-normal baseline

[postboot.json](postboot.json) was recorded on the installed mainline system:
7.3.0-rc5, system, profile and init `5g3ylmyy…`, `running`, no failed units,
and all eight boot-file hashes (OpenSBI wrapper and selectors unchanged). The
trial tooling's `NORMAL_BASELINE` now points here, and the expected normal
`uname` and system are read from this file rather than pinned to `6.6.36` and
`p1a1hz…`.

## Recovery

The stage `/var/lib/k230/coherent-boot/5g3ylmyy7s1crbskp6m8s8bgxj0zhif7-20261006`
keeps the vendor backups and GC roots for both systems. To return to vendor
6.6, run on the board as root:

```
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/coherent-boot/5g3ylmyy7s1crbskp6m8s8bgxj0zhif7-20261006/install.py rollback \
  /var/lib/k230/coherent-boot/5g3ylmyy7s1crbskp6m8s8bgxj0zhif7-20261006
reboot
```

If mainline cannot reach Linux, stop at U-Boot and use `--recover-baseline`
first. This was proved for the vendor bundle, not re-run in this drill.
