## 1. Preserve baseline and qualify artifacts

- [x] 1.1 Commit the 2026-10-01 unaccepted matching vendor trial, exact artifact/boot identities, camera observations and successful normal restoration. Proof: committed `docs/evidence/boot-verification/2026-10-01/{README.md,result.json,normal-boot-candidate.txt,normal-boot-restore.txt,restore-verify.txt}`. No persistent selection or new finger acceptance is claimed.
- [ ] 1.2 Implement a normal bundle built from one selected coherent-shell configuration and its inspector. Proof: `nix build .#coherentShellBootFiles --no-link --print-out-paths --max-jobs 1 --cores 4`, then `python3 tools/coherent-shell-boot-inspect.py <bundle>`. Planned output/tool do not yet exist; compare selected kernel/initrd payloads, DT/env init and CRCs, not just filenames.

## 2. Diagnose and prove the candidate on the physical board

- [ ] 2.1 Compare working baseline and current vendor candidate under the same recoverable manual boot procedure; inspect persisted bootcmd/preboot and actual display behavior. Commit exact boot artifacts, serial and panel observations. Use a reserved CR-only controller `python3 tools/coherent-shell-board-boot.py --candidate <bundle> --output <new-evidence>` (planned). Do not infer root cause from shared debug warnings.
- [ ] 2.2 Repair the identified source/configuration defect, if any, and repeat qualified candidate boot. Run only the narrow affected build and relevant inspector/source tests, then record physical Home/overview/app navigation. Keep the candidate rejected while the panel is black; host or QEMU output alone does not tick this task.

## 3. Persist and verify an ordinary reboot

- [ ] 3.1 Stage the registered matching closure and rollback bundle, reserve board, install only qualified normal boot artifacts and select the matching profile. Proof: the operator controller's `--install` mode (planned), committed pre/post boot-file hashes and rollback command; preserve root layout, secrets and stage1. No whole-card flash or blanket readback is needed.
- [ ] 3.2 Reboot through untouched normal autoboot and record booted kernel, /proc/cmdline init path, /run/current-system, persistent profile, active shell services, photographed Home and usable touch navigation. Proof: `flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=5 'readlink -f /run/current-system; readlink -f /run/booted-system/kernel; cat /proc/cmdline'` plus committed visible observation. Check remembered theme/wallpaper separately; this is not all Omarchy acceptance.
- [ ] 3.3 Validate `openspec validate the-coherent-shell-boots-the-selected-system --strict`, commit/land/push source and proof, and inspect matching CI/Pages before archive. Leave physical tasks open until their actual evidence exists.
