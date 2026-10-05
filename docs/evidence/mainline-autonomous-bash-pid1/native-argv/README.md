# Native fixed autonomous PID1 argv proof

Group 5n.1 PASS on the host, base `703e91050375aa260a9b44472e605d390530d3e5`.
[result.json](result.json) preserves compiler, exact source/function/fixture hashes,
independent vectors and execution facts. The selected artifact remains p2kdar89;
this proof performs no Nix/kernel build, serial open or board operation.

Run from the repository root:

```sh
python3 tests/test_mainline_autonomous_bash_pid1_argv.py
openspec validate the-board-runs-a-mainline-kernel --strict
openspec validate --all
git diff --check
```

The native command passes 12 tests (0.498s in the recorded run), using host
`cc (GCC) 16.2.1 20260810`. It compiles the entire untouched official old-Hush
v2022.10 parser (SHA `954771b8638977d12955c4da3c540a3929d47e4431a092c079192155b2d60011`)
with capture-only U-Boot callbacks. Its real execution engine dispatches exactly
one `setenv bootargs` with three arguments, producing precisely the independent
477-byte expected vector. The script's dollar signs, semicolons, `&&`, double
quotes and doubled backslashes remain data. Only the normal IFS environment
lookup occurs: no script-variable lookups, extra command dispatch or environment
writer callback. The stub stores volatile bootargs bytes; the real U-Boot setenv
handler/persistence implementation is not executed. Attribution, license and
adapter details are in the [fixture README](../../../../tests/fixtures/mainline-autonomous-pid1/README.md).

The selected Linux source is
`/nix/store/0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src`.
Exact native `next_arg`, `parse_args`, `init_setup`, `rdinit_setup`,
`repair_env_string` and `set_init_arg` functions produce only `-c` and the full
154-byte script. The script's first `n=` is split then repaired, exterior double
quotes disappear, and its dollars/backslashes remain unchanged. Actual setup
reset loops are tested in both init/rdinit orders, and post-`--` init/rdinit text
is argv rather than setup. A small adapter supplies setup registration dispatch;
other pre-`--` handlers are inert. This is selected parser execution, not a kernel
boot or successful target exec.

Four valid nonce patterns pass the complete native pipeline. Invalid nonce
length/case/characters and changed quote/backslash/variable/script/extra-command
syntax are rejected by the fixture's fixed-input check before Hush execution.
Separate unqualified negative runs demonstrate actual extra-command dispatch,
variable lookup and the old-Hush backslash transformation; those effects are
observed by inert hooks and never execute a real saveenv/reset. Python only
orchestrates compilation and compares raw bytes, without a shell lexer/shlex.
The unchanged script/bootargs/transport are 154/477/503 bytes; adding the host CR
makes 504, within the unchanged 512-byte bound.

The first warning-strict harness compile rejected upstream Hush's seven existing
signed/unsigned comparisons at lines 2955–3116. The final harness disables only
`-Wsign-compare` for that unchanged snapshot; all other compiler output is fatal.
No parser source bytes were changed. An attempted license copy from a conventional
host pathname was absent; COPYING instead contains the GPL-2 text from the exact
selected Linux source's `LICENSES/preferred/GPL-2.0`.

Controller/actual-artifact qualification, installed U-Boot/architecture ABI,
autonomous target records, protected physical recovery and ordinary root/touch
remain separate gates. The receipt cannot authorize arbitrary scripts or candidate
input; it qualifies only the independently reconstructed fixed vector. A host
native pass is not a physical boot, sleep/IRQ/RX result or automatic return.
