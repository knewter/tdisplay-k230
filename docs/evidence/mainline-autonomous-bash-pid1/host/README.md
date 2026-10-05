# Actual autonomous Bash PID1 host qualification

The corrected integrated controller passed actual existing-artifact preparation on 2026-10-05 from 00:23:39.973037 to 00:23:41.379468 UTC. This is host preparation and native parser evidence. No UART, board operation, build, fresh normal preflight or recovery was performed. Physical B/E/prompt, Bash/sleep execution, RX, ordinary root and touch remain UNVERIFIED.

[result.json](result.json) records the executed checks against root revision `82b27a3626733ffe99d7c69a024599f0286f558c`, controller SHA256 `666d5019b6446ba4e8e4e8e5ad5cd78315c7f5d5598dbcdc02ee04cbaaba0d36`, equal to author checkpoint `d988bb08`. The private executed script is byte-identical to [qualification-command.py](qualification-command.py). It was copied into the fresh protected directory `~/tmp/k230-mainline-autonomous-pid1-host-qualification-corrected` and executed successfully:

```
TMPDIR="$HOME/tmp" PYTHONDONTWRITEBYTECODE=1 python3 "$HOME/tmp/k230-mainline-autonomous-pid1-host-qualification-corrected/qualification-command.py" --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files --dev /nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev --normal-report "$HOME/tmp/k230-mainline-uart-memory-printk-nohz-board/normal-report.json"
```

The unchanged archive uses zstd; this invocation used host Python 3.14 native `compression.zstd`. The qualifier reads existing Nix derivations and realized files only. It imports no serial module and performs no build. Its protected output directory must be mode 0700 and fresh; private normal report, manifest, prepared runtime nonce/arguments/transport remain there and are not committed.

The actual kernel output `xna7x12lh4lmzwgmwq51cyc9wf86504p`, dev `24hbalyljs6gn6fzkkl24znv8a0x6jdl`, source `0l4mgw9hr1j7pj247jsrxjd478fnlfy8`, config SHA `52e7470b…`, worker SHA `30e8eb1e…` and Image SHA `c2c9663b…` equal the previous MemoryPrintk proof. Both outputs are tied to the same actual kernel derivation. The original successful full-build receipt remains frozen at `1c59f8565ce6baab1e97ffad23e55556961af308`; this invocation did not rebuild it or restore any source.

The five manifest files, their counts/CRCs/hashes, DT original bootargs, SHA256SUMS, wrapped initrd, selected Bash/systemd/common loader, protected normal anchors and registration-absence assertion match the prior proof. Shared preparation/observer/default transport AST remains equal to base `703e9105`; selected root controller bytes equal the corrected author checkpoint. Executable archived `/bin/sh` and `/bin/sleep` are ELF64 little-endian RISC-V with the same qualified loader. The Bash symbol tables contain defined function exports for `printf_builtin`, `test_builtin` and `exec_builtin`. Archive/common-loader/export evidence does not prove execution or an installed firmware ABI.

The native proof gate verified the committed receipt SHA `1a718d596a9c31b65651738df4128687a77f3e00cb0c0922544959dca07f42b7`, all 20 fixture hashes, test hash, whole pinned Hush source, selected Linux file bytes/function manifest and exact independently reconstructed vector. The native vector uses an explicitly public placeholder nonce; it is not the private generated runtime nonce. The fixed body is 154 bytes, recovered raw kernel arguments 477 bytes, one single-quoted Hush command 503 bytes, and wire command including CR 504 bytes, below the unchanged 512-byte bound. All reporter, trace, `nohz` and `nohlt` gates are absent from the selected volatile policy. The native hooks prove parser dispatch and recovered argv; they do not prove the installed U-Boot handler ABI, kernel boot or Bash execution.

[controller-host.md](controller-host.md) records source fixtures. A peer found a concrete accepted-bootm/unknown-flush fallback-reset boundary; it was corrected only for this selector, with the boot attempt marked before writing and no subsequent candidate bytes on unknown completion. Root and peer independently passed the final 16 focused tests. [run-history.json](run-history.json) retains the earlier superseded host artifact pass and the first reused-dictionary fixture error; neither was a hardware or actual-artifact failure. The corrected actual qualification above passed without errors.

Group 5n.2–3 host gates are complete. Group 5n.4 requires a NEW operator reset and protected normal recovery before the single root-operated comparison:

```
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --same-image-shell-pid1 --autonomous-bash-pid1 --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL --log PRIVATE_LOG --result PRIVATE_RESULT
```

The controller captures passively for 60 seconds and never requests candidate exit/reboot. B/E records and the prompt remain independent, and record presence cannot prove that record's own output call returned. Only an independently fresh protected normal postflight can prove recovery; otherwise another NEW operator reset is required. No board action is authorized by this host receipt itself. Ordinary root/touch task 5b.5 remains open.
