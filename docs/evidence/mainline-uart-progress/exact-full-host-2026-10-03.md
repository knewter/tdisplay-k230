# Exact configured objects and full matching artifacts

Evidence class: completed full matching host build, exact configured-header
RISC-V object compilation and immutable artifact inspection. No board/UART,
Bash reception, physical timer health, usable root, panel/glass or automatic
return was tested. Physical tasks5f.5–6 and task5b.5 remain **UNVERIFIED**.

The coordinator's full build used frozen revision
`35e9375736e872a28907420ad7b126596183677b`, started
2026-10-03T23:38:53.689100Z and completed 2026-10-04T00:09:27.288083Z, return0:

```sh
nix build .#kernelMainlineUartProgressTrialBootFiles \
  .#kernelMainlineUartProgress.dev --no-link --print-out-paths \
  --max-jobs 1 --cores 16
```

Our exact-object proof used branch `mainline-uart-progress`, worktree
`/home/jadams/tmp/k230-mainline-uart-progress`, revision
`80d581a4993b63354f5a5e5d8509068392a8238d`. Only after the successful completion
receipt and dependency existence checks did we reserve the shared build lock.
A dry run showed only the exact-object derivation, followed by return0:

```sh
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineUartProgressExactObjects --offline --no-link \
  --print-out-paths --max-jobs 1 --cores 2
python3 tools/mainline-drm-trial-inspect.py \
  /nix/store/gmsmqkjcb8vmh6h44xvq7y59dd9xihsh-k230-mainline-drm-trial-boot-files
```

The narrow object invocation did not rebuild the kernel. The lock is released.
Owned changes for this handoff are this exact/full evidence and task5f.2–3 entries;
no source, protocol, controller or existing output definition was changed.

## Exact object proof

Output `/nix/store/i8qvh6gwsrjlg3x12myi6bczdlfyc79j-k230-mainline-uart-progress-exact-objects`
uses actual selected `a3r0fwxh2s594xgz4amb4ydbp22l3w65` kernel.dev headers and
installed config, with source `4av3w0kigacwah6w04zfpnky4gsh0k59`.
No forced CONFIG overlay is applied. The copied config and generated autoconf
are byte-identical to the installed selected dev files before/after compilation;
both report K230_UART_PROGRESS built-in. Actual installed config SHA-256:
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`.
The [exact object receipt](exact-object-proof.json) records both config/header
hashes, source/dev paths, command and all object identities.

All three objects are ELF64 little-endian RISC-V relocatables, compiled by
GCC15.3.0 with W=1. [Compile log](exact-object-compile.log) retains the pahole
version mismatch (kernel131 versus object environment0); no C warning was
observed. [Checksums](exact-object-sha256.txt) validate all returned bytes.
[ELF inspection](exact-object-readelf.txt), via `readelf -hWSs OBJECT`, proves
snapshot/timer getter/worker in ordinary `.text`, timer state and enable flag
in ordinary `.sbss`, and the 256-byte record at BSS offset0 with alignment256.
It remains page-contained under the actual 4KiB configuration, survives initmem
freeing and is not VMAP_STACK storage. Setup/late-init functions alone use
`.init.text`. An initial local inspection assertion used the wrong timer-state
symbol name; the actual `k230_uart_progress_ready_timer_irq` was then checked.
No source/object correction or kernel fault is inferred from that script error.

This completes the exact-header requirement left open by the earlier installed
base-header-plus-overlay proof. The actual kernel's `.config`, not merely the
configure-only result, is now grounded. OPENSSL_SUPPORTS_ML_DSA is y in this
actual installed configuration (the earlier configure-only result lacked it);
the effective installed-base versus installed-reporter comparison records only
the new K230_UART_PROGRESS assignment. No hardware implication is claimed.

## Full matching artifacts

[Full artifact receipt](full-artifact-proof.json) records the coordinator's
completion fields and the successful existing inspector result. Bundle:
`/nix/store/gmsmqkjcb8vmh6h44xvq7y59dd9xihsh-k230-mainline-drm-trial-boot-files`.
Selected system `j312r12misprfg605h49bvqii097shzi`; kernel
`5cgxny407spyx9la94l1375dmpswigkm`; dev `a3r0fw…` (all full paths in receipt).

Image equals the selected kernel Image, uImage header/data CRCs and size pass,
initrd payload equals the selected system initrd, DT chosen bootargs equal the
bundle text, closure includes system/kernel and every inventoried path exists,
registration is nonempty and all bundle checksums pass. The sole init points
to that selected executable system init. Original two trace tokens are present
once, ttyS0 is the sole console and no rdinit/async/reporter/retained-console
comparison controls are baked into the artifact. Image contains the reporter
format/setup/name strings; installed config resolves all reporter dependencies
to y. These checks do not execute the reporter or initrd.

Hardware DT comparison against the earlier `brmp1qf9…` bundle passed: copy each
DTB into a temporary directory, delete only `/chosen/bootargs` using
`fdtput -d COPY /chosen bootargs`, then compare complete sorted
`dtc -I dtb -O dts -s COPY` output. Canonical SHA-256:
`c36085249e61fc1ed6f8f586b1ccbf11f22a4e27428a3e7e23b046384268fc02`.
The original files were not modified. This is complete decoded hardware-DT
identity after the documented chosen-argument mutation, not runtime equality.
The prior [22-output receipt](identities.json), [wiring receipt](wiring-identities.json)
and [exact-output selection](exact-object-selection.json) retain the separately
proved unchanged existing/preliminary kernel/object identities.

Task5f.2–3 narrow proofs passed; strict/all56 OpenSpec and whitespace checks
passed. Coordinator review, integration/push and CI
remain; controller manifest/preparation, staging and physical one-stimulus
capture belong to root. No UART or board was opened during this host proof;
the reporter still cannot guarantee firmware return, RX delivery or recovery.
