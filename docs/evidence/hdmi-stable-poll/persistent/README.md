# Accepted kernel persists across ordinary boot

The operator's “everything's good land whatever we're on tell me what's next” accepted the remaining candidate checks after the outstanding HDMI reconnect/Overview gate was named. [Exact report and limits](../physical-a/operator-acceptance.json) distinguish this acceptance from the earlier read-only cable watcher and from a camera/contact trace. No precise replug or finger-contact timestamps were invented.

The reserved-board preflight verified the same running candidate, old persistent profile, all five original boot files and their root-backed backup, and the four staged candidate payloads. The narrow [promotion driver](promote-driver.py.txt), SHA256 `e1bc1070d55f204b2781595e74170136ba8a08cf69f50867dc2a4ec2d2385d08`, ran 19:56:15.565–19:56:33.751 UTC on 2026-10-20. It guarded the exact current/booted system, boot ID, GNU kernel build ID, original files, source payloads, absence of unfinished writes and available root/boot space. Before writing, it rooted both candidate and rollback closures against GC. It verified the existing backup on the root filesystem, separately from the boot partition.

The Image and initrd used the existing installer's checked root-backup replacement-gap algorithm because neither complete temporary payload fit beside its predecessor on the small boot partition. They were not claimed to be an atomic pair. DTB and bootargs used fsynced atomic renames; the explicit bootargs selector changed last. The exception path restores all four old files and the old profile. The old root-backed bundle and GC root remain available. Stage1/loader, logo and display selectors were byte-identical before/after. Only after the four target hashes matched did `nix-env --profile /nix/var/nix/profiles/system --set <candidate>` select the persistent closure. [Promotion receipt](promotion.json) describes this historical **pre-reboot** phase; its `ordinary_boot_verified:false` is superseded only by the separate fresh-boot proof below.

The exact SSH operation used the protected configuration outside Git:

```sh
scp -q -F "$PROTECTED_SSH_CONFIG" docs/evidence/hdmi-stable-poll/physical-a/accepted-preflight.json k230:/run/pane23-stable-poll-accepted-preflight.json
scp -q -F "$PROTECTED_SSH_CONFIG" docs/evidence/hdmi-stable-poll/persistent/promote-driver.py.txt k230:/var/tmp/k230-hdmi-stable-poll-candidate-a/promote-stable-poll-board.py
ssh -F "$PROTECTED_SSH_CONFIG" k230 '/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 /var/tmp/k230-hdmi-stable-poll-candidate-a/promote-stable-poll-board.py'
ssh -F "$PROTECTED_SSH_CONFIG" k230 'systemctl --no-block reboot'
```

Promotion and reboot requests exited 0. Request acceptance alone is not boot proof. The host [ordinary-boot observer](observe-driver.py.txt) waited for SSH and required **a different boot ID**, actual GNU kernel build ID, exact current/booted/persistent system and the candidate init selector. It observed 12 connection attempts, retaining the early timeouts rather than implying immediate return. At 19:58:40.851 UTC [ordinary-boot.json](ordinary-boot.json) qualified:

- Fresh boot ID `69e90426-5ead-4ebb-82d5-2a592168e34d`, distinct from the one-time trial `c17ee483-0191-48ea-986a-9738a274393e`.
- Actual kernel GNU build ID `7a61d8cea3e26df94695189b766de3fd66fa6860`, matching the tested Image/vmlinux.
- Current, booted and persistent system all `/nix/store/hpmzja32mncizz7s49ylr8pj9cy5npvg-nixos-system-nixos-26.11.20260919.20b1ddd`, with the exact candidate `init=.../init` selector.

This was an ordinary `systemctl reboot` and U-Boot autoboot using the installed files; it was **not another kexec test**. The [allowlisted kernel boot lines](boot-journal-allowlist.log) retain Linux version/model/cmdline. The complete kernel boot journal stays protected on the host; its SHA256 is in [summary.json](summary.json). No UART or camera recording was collected.

The [final cleanup driver](cleanup-driver.py.txt), SHA256 `2d3319674b80209b01efb3569d4f66e163f13f80d9e5c3e6c36ca92a48825819`, verified all installed/backup hashes and protected GC roots before retiring copied diagnostics. The entire owned diagnostic directory was first copied to protected host scratch and checked against [its file manifest](owned-copied-files.json). Only matching owned files and their generated Python cache were removed. Duplicate staged payloads were removed after verifying their candidate hashes; the host build artifacts and durable rollback backup/GC roots remain. Hash-verified temporary finalizer/config files in `/run` were also removed. [Final control](final-control.json) records before/after observations within the **new boot**, not an invalid across-reboot trace-control comparison:

- Sway PID 1046 and Rust PID 1061 retain the tested executable/config hashes; no compositor or UI-client substitution was made.
- Panel physical 568×1232@52.19Hz, transform 270, scale 1, logical 1232×568; retained landscape and unchanged `max_render_time 8` configuration.
- Real touch device present; HDMI unplugged and its virtual trackpad absent, matching panel mode.
- Standard startup terminal with idle shell and the pinned color follower; normal services active, one CPU online, no injected test device.
- Normal Pixman/output-turn configuration, trace environment/temporary UI override absent.
- All nine root-tracing hashes unchanged by cleanup, `nop` tracer, no enabled events/instances or owned cleanup timers; original tracefs mount state restored.
- All installed candidate boot-file hashes still match; loader/logo/selectors unchanged by promotion.

The board lease was released after the timestamped final verification; `summary.json` records completion. No build slot was held. Root storage still has zero unprivileged available bytes despite removing duplicate staging payloads; that separate cleanup issue is recorded without deleting unrelated closures or widening this change. The full command sources, immutable receipts and hash references distinguish built source, one-time trial, operator acceptance, persistent file selection, ordinary boot and cleanup. No universal/glass/portrait latency claim or permanent notification-shade performance fix follows from this proof.
