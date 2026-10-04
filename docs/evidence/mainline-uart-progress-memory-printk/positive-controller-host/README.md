# Actual MemoryPrintk controller qualification

The actual new matching artifacts passed host controller preparation on
2026-10-04, from 07:15:36.553575 to 07:15:37.926705 UTC (exit 0).
This completes the actual-artifact portion of task 5l.4. It did not open UART,
send board commands, build implicitly or perform a protected board preflight.
Physical output, scheduling, recovery, ordinary root and real touch remain
**UNVERIFIED**. Root owns the separate full-build/object receipts and the
subsequent reserved physical operation.

The [safe receipt](result.json) records the selected bundle, system, kernel,
derivation/dev/config, source, Image, initrd, DT, archived executables/common
loader, five-load hashes/CRCs and protected manifest identity. The
[executed qualifier](qualification-command.py) is byte-identical to the protected
script run below (SHA256 `727a4dc6877fe43311cb6745ff1d9223fad474672751c4c41a5a69c4ebac599f`).
The controller was `1aca20f71673ea468732b78510e206adaf3281ac`; its preparation,
transport and observation function/constant AST matches frozen root
`1c59f8565ce6baab1e97ffad23e55556961af308`. That frozen build's private receipt
returned 0 and already-realized outputs contained both exact bundle and dev.
The qualifier exited 0 on its first actual run; no initial failure occurred.

```sh
TMPDIR="$HOME/tmp" python3 "$HOME/tmp/k230-mainline-uart-memory-printk-host-qualification/qualify.py" \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --dev /nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev \
  --normal-report "$HOME/tmp/k230-mainline-uart-memory-printk-board/normal-report.json"
```

The standalone copied qualifier retains its original protected directory and
worktree contract; run it with fresh outputs after an explicit successful frozen
build receipt. It requires Python 3.14 native Zstd support plus existing
`nix-store`, `nix`, `fdtget`, `dtc` and `sha256sum`; it never realizes missing
outputs. Public evidence contains no normal boot identifier, receipt token,
private address or protected report. Actual manifest/prepared helper/transport
and normal report remain in the protected host directory.

The selected kernel is
`/nix/store/xna7x12lh4lmzwgmwq51cyc9wf86504p-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
Its derivation supplies the selected realized dev; actual config SHA256
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`
matches base Memory. PRINTK, PRINTK_TIME, SERIAL_8250_CONSOLE and SERIAL_8250_DW
are built in, with PRINTK_CALLER disabled. The reviewed worker SHA256
`30e8eb1ee365d62665c9d3ffd674e973736f3d04405d53f0f5dc12c3ee23f5f2`
is read from actual immutable source
`/nix/store/0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src`.
The linked Image matches its selected kernel and contains the unique new setup
and exact KERN_INFO format with leading newline (format offset 25646280).
These artifact checks qualify the variant; they do not prove runtime gate or
output execution.

Actual DT hardware is byte-identical to base Memory after removal of the sole
`/chosen/bootargs` property; each original chosen argument value matches its
bundle. The actual archive contains the same verified RISC-V Bash, systemd,
helper executables and ELF loader as base Memory. Bundle SHA256SUMS, five load
ranges and hashes/CRCs passed. The wrapper is anchored to the protected historical
normal report and fixed CRC `99b89787`, rather than a new board readback. The
report is a host-only historical anchor; it is not a fresh recovery or preflight.
Registration absence is asserted in the prepared pre/post helper, not claimed as
a newly performed board assertion.

For this new selected system, the reconstructed base zero-input Memory literal
is 381 bytes. Adding only `k230.uart_progress_memory_printk=1` produces the exact
416-byte literal U-Boot command. No nohlt, earlycon, keep_bootcon or quiet control
is added. This comparison uses zero candidate input, NOT_REQUESTED receipt and
RX NOT_TESTED. Its parser requires fresh exact received args plus ordered UART0
registration and ttyS0 console-enable markers before trusting a timestamp-only
UMK summary; artifact preparation does not observe those live markers.

After independent source/native/exact-object/full gates and a fresh protected
normal preflight pass, the sole operator may run with fresh protected output
paths and the reviewed matching manifest:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus --uart-progress-memory-printk \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_LOG --result PRIVATE_RESULT
```

No candidate reboot or retry is authorized by a summary. Recovery requires the
independent fresh normal return/postflight or an operator reset. Tasks 5l.5–6 and
5b.5 remain open in this handoff. Existing [controller fixture proof](../controller/README.md)
is a prior preparation checkpoint, distinct from this actual-artifact execution.
