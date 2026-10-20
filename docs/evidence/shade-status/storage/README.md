# Safe space for the native-status candidate

The reserved board initially had zero unprivileged root bytes available (525,193,216 root-free bytes). The three named, completed investigations in `copied-files.json` belong to this session and their commands are cited by the archived stall-trace/DRM-wait/DRM-holder evidence. No process had an open descriptor or working directory in them. A protected host tar copy completed and every one of135files/354,539,689bytes matched its original SHA256 before deletion. The private archive SHA256 is committed in `copy-verified.json`; raw trace contents remain protected on the host.

The first host check was attempted while the copy still ran and failed with an incomplete-tar error. No deletion followed it. The original transfer completed0; a new complete read verified every file against the immutable inventory, allowing the guarded cleanup. `early-copy-check.json` retains the rejected check.

`cleanup-driver.py.txt` rechecks exact hashes and no open references, deletes only the explicit copied files and then their empty directories, and verifies protected controls unchanged. `cleanup.json` records root availability rising to193,183,744bytes, adequate for the candidate's4,144,432 incremental NAR bytes and bounded recovery staging. All five boot hashes, current/booted/persistent hpmz, boot69e90426, kernel notes, root tracing controls, known-good j30 backup and accepted/rollback GC roots are preserved. No Nix GC, profile deletion or unrelated cleanup occurred.

Exact commands used the protected SSH configuration pathname outside Git:

```sh
ssh -F "$PROTECTED_SSH_CONFIG" k230 "$BOARD_PYTHON -" < inventory-driver.py.txt
ssh -F "$PROTECTED_SSH_CONFIG" k230 tar -cf - -C /var/tmp k230-drm-holder-20261020b k230-stall-trace-20261020 k230-drm-wait-20261020 > "$PROTECTED_HOST_COPY"
# Only after transfer exit0 and complete host SHA256 verification:
ssh -F "$PROTECTED_SSH_CONFIG" k230 "$BOARD_PYTHON -" < cleanup-driver.py.txt
```

The full protected inventory paths are deliberately limited to the three owned diagnostic directories. Boot backups were retained. This is capacity/recovery proof, not an explanation for the shade's stutter.
