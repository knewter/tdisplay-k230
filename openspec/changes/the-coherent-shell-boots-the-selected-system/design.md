## Context and observed limit

The 2026-10-01 matching vendor trial booted `/nix/store/xphf8zb00gz9hiyqkkh399rldr2ljykb-nixos-system-nixos-26.11.20260919.20b1ddd` and its selected `03zyl0…` kernel, but camera output initially appeared dark after compositor startup. Native output later showed Foot, so a dark photograph alone cannot establish a dead display. Working-kernel userspace activation showed Home after explicit navigation. Normal restoration with the original `p6z5nsr…` Image was photographed. Persistent bootargs and profile remained older. See committed baseline evidence; neither service-active state nor common scan-out debug messages prove panel acceptance.

## Decisions

1. Build the bundle from one configuration's selected system/kernel/initrd/params and the board DTB. Inspect exact payload equality, CRCs, init path and closure availability. Do not construct a working-looking bundle by mixing older kernel/modules with the selected configuration.
2. Compare recoverable candidate and working baseline using the same serial/manual load path before blaming the kernel. Trace the actual persisted boot environment separately. Keep failed observations and exact identities.
3. Stage the registered closure and boot files on the existing root, protecting them with a GC root. Save normal profile/boot artifacts before touching anything. `/nix-path-registration` must remain absent to avoid bootstrap profile replacement. Use CR-only U-Boot commands and inspect each load count and CRC.
4. Select persistently only after the candidate produces a visible usable Home/overview/app UI on the physical panel. The boot partition may lack room for duplicate Images; keep rollback on root, copy verified files under a documented interruption-safe sequence, and retain serial manual recovery from those backups. Preserve existing stage1 and selectors.
5. Complete an ordinary boot without manual candidate environment. Record booted kernel, selected init/system/profile, actual services and visible navigation, theme/background state and restoration. Credentials and network addresses remain private.

## Remaining risks

Visible navigation on the candidate remains unresolved; neither a dark terminal nor a shared debug warning establishes a driver failure. Stage1 startup versus manual load differences must be controlled. A host build cannot establish display readiness. Physical touch acceptance may use the user's focused report; injected board events must retain their own evidence class. Failed boot/recovery must remain documented, not hidden by the final successful run.
