# Deploy the completed theme consumers — 2026-10-10

Worktree `/home/jadams/tmp/k230-theme-install-2026-10-10`, branch
`deploy/themes-2026-10-10`, base/source `ddbe7204c5a64869fcb512c29fb1ef6ec6930095`.
Owned paths: the userspace-update authorization branch in
`tools/coherent-shell-board-install.py`, its host tests, and this deployment
record; the archived theme's status/evidence references will be reconciled
when installation is actually observed. The exclusive build lock protects the
matching bundle construction; the board/serial lock protects each board action.

The operator asked to continue after the completed theme parent was archived
and the new packages were identified as not yet installed. Their existing
instruction explicitly waived additional proof collection. The installer now
keeps this authorization distinct from an operator real-finger report. The
new evidence class requires explicit deployment/waiver flags, the authorized
source revision, exact candidate system/kernel/bundle/executable, and an
accepted baseline. It rejects claimed finger checks and any kernel/Image/initrd
change; the baseline profile and hashes must match the board's protected stage.
All original registration, candidate-running, init-selector, rollback-root,
protected-selector and atomic boot-file checks remain.

`python3 tests/test_coherent_shell_board_install.py` passed 13 host cases;
`python3 tests/test_coherent_shell_board_boot.py` passed five. The three new
cases distinguish authorization from physical observations and reject changed
boot code or a mismatched protected baseline. Logs are committed here. These
host checks do not claim installation. Build, staging and ordinary-boot results
are recorded below only after their actual operations finish.


## Matching bundle, stage and temporary boot

The matching `kernelMainlineDrmShellBootFiles` build passed for source
`ddbe7204c5a64869fcb512c29fb1ef6ec6930095`; the staged installer is
`abc947cbe7174f3ab9a2bfeb4de62f0c81d4bbb5`. The build produced 35 changed
userspace/system derivations and reused the existing kernel. Both `Image` and
`initrd.uimg` are byte-identical to the accepted installed baseline. Exact
bundle/system/consumer paths, timestamps and commands are in
[build-result.json](build-result.json), [build.log](build.log) and
[host-inspection.json](host-inspection.json). Host inspection validates the
selected kernel, initrd payload/uImage CRC, reconstructed DTB, system selector
and registered closure; it is separate from board startup.

[Preflight](preflight.json) read the actual accepted baseline with the [actual board probe](preflight-board-probe.py),
through the
reserved serial port, including all eight normal boot hashes, exact running
executables and four active services. Its board command succeeded; the initial
host collector rejected UART formatting. The single actual JSON record was
recovered from the private UART with `JSONDecoder.raw_decode` after removing
CR/LF. No board result was inferred or repeated to repair that parse.

The [actual stage recipe](stage-used.py) transferred only the closure delta,
verified transfer hashes, imported and rooted it, then checked the protected
normal profile and boot backups. [Transfer](transfer.json),
[staged state](staged-state.json) and [stage.log](stage.log) record success.
Staging did not alter normal boot selection.

The temporary boot controller verified all five loaded artifact lengths/CRCs,
then lost its serial connection during Linux startup. That failure remains in
[candidate-controller-disconnect.json](candidate-controller-disconnect.json).
A first reconnect observed startup still reaching the login prompt and could
not yet obtain a root prompt. A subsequent read-only reconnect passed without
another reboot: [candidate-runtime.json](candidate-runtime.json) records a new
boot ID, exact new system/kernel/Rust ELF/Sway/helper, four active services,
active DSI output, unchanged normal boot files/profile and preserved appearance
state. The actual [runtime runner](runtime-check-used.py) and
[on-board probe](inspect-runtime.py) obtained that report. This recovers identity
and service evidence; it does not turn the interrupted controller run into PASS.

[Deployment authorization](deployment-authorization.json) binds the operator's
continuation and standing physical-collection waiver to this exact candidate,
its observed temporary boot and the accepted same-kernel baseline.
[Qualification recipe](qualification-used.py) verified those identities and
saved the checked authorization on board; [qualification.log](qualification.log)
records success. It contains no real-finger check claims.

## Build retention

[Retention recipe](retain-inputs.py) enumerated the recursive selected derivation
sources and all currently realized declared outputs, including native tools
outside the runtime closure. It unions the previous verified farm's requisites.
[Retention log](retention.log), [farm build](retention-build.log),
[derivation](retain.nix) and [receipt](retention.json) record 10,627 valid paths,
78 newly retained paths and a durable GC root under
`~/.local/state/tdisplay-k230/retained-builds/theme-install-2026-10-10/`.
Every retained input was verified reachable from that root. The first local
enumeration attempted an absent previous manifest; the corrected recipe reads
the actual previous farm's requisites. No store or board mutation occurred in
that failed enumeration. Global GC policy was not changed.

The normal bundle required new native cache tools and a regenerated theme
package: these changed shared source/default-store-path inputs also changed the
selected Rust package. Retention prevents GC from deleting unchanged realized
inputs; it cannot prevent builds whose inputs changed. This build reused the
kernel, Image and initrd.


## Persistent installation and ordinary startup

The guarded installer passed. [Installation journal](installation.json) records
`Image` and `initrd.uimg` as unchanged, atomic replacements of the matching DTB
and boot arguments, the new system profile and preserved appearance markers.
Stage 1 and all three selector files retain their baseline hashes. Root backups,
candidate GC root and both rollback system roots remain valid. This is a
userspace update, with no image flash.

Commands run from this worktree:

```sh
python3 tools/coherent-shell-board-boot.py \
  --candidate /nix/store/sxn7li6gqckkfvph9d16avswz5qxlbhl-k230-coherent-shell-boot-files \
  --state /home/jadams/tmp/k230-theme-install-board-2026-10-10/state.json \
  --qualification docs/evidence/omarchy-themes/installed-consumers-2026-10-10/deployment-authorization.json \
  --output /home/jadams/tmp/k230-theme-install-board-2026-10-10/ordinary --install
python3 /home/jadams/tmp/k230-theme-install-board-2026-10-10/runtime-check.py ordinary
```

[Ordinary-boot controller](ordinary-boot.json) passed after sending no key,
manual boot command or volatile boot arguments during autoboot; its
[log](ordinary-boot.log) and the independently obtained
[ordinary-runtime.json](ordinary-runtime.json) record actual board startup.
The ordinary boot ID differs from the temporary boot. Current system and normal
profile both select
`/nix/store/925i44g1rmqyjcbz8hziyz3vvkx95waf-nixos-system-nixos-26.11.20260919.20b1ddd`.
The exact new Rust ELF, Sway and theme-helper identities match the matching
bundle; shell, shell-ui, theme-helper and touch-trackpad are all active. The DSI
output is active at 568×1232. Normal boot hashes match the installation journal,
and all rollback roots exist. The installation journal itself deliberately
keeps `ordinary_boot_verified: false`: it was written before reboot. The later
controller and runtime reports provide that separate proof.

The recorded appearance generation/report and background preference file were
absent in preflight, temporary boot, install and ordinary boot. Preservation
therefore proves those markers remained absent; it does not claim a newly
verified selected theme or fresh-HOME appearance behavior. No new physical
finger, pixel, HDMI cable, typography, spacing or performance collection was
performed. The operator's existing acceptance/waiver remains distinct from the
serial identities and active-output checks.

Installation is complete. Build and board/serial reservations are released.
The landed revision and exact-revision CI/Pages publication of this record are
reported separately from the now-observed installed system.
