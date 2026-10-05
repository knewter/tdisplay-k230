# Fixed info/kmsg: physical comparison

Physical UART capture at revision `43db3706b3d1aef60000540702271065cf6a7413`,
2026-10-05 03:22:55–03:26:21 UTC. Total invocation 206.114 seconds
includes protected preparation/loading; passive readiness bound180 seconds.
Exit1 means **ordinary init login readiness unverified**.

[Actual artifact qualification](../host/README.md) and source review passed
with unchanged p2/24h source/config/Image/DT/initrd/init/manifest and five
load/CRC expectations. Preceding NEW [armed info-comparison recovery](../../mainline-initrd-info-logging/physical-2026-10-05/recovery.json)
passed full protected identities/eight hashes/three services/registration
absence/distinct boot. This begin invocation ran its own protected preflight.

The sole info/console→info/kmsg destination value changed. One board/UART
reservation ran:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers --initrd-info-kmsg-logging \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report NEW_PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log NEW_PRIVATE_LOG --result NEW_PRIVATE_RESULT
```

Fresh Linux and `Run /init as init process` appeared. The announcement is
before exec success; it does not prove systemd started. No systemd startup,
closure-unit or login messages were observed within the bound, matching the
silent info/console comparison. Changing this backend did not restore observed
progress. This identifies neither an output-call stall nor a hardware cause.
Kmsg selection can fall back to console and records can be filtered/dropped;
it does not establish that console was unused or every record was delivered.

[Result](result.json) records safe facts and private-log hashes; [fixed
observations](fixed-observations.txt) are derived, not a raw transcript.
Independent full private physical review PASS: five strict loads/CRCs, exact printed/fresh received352-byte arguments and370-byte literal, source and uniquely guarded preflight, false chunked readiness replay and full private coverage match. Bootm is the final command annotation; reviewed source sends no later candidate input. This is not independent electrical TX proof. No camera/glass proof was obtained.
The candidate capture released the port; the separate180-second recovery listener received zero bytes, sent zero bytes and exited without fresh normal SPL/6.6/login/prompt. It did not run protected postflight and has released the port. NEW reset confirmation and recovery remain PENDING; no prior reset or automatic return is claimed.
[Publication receipt](publication.json): exact236f6bca CI/deployment passed; work revision and physical capture page HTTP200/timestamps were verified. Ordinary root/panel/glass and task5b.5 stay **UNVERIFIED**. Default logging can
later use journal-or-kmsg, so the next narrow discriminator is an unchanged
ordinary-baseline repeat; that repeat has not been run.
