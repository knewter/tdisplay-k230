# C908 vectors on the installed mainline ordinary system, 2026-10-11

This directory holds the restated gates for OpenSpec change
`the-system-enables-proven-c908-extensions` (see the change's retarget note).
The ordinary system is now `k230-mainline-drm-shell` on mainline 7.3.0-rc5. The
theme deployment made it persistent through a one-time boot, preserved rollback
roots and a verified ordinary autoboot
([ordinary-boot.json](../../omarchy-themes/installed-consumers-2026-10-10/ordinary-boot.json)).
All physical runs below share that autoboot's boot ID
`6371650b-c4c0-467f-8735-abf18ce205a9`. There was no reboot, flash, boot-file or profile
write. Times are UTC.

| Identity | Value |
| --- | --- |
| System | `/nix/store/925i44g1rmqyjcbz8hziyz3vvkx95waf-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel | `/nix/store/f3rnipvbc5vqam8kwdmn3wgcl5rbz9yx-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` (`CONFIG_RISCV_ISA_V=y`) |
| Pixman (mapped by the running Sway) | `/nix/store/brhzfimak2r3c23lmn80y1g6ww6nmb1r-pixman-riscv64-unknown-linux-gnu-0.46.4` = flake `.#pixman-rvv` |
| Manifest | [candidate-manifest.json](candidate-manifest.json), SHA256 `b76f8e06…942b26` |
| Board model | `LILYGO T-Display-K230 (mainline)` |

At source revision `3b08b46c`, host
`nix build .#nixosConfigurations.k230-mainline-drm-shell.config.system.build.toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths`
printed exactly the installed system path (host build proof).

## Tool corrections (host-tested)

- The mainline device tree reports the model `LILYGO T-Display-K230 (mainline)`. `rvv-candidate-identity.py` now accepts that string and the vendor string exactly, and nothing else. The pixel report records the observed model.
- On mainline, `event0` is the PMU power key. `card-shell-rvv-benchmark.py` now resolves the single Goodix touchscreen by name.
- `PIXMAN_SOURCE_TAR=/nix/store/s2cifkjf074cwcim1p9lij646fi3p3zy-pixman-0.46.4.tar.gz python3 tests/test_pixman_rvv_probe.py && python3 tests/test_card_shell_rvv_benchmark.py`
  passed 5 + 9 host tests.

## 3.1 QEMU: exact candidate kernel (QEMU proof only)

`python3 tools/rvv-context-qemu.py --package /nix/store/4gn2z5fi5szrnflhzjsr1kq3f1b39wqx-k230-rvv-context-probe-riscv64-unknown-linux-gnu-0.1 --corrupt-package /nix/store/yalzjvz5njqm5bqr5bqap1xsnsyfi51s-k230-rvv-context-probe-corrupt-riscv64-unknown-linux-gnu-0.1 --kernel /nix/store/f3rnipvbc5vqam8kwdmn3wgcl5rbz9yx-linux-riscv64-unknown-linux-gnu-7.3.0-rc5 --output … --timeout 90`
ran at 2026-10-11T12:47Z on QEMU 11.1.0 `virt` and returned PASS:
- no-vector: SKIP, as expected;
- VLEN 128 and 256: 2 processes × 2000 iterations each;
- corrupt control: FAIL, as intended.

See [qemu-context/](qemu-context/). The generated initramfs files were
deleted after their hashes were recorded in
[initramfs.sha256](qemu-context/initramfs.sha256). Limit: this is a probe
initramfs under the generic `virt` machine. It is not the NixOS system or the
K230 machine.

## 3.3 Physical vector context and pixels

`python3 tools/pixman-rvv-compare.py --board --manifest docs/evidence/cpu-extensions/installed-mainline-2026-10-11/candidate-manifest.json --package /nix/store/1sc1733sagi7ifx4bxw4dz0yg3hw3amj-k230-pixman-rvv-pixel-probe-riscv64-unknown-linux-gnu-0.1 --output docs/evidence/cpu-extensions/installed-mainline-2026-10-11/pixels`
(observed 2026-10-11T12:40:21Z) returned **PASS**:
- vector context: 2 processes × 2000 iterations;
- pixels: 192/192 cases equal between scalar and vector;
- corruption control: the one intended byte differs;
- vector dispatch depth 4 with 56 fast + 864 combine RVV calls;
- scalar control: depth 3, 0 RVV calls.

See [pixels/result.json](pixels/result.json). An earlier attempt stopped at the
board-model guard before any measurement. Probes were delivered as a 3-path
closure delta and rooted under `/nix/var/nix/gcroots/k230-c908-*-20261011`.

## 3.4 Representative workloads (injected input; not real-finger or optical)

The board ran
`card-shell-rvv-benchmark.py --board --repeats 3 --revision 3b08b46cdaa4c199e14e6444bfbc8cca5df738ba --manifest … --output /var/lib/k230/rvv-benchmark-mainline-20261011b`
from 12:45:57Z to about 13:02Z. It was a detached `systemd-run` unit, with
staged files hash-checked before the run. Measurement was **COMPLETE**: 6 runs,
alternating order, each restoring `shell` and `seatd`. Public outputs are in
[cards/](cards/); the archive SHA256 is `9126955a…2133ad`.

**Budgets: every run FAILS**, unchanged scripts and budgets. The failing metrics
are `frame_update_cpu_ms` (a max outlier) and `tracking_present_interval_ms`
for both card counts. **Interaction checks: the same five fail in every run
under both policies**: `terminal-route`, `monitor-route`,
`windows-home-route`, `keyboard-reserves-content` and
`normal-controls-recover-focus`. They exercise the earlier bar-era routes,
which the coherent shell no longer offers. This is a measurement of the vector
policy, not card acceptance.

| Cards | Metric (median of run p95) | no-rvv | auto (RVV) |
| --- | --- | --- | --- |
| 1 | frame_update_cpu_ms p95 | 7.02 | 6.87 |
| 1 | motion_to_present_ms p95 | 55.00 | 55.06 |
| 1 | tracking_present_interval_ms p95 | 38.33 | 38.33 |
| 1 | release_to_present_ms p95 | 54.02 | 52.05 |
| 2 | frame_update_cpu_ms p95 | 12.05 | 12.34 |
| 2 | motion_to_present_ms p95 | 54.69 | 57.40 |
| 2 | tracking_present_interval_ms p95 | 38.35 | 57.48 |
| 2 | release_to_present_ms p95 | 72.39 | 53.80 |

Three pairs are a small serial comparison. The difference is mixed, with no
consistent speedup, as on the vendor kernel
([card-cost](../../card-shell/kernel-rvv/card-cost/README.md)).

Console, shell and network on the same boot, after the runs
([board-checks.log](board-checks.log), 13:05:34Z):
- `shell`, `shell-ui`, `theme-helper` and `seatd` are active;
- `wlan0` is up with carrier and holds the default route;
- the serial console responded throughout.

No network identifiers are recorded.

## 2.2 Additional extensions: bitmanip physical execution

`/nix/store/cnnvlgaclh0knh92q94ypzfxlcdyfxph-k230-c908-bitmanip-probe-riscv64-unknown-linux-gnu-0.1/bin/c908-bitmanip-probe --probe`
(SHA256 `9de99882…a1494`, same boot) reported **PASS 4/4** for each of
Zba `sh1add`, Zbb `andn`, Zbc `clmul` and Zbs `bset`, with 0 SIGILL.
Mainline `/proc/cpuinfo` now also advertises `zbc` and `zicbop` (plus
`zfh`/`zvfh` and the `zve*` subsets), which the earlier vendor report omitted.
This is one opcode per family on fixed vectors, not conformance.

**Decision:** no additional extension is enabled for ordinary userspace codegen.
No targeted library path is proposed. Zb\* benefit, Zicbop/Zicboz userspace
use, Zfh/Zvfh, counters and Xuantie custom instructions remain **UNVERIFIED**
for default use. The ordinary image continues to boot as `rv64gc` userspace plus
the runtime-gated Pixman RVV path. See the [inventory](../README.md).

## 3.5 Rollback route (read-only, by operator decision; no recovery performed)

[rollback-route-check.py](rollback-route-check.py) (SHA256 `9bfb3e86…c614`)
mirrors the preconditions of `coherent-shell-board-install.py rollback()`
without writing anything. On the board it returned **PASS**:
- both rollback roots resolve to the valid earlier system `svjjlnvr…`;
- all 8 staged `backup/` boot files match `state.json`;
- the 4 protected `/boot` files are unchanged.

The installer's `rollback` subcommand restores those backups and the profile.
U-Boot `ums` reimaging ([uboot-ums.md](../../../uboot-ums.md)) is the
documented fallback if Linux does not come up. A physical return to the earlier image was
**not** exercised and remains UNVERIFIED.

## 3.6 Persistent selection and identity

`/run/current-system`, `/run/booted-system` and the system profile all resolve to
`925i44g1…` on boot ID `6371650b…`. That boot is the fresh ordinary autoboot
recorded in the theme deployment's `ordinary-boot.json` (physical deployment
proof made by that deployment and re-observed here).
