# Brightness and power recovery pass on the installed system

Physical board, 2026-09-27 UTC. Source `433a4226`, candidate system
`/nix/store/11y992kp7bikr5hg21i2azfvmca43i7i-nixos-system-nixos-26.11.20260919.20b1ddd`.
The combined build includes live HS brightness, rounded cards, the bounded
picker thumbnail working set and the saved-theme store-relocation repair.

The candidate booted once from its staged root-filesystem bundle. Running
and booted system identities matched, all three shell services were active,
and no units were failed. Its kernel Image is byte-identical to the earlier
[camera-proven HS kernel](../live-hs/README.md). Exact boot-file hashes,
runtime executables, capture timestamps and measurements are in
[result.json](result.json).

## Camera and Settings checks

At the same locked camera settings and interior measurement rectangle as
the earlier trial:

| Operation | Levels | Mean grayscale |
| --- | --- | --- |
| Live shell-user writes | raw 26 / 128 / 255 | 26.22 / 91.62 / 172.22 |
| Repeat live write | raw 128 | 92.12 |
| Power off / on | retained raw 128 | 24.23 / 92.02 |
| Settings backend as shell | 10% / 50% / 100% | 26.44 / 91.64 / 172.61 |

Top row: live raw levels. Bottom row: Settings backend percentages.

![Live and Settings brightness on the combined candidate](live-and-settings.jpg)

![Off and recovered at nondefault brightness](off-on.jpg)

The commands and camera method are the same as the [HS trial](../live-hs/README.md).
Before DPMS off, an independent 45-second power-on timer was armed and
confirmed active. Direct power-on recovered the panel, and the unused timer
was stopped. No calibrated-nits claim is made.

The actual Settings UI was also exercised with the same Rust executable
on the preceding system `4zq3l00l…`: verified virtual-touch taps at
`(416,345)` and `(494,345)` changed brightness from raw 255 to 230 and back
to 255. The screenshot shows the applied result. This is injected physical
board input, not real-finger acceptance.

![Settings UI applied brightness](settings-ui.png)

## Normal installation interruption

The persistence transaction was launched after the candidate checks, but
the completion check received a new serial autologin session instead of
the requested marker/profile result. Its background output was under
`/run`; that log was not retrieved before reboot. The failure phase is
therefore unknown: no early-exit, rollback or successful-install claim is
supported.

The subsequent normal boot selected the earlier `9h5z3gk…` init path and
loaded a 27,314,664-byte initrd, whereas the candidate's is 27,313,841 bytes.
See the allowlisted [boot excerpt](normal-boot-excerpt.txt). The collector
incorrectly accepted a stale preboot prompt after seeing the new kernel
header and stopped early. That log alone does not demonstrate a kernel
hang. Independent follow-up serial probes returned no bytes, and SSH was
unavailable. A physical reset was requested to reload the tested staged candidate.

At that point, normal installation, task 6.4 and archive remained **UNVERIFIED / open**.
The retry must record a durable phase/result log from the first preflight,
run outside the login session, verify candidate boot hashes and system
profile before reboot, and then wait for a fresh root prompt after the new
kernel header. The retry below used the corrected host reboot checker.

## Source-based installer diagnosis

The [exact attempted transaction](persist-attempt.txt) copies another full
bundle into hidden `/boot/.k230-panel-next-*` files before its EXIT trap is
installed. `nix/sd-image.nix` defines a 112 MiB boot partition. The candidate
bundle is 87,814,083 bytes (about 84 MiB), while the existing bundle occupies
about the same amount. The shadow copies cannot fit. This is a definite
capacity defect in the helper, although the lost transaction log means we
cannot tell whether an earlier precondition failed first on this attempt.

The corrective transaction must keep staging and backups on the larger
root filesystem, check final/per-file replacement capacity, install its
failure handler before preflight, and copy the verified boot files only
inside the guarded replacement phase. This is not an atomic multi-file
update: interruption during replacement needs recovery through the preserved
root-filesystem bundle. Inspect and remove only the coordinator's own partial
hidden staging files after recovery; never clean unrelated boot files.

## Recovery and corrected installation

After the operator reconnected power, the old `9h5z3gk…` system booted
normally. All eight normal boot files matched the preserved backup. `/boot`
was full, with a 13,873,152-byte `.k230-panel-next-Image` partial copy whose
entire contents matched the corresponding prefix of the candidate Image.
The coordinator removed only that owned partial file. This confirms the
attempt reached shadow-copy staging and exhausted the boot filesystem;
the original volatile error log remains unavailable. The inspection is
recorded in [recovery-inspection.json](recovery-inspection.json).

The candidate was loaded again through U-Boot from the preserved rootfs
bundle. Its exact current/booted identities and all three active shell
services were checked before the corrected installer ran. A second manual
power interruption happened during an earlier one-shot boot, before any
persistent boot mutation; the old normal system recovered again.

The [corrected transaction](persist-durable.sh) ran as a detached systemd
oneshot, with durable logs and rollback armed before the first boot-file
write. It staged on the root filesystem, verified the candidate and backup,
and retained the actual previous system profile. `/boot` had 12,701,696
bytes available after cleanup; the replacement's worst-case growth was zero,
with 2 MiB required as metadata headroom. Direct replacement is **not atomic**;
the verified rootfs bundles remain the recovery path for power loss.

[Transaction result](persist-result.json), [allowlisted log](persist-log.txt)
and [independent verification](persist-verification.json) record SUCCESS,
all four candidate hashes, unchanged firmware/selectors, the target system
profile and sync. No normal reboot was requested until those checks passed.
The unit launch exceeded the first console collection window; its durable
result and independent checks, rather than a launch marker, establish success.

## Verified normal boot

The corrected normal reboot completed without intervention. The collector
waited for a fresh root prompt after the new kernel header, then a separate
serial command verified current system, booted system, kernel, Sway, Rust
shell and keyboard executable paths. All three shell services were active;
no units were failed. See [normal runtime identities](normal-runtime.json)
and the [allowlisted normal boot excerpt](installed-boot-excerpt.txt).

This completes task 6.4. The installed system is the same `11y992kp…`
candidate whose camera measurements and DPMS retention are recorded above.
No full-card flash or readback was performed. The actual UI stepper evidence
uses injected input on the physical board; no real-finger test is claimed.

The narrow final verification was the detached transaction's SUCCESS record,
`sha256sum -c` of the four candidate boot files, `cmp` of the four unchanged
firmware/selector files, `readlink -e /nix/var/nix/profiles/system`, and a
normal reboot followed by `readlink -f /run/{current,booted}-system`,
`readlink -f /run/booted-system/kernel`, shell service `is-active` and
`/proc/<MainPID>/exe` checks, plus `systemctl --failed`.
