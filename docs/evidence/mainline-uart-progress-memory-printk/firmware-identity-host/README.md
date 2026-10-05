# Protected OpenSBI wrapper matches the inspected host payload

A deterministic legacy U-Boot header around the inspected 270744-byte OpenSBI
1.4 fw_jump.bin produces 270808 bytes with SHA-256 `9627edbe…f42c99`, exactly
the protected wrapper hash recorded by the normal report and freshly checked
before the [nohz-off trial](../nohz-off-physical-2026-10-04/README.md). Payload SHA
`74d08f87…938f9` identifies the actual inspected host binary.

This closes the file-identity gap in the [timer/SBI audit](../../../research/mainline-memory-printk-periodic-tick-comparison-2026-10-04.md):
the wrapper store output was absent, but its deterministic packaging is fully
reproducible without that output. `nix/stage1.nix` sets epoch 1700000000 and
wraps the existing payload as a RISC-V/Linux/uncompressed kernel with zero
load/entry and name linux. The verifier constructs that 64-byte header,
computes both CRCs and compares the resulting full-file SHA against the
protected normal file and actual physical preflight receipt.

[Executed verifier](verify-wrapper.py) and [safe result](result.json) preserve
inputs/hashes and proof limits. Exact command (return 0):

```sh
python3 docs/evidence/mainline-uart-progress-memory-printk/firmware-identity-host/verify-wrapper.py \
  --payload /nix/store/7fmfx6dan9c2dsa55cs3jba3b5wx6w6p-opensbi-k230-riscv64-unknown-linux-gnu-1.4/fw_jump.bin \
  --normal-report PRIVATE_NORMAL --trial-result PRIVATE_NOHZ_RESULT \
  --output FRESH_PRIVATE_RESULT
```

No firmware/kernel build, flash, UART access or new board readback was performed.
This is host file reconstruction tied to the earlier physical protected-file
check. It supports identifying the inspected OpenSBI payload in that file; it
does not independently observe firmware execution, runtime SSTC/backend choice,
CSR interrupt state or the cause of missing worker/observer progress. The read
source's full-width timer stop/rearm support is therefore tied to the protected
payload, while runtime behavior remains **UNVERIFIED**.
