# Coherent normal boot bundle: host qualification

2026-10-01. Evidence class: **host cross-build and artifact inspection**.
Worktree `impl/coherent-normal-boot`, base `7ad556f6735e601db7ad28db0bd849533b65e649`.
The selected system is the existing Settings-qualified `p1a1hz…` closure
(application source `5bb67db128210f830dab4de0d20a4b0eca13c578`).

```
nix build .#coherentShellBootFiles --no-link --print-out-paths --max-jobs 1 --cores 4
python3 tools/coherent-shell-boot-inspect.py /nix/store/pnci1pzsca9f45mfyakcrzyk7yx2ad42-k230-coherent-shell-boot-files
python3 tests/test_coherent_shell_boot_inspect.py --bundle /nix/store/pnci1pzsca9f45mfyakcrzyk7yx2ad42-k230-coherent-shell-boot-files
openspec validate the-coherent-shell-boots-the-selected-system --strict
```

All pass; 13 fixture/tamper tests pass. `result.json` records the exact bundle,
system, kernel, initrd, source board DTB, load sizes, SHA256 and CRC32. The
inspector compares Image and initrd payloads with the selected system, checks
both legacy ramdisk CRCs and its Linux/RISC-V type, requires exactly one matching
init parameter, compares the environment and DT command lines, recreates the
DTB's only permitted modification from the pinned board tree, and checks all
1,158 closure paths and their registration records. Native DT tools are pinned
in the host bundle; they are not added to the board's system closure.

Tamper tests independently rehash wrong payloads so the deeper checks are
exercised: wrong kernel/system, duplicate init, changed environment, unrelated
DTB model change, corrupt header/payload CRC, valid-CRC wrong initrd, wrong
architecture, truncated registration and missing closure member. Initial host
inspection incorrectly required every closure output to be a directory; Nix
also allows file outputs. This host-only inspector error was corrected before
qualification. No board mutation or boot attempt occurred during these checks.

**Remaining gate:** reserve the board and use the recoverable CR-only manual
boot controller to compare the candidate and working baseline, observe actual
panel/navigation, then install and prove ordinary reboot. This does not certify
physical boot, touch, persistence, or the broader theme proposal.
