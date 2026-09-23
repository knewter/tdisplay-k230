# RVV trial preparation on the expanded card

This is an independent CPU-vector experiment. It does not enable the second
core or GPU, change the normal renderer, or replace default Pixman acceptance.
The card interaction budgets remain open.

## Matching system and image

[artifacts.json](artifacts.json) records the actual cross-builds at master
`648eab07`, including the now-verified root-growth service. The trial kernel,
external Wi-Fi module, initrd and context probe form one complete system.
Host extraction of the built boot partition verifies the kernel bytes, wrapped
initrd payload/CRCs and selected system in bootargs. These are host proofs.

The complete closure was imported over Wi-Fi and pinned on the board. Its
112,751,696-byte Nix export SHA256 is
`561037e0780a6cfa6367bb628e05d108d23c2e5c3ae0e990c473db0ad4e589a9`.
Only 16 paths differed from the current normal system. This now fits because
the physical root expanded during the earlier storage boot trial.

The trial bootargs, DTB and wrapped initrd are staged below
`/var/lib/k230/rvv-trial/`. Their 27,402,240-byte transport bundle SHA256 is
`fdf22f14b6166e3048cdd05b214dd992ea5ba9fe95bb44031c4216dac91186da`.
The normal boot partition and system profile were not replaced. All files are
public build artifacts; runtime credentials are excluded.

## Boot controller and guards

`tools/rvv-board-preflight.py` checks the current normal system/profile,
physical layout and filesystem size against the committed storage capture,
protected firmware/boot hashes, every staged artifact's SHA256 and size,
complete registered closure, trial GC root and running shell. The host runs it
with Python's isolated mode and requires a fresh complete token line.

`tools/rvv-board-boot.py` holds the board lock, catches U-Boot, and loads five
artifacts into the established non-overlapping boot addresses. It verifies
actual reported lengths and CRC32 of each loaded memory region. Trial files
come from root partition 2; the unchanged SBI payload comes from boot partition
1. Its default mode then resets to the ordinary boot selection. `--boot`
instead imports the verified trial bootargs only into volatile U-Boot state and
boots the matching in-memory kernel/initrd/DTB once. No `saveenv`, flash,
partition change or persistent boot selection command is issued.

If a load fails while U-Boot remains available, the controller resets to normal
boot and records whether a fresh Linux login appeared. A login alone is never
claimed as vector execution, context preservation, shell recovery or speedup.
A kernel hang after entering a trial may still require a physical reset; the
normal persistent boot selection remains the recovery target.

Five host tests reject malformed paths, oversized artifacts, echoed/short or
ambiguous load reports, wrong memory CRCs and stale/incomplete preflight tokens.
The first physical preflight-parser failure is preserved in
[load-check.json](load-check.json) and [its analysis](preflight-parser-failure.json):
the board guard passed, but the host did not account for the Linux shell's
leading bracketed-paste reset. No reboot was attempted by that failed run. The
corrected parser removes only that known leading artifact and retains strict
complete-line matching.

The next load attempt also remains failed in
[load-check2.json](load-check2.json) and [its protocol analysis](crc-protocol-failure.json).
The actual first-file CRC matched the expected value, but the vendor prints
`crc32` in lowercase. The inherited CRLF sender also supplied a second empty
U-Boot command, repeating its previous command. The controller rejected the
reply and observed Linux login after resetting into normal boot. It now sends
exactly one CR per command and accepts the observed case while retaining exact,
unique length/CRC requirements. No vector instruction was executed in either
failed attempt.

## Physical load-and-return proof

[load-check3.json](load-check3.json) passes: U-Boot read the staged bootargs,
SBI payload, trial kernel, DTB and trial initrd at the expected sizes, and every
in-memory CRC32 matched the extracted image artifact. The controller then
reset, without importing trial arguments or executing its kernel. The following
ordinary boot reached Linux login. [Selected console lines](load-check3-selected.log)
and [provenance](load-check3-provenance.json) preserve this distinction.

[load-normal-recovery.json](load-normal-recovery.json) separately passes the
physical recovery checks: a fresh boot ID, the exact normal system, unchanged
persistent boot-file/firmware hashes and root layout, successful no-op growth
service, active shell/seatd, and Wi-Fi association plus HTTPS over `wlan0`.
This proves read access from the expanded root and normal recovery. At this load-only checkpoint, the trial kernel had not executed. The later
physical vector result is recorded below; rendering benefit remains open.

The next explicit operator trial uses the same controller with `--boot`:

```sh
python3 tools/rvv-board-boot.py --manifest HOST_TRIAL_MANIFEST \
  --private-log PRIVATE_LOG --output NEW_EVIDENCE/boot.json --boot
```

The host manifest combines `artifacts.json` with a `normal` member copied from
`docs/evidence/storage-capacity/board-repeat.json`; the identical manifest and
`tools/rvv-board-preflight.py` are staged with the verified boot files. Use new
log/output names because prior runs must not be overwritten. After an actual
trial boot, verify the selected running system and kernel configuration, then
run the scalar hwprobe gate and the context probe. Preserve the ordinary boot
selection and verify its recovery again before treating the experiment as safe.

## Physical trial boot and vector context

The one-time trial now reached Linux login: [boot1.json](boot1.json),
[selected boot lines](boot1-selected.log) and [raw-log provenance](boot1-provenance.json).
The verified five loads were followed by volatile trial-argument import and
`bootm`; no persistent selection command was used.

[capture-vector-state.py](capture-vector-state.py) was transferred with matching
MD5 and run through the serial console with isolated Python. It requires the
physical device-tree model, exact trial `/run/current-system`, matching kernel
command-line selection and all five expected vector configuration values.
It then makes a scalar hwprobe query and invokes the immutable, capability-gated
context diagnostic under a 15-second timeout.

[vector-state1.json](vector-state1.json) and [its serial report](vector-state1.serial.log)
record physical **PASS** at boot ID `3f80b720-c0e6-4f41-9437-e97aff248d28`:

- Running system is the matching `fm8136…` trial; all five vector settings are enabled.
- Standard hwprobe succeeds with value 63, including the standard V capability.
- Both diagnostic processes complete 2,000 checks. The parent records 2,002
  signals and 477 involuntary context switches; parent result, child status and
  process exit are all zero.
- Shell/seatd are active, Wi-Fi is associated and HTTPS succeeds over `wlan0`.
- Persistent system profile and bootargs still select the normal `gnr36q…` system.

The diagnostic verifies representative vector arithmetic/control state across
signals and scheduling. It does not exhaustively test every instruction or
register, establish Pixman pixel correctness, measure card performance, or prove
real-finger interaction. The normal renderer remains unchanged.

[Preparation reconciliation](preparation-reconciliation.json) maps the earlier
build/full-guest/load checkpoints to proposal tasks with exact evidence hashes.
The Pixman host detector test was rerun with its required pinned source
environment variable; the initially bare invocation failed before running.

## Normal recovery after executing vectors

An ordinary serial `reboot` returned to the persistent normal selection without
operator intervention. [trial-normal-recovery.json](trial-normal-recovery.json)
and [its serial report](trial-normal-recovery.serial.log) pass the independent
root-growth recovery checker: fresh normal boot, exact `gnr36q…` system,
unchanged boot/firmware hashes and root layout, successful no-op growth service,
active shell/seatd, protected credential permissions, Wi-Fi association and
HTTPS over `wlan0`. No full-image flash or readback was performed.

The proposal's build, guest, physical load, actual boot/context and subsequent
normal recovery tasks are complete (9/14). Pixel comparison, optional renderer
packaging, paired card costs, final decision and final publication remain open.
